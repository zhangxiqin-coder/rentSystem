"""
提醒API - 租约到期、付款日提醒
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import date, timedelta
from typing import List, Optional

from app.database import get_db
from app.models import Room, Payment, UtilityReading
from app.schemas import ReminderResponse, ReminderItem
from app.core.deps import get_db, get_current_user
from app.utils.wechat import send_wechat_message

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("/upcoming", response_model=ReminderResponse)
async def get_upcoming_reminders(
    days_ahead: int = 7,
    include_overdue: bool = True,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    获取即将到期的提醒（租约到期、付款日）
    
    Args:
        days_ahead: 提前几天提醒（默认7天）
        include_overdue: 是否包含逾期
    """
    today = date.today()
    end_date = today + timedelta(days=days_ahead)
    
    reminders = []
    
    # 获取所有已租房间
    rooms = db.query(Room).filter(Room.status == "occupied").all()
    
    for room in rooms:
        # 1. 检查租约到期
        if room.lease_end:
            days_until_lease_end = (room.lease_end - today).days
            
            if 0 <= days_until_lease_end <= days_ahead:
                reminders.append(ReminderItem(
                    room_id=room.id,
                    room_number=room.room_number,
                    reminder_type="lease_expiry",
                    reminder_date=room.lease_end,
                    days_left=days_until_lease_end,
                    amount=float(room.monthly_rent),
                    tenant_name=room.tenant_name,
                    message=f"租约将于{days_until_lease_end}天后到期（{room.lease_end}）"
                ))
            elif include_overdue and days_until_lease_end < 0:
                reminders.append(ReminderItem(
                    room_id=room.id,
                    room_number=room.room_number,
                    reminder_type="lease_overdue",
                    reminder_date=room.lease_end,
                    days_left=days_until_lease_end,
                    amount=float(room.monthly_rent),
                    tenant_name=room.tenant_name,
                    message=f"租约已逾期{-days_until_lease_end}天"
                ))
        
        # 2. 检查付款日
        if room.last_payment_date and room.payment_cycle:
            # 计算下次付款日期
            year = room.last_payment_date.year
            month = room.last_payment_date.month + room.payment_cycle
            while month > 12:
                month -= 12
                year += 1
            
            try:
                next_payment = date(year, month, room.last_payment_date.day)
            except ValueError:
                next_payment = date(year, month, 28)
            
            days_until_payment = (next_payment - today).days
            
            if 0 <= days_until_payment <= days_ahead:
                # 获取最近的水电费用
                water_amount = 0
                electricity_amount = 0
                recent_reading = db.query(UtilityReading).filter(
                    UtilityReading.room_id == room.id,
                    UtilityReading.utility_type == "water"
                ).order_by(UtilityReading.reading_date.desc()).first()

                if recent_reading:
                    water_amount = float(recent_reading.amount or 0)

                recent_reading = db.query(UtilityReading).filter(
                    UtilityReading.room_id == room.id,
                    UtilityReading.utility_type == "electricity"
                ).order_by(UtilityReading.reading_date.desc()).first()

                if recent_reading:
                    electricity_amount = float(recent_reading.amount or 0)

                cycle = room.payment_cycle or 1
                rent_due = float(room.monthly_rent) * cycle
                total_amount = rent_due + water_amount + electricity_amount
                rent_label = f"房租（{cycle}个月）" if cycle > 1 else "房租"

                reminders.append(ReminderItem(
                    room_id=room.id,
                    room_number=room.room_number,
                    reminder_type="payment_due",
                    reminder_date=next_payment,
                    days_left=days_until_payment,
                    amount=total_amount,
                    tenant_name=room.tenant_name,
                    breakdown={
                        "rent": rent_due,
                        "water": water_amount,
                        "electricity": electricity_amount
                    },
                    message=f"应付{rent_label}¥{total_amount:.2f}（{rent_label}¥{rent_due:.2f} + 水电¥{water_amount + electricity_amount:.2f}）"
                ))
            elif include_overdue and days_until_payment < 0:
                cycle = room.payment_cycle or 1
                rent_due = float(room.monthly_rent) * cycle
                reminders.append(ReminderItem(
                    room_id=room.id,
                    room_number=room.room_number,
                    reminder_type="payment_overdue",
                    reminder_date=next_payment,
                    days_left=days_until_payment,
                    amount=rent_due,
                    tenant_name=room.tenant_name,
                    message=f"房租已逾期{-days_until_payment}天未付"
                ))
    
    # 按日期排序
    reminders.sort(key=lambda x: (x.reminder_date, x.reminder_type))
    
    return ReminderResponse(
        total=len(reminders),
        reminders=reminders,
        as_of_date=today
    )


@router.post("/send-notifications")
async def send_reminder_notifications(
    days_ahead: int = 7,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    发送提醒通知到微信
    """
    # 获取提醒列表
    reminder_response = await get_upcoming_reminders(days_ahead=days_ahead, include_overdue=True, db=db, current_user=current_user)

    if not reminder_response.reminders:
        return {"message": "没有需要发送的提醒", "sent_count": 0}

    # 构建消息内容
    lines = ["📋 收款提醒\n"]

    current_date = None
    for reminder in reminder_response.reminders:
        reminder_date_str = reminder.reminder_date.strftime("%Y-%m-%d")
        if reminder_date_str != current_date:
            lines.append(f"\n📅 {reminder_date_str}")
            current_date = reminder_date_str

        emoji = "🏠" if reminder.reminder_type in ["lease_expiry", "lease_overdue"] else "💰"
        days_text = "今天" if reminder.days_left == 0 else f"{reminder.days_left}天后"
        lines.append(f"{emoji} {reminder.room_number} {days_text} {reminder.message}")

    message = "\n".join(lines)

    # 发送到微信
    try:
        result = await send_wechat_message(message)
        return {
            "message": "提醒已发送",
            "sent_count": len(reminder_response.reminders),
            "reminders": reminder_response.reminders
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送失败: {str(e)}")


@router.post("/send-rent-reminder/{room_id}")
async def send_rent_reminder_for_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    为单个房间发送催租通知（不含水电）

    适用于：
    - 2501开头的房间（水电分摊，不单独录入）
    - 其他只需催房租的场景
    """
    from app.utils.notification_service import send_rent_notification_if_complete

    # 获取房间信息
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    if not room.tenant_name:
        raise HTTPException(status_code=400, detail="房间无租客信息")

    # 发送催租通知
    result = await send_rent_notification_if_complete(
        db, room, date.today(), include_utilities=False
    )

    if result["sent"]:
        cycle = room.payment_cycle or 1
        rent_due = float(room.monthly_rent) * cycle
        return {
            "success": True,
            "message": f"已发送 {room.room_number} 催租通知",
            "room_number": room.room_number,
            "tenant_name": room.tenant_name,
            "rent_amount": rent_due
        }
    else:
        raise HTTPException(status_code=500, detail=f"发送失败: {result.get('error', result.get('reason', '未知错误'))}")


@router.get("/summary")
async def get_reminders_summary(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    获取提醒摘要统计
    """
    today = date.today()
    next_7_days = today + timedelta(days=7)
    next_30_days = today + timedelta(days=30)
    
    rooms = db.query(Room).filter(Room.status == "occupied").all()
    
    lease_expiry_7days = 0
    lease_expiry_30days = 0
    payment_due_today = 0
    payment_due_7days = 0
    overdue_payments = 0
    overdue_leases = 0
    
    for room in rooms:
        # 租约到期统计
        if room.lease_end:
            days_until = (room.lease_end - today).days
            if 0 <= days_until <= 7:
                lease_expiry_7days += 1
            if 0 <= days_until <= 30:
                lease_expiry_30days += 1
            if days_until < 0:
                overdue_leases += 1
        
        # 付款统计
        if room.last_payment_date and room.payment_cycle:
            year = room.last_payment_date.year
            month = room.last_payment_date.month + room.payment_cycle
            while month > 12:
                month -= 12
                year += 1
            
            try:
                next_payment = date(year, month, room.last_payment_date.day)
            except ValueError:
                next_payment = date(year, month, 28)
            
            days_until = (next_payment - today).days
            if days_until == 0:
                payment_due_today += 1
            if 0 <= days_until <= 7:
                payment_due_7days += 1
            if days_until < 0:
                overdue_payments += 1
    
    return {
        "lease_expiry": {
            "next_7_days": lease_expiry_7days,
            "next_30_days": lease_expiry_30days,
            "overdue": overdue_leases
        },
        "payment_due": {
            "today": payment_due_today,
            "next_7_days": payment_due_7days,
            "overdue": overdue_payments
        },
        "total_reminders": lease_expiry_7days + payment_due_7days + overdue_payments + overdue_leases
    }
