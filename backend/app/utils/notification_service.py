"""
Centralized notification service - eliminates duplicated notification logic
"""
from datetime import date, timedelta
from typing import Optional
from dateutil.relativedelta import relativedelta

from sqlalchemy.orm import Session

from app.models import Room, Payment, Tenant
from app.utils.wechat import (
    check_if_both_utilities_recorded,
    generate_rent_notification,
    send_wechat_message,
)


def _is_tenant_notify_restricted(db: Session, room: Room) -> tuple[bool, str]:
    """
    检查房间关联租客是否有通知日期限制（notify_after_day）。
    返回 (是否被限制, 原因说明)。
    被限制 = 今天还没到该租客约定的可通知日期。
    """
    if not room.tenant_id:
        return (False, "")

    tenant = db.query(Tenant).filter(Tenant.id == room.tenant_id).first()
    if not tenant or tenant.notify_after_day is None:
        return (False, "")

    today_day = date.today().day
    if today_day < tenant.notify_after_day:
        return (True, f"租客{tenant.name}约定每月{tenant.notify_after_day}号后才通知")

    return (False, "")


def _has_paid_for_target_cycle(db: Session, room: Room, cycle: int) -> bool:
    """
    判断目标到期周期是否已有rent payment覆盖。

    逻辑：计算当前周期到期日（lease_start + cycle个月，最后一个<=今天），
    检查是否有rent payment在该到期日±14天内。
    有 → 已付，不需再收房租
    无 → 未付，应收房租

    ⚠️ 必须检查"当前周期到期日"而非"下次到期日"：
    季付提前交租后（如8/1交了8/2季度的房租），下次到期日（11/2）±14天内
    自然没有支付，查下次到期日会误判"未付"→房租重复计入
    （2026-09-27 102-2 事故：8-01已交4650，9-27录水电时账单又含4650房租）

    与前端 shouldIncludeRent（paymentCycle.ts）逻辑一致。
    """
    if cycle <= 1:
        return False  # 月付永不走这个判断

    if not room.lease_start:
        return False  # 无租约开始日，默认未付

    today = date.today()

    # 计算当前周期到期日：最后一个 <= 今天的到期日
    if room.lease_start > today:
        return False  # 租约尚未开始
    current_due = room.lease_start
    while True:
        nxt = current_due + relativedelta(months=cycle)
        if nxt > today:
            break
        current_due = nxt

    # 检查是否有rent payment在当前周期到期日±14天内
    window_start = current_due - timedelta(days=14)
    window_end = current_due + timedelta(days=14)

    payment = db.query(Payment).filter(
        Payment.room_id == room.id,
        Payment.payment_type == 'rent',
        Payment.status != 'cancelled',
        Payment.payment_date >= window_start,
        Payment.payment_date <= window_end,
    ).first()

    return payment is not None


async def send_rent_notification_if_complete(
    db: Session,
    room: Room,
    reading_date: date,
    include_utilities: bool = True,
) -> dict:
    """
    Send rent notification if conditions are met.

    1. Skip 2501 rooms (when include_utilities=True)
    2. Check both water and electricity recorded (when include_utilities=True)
    3. For quarterly+ rooms, check if rent already collected this cycle
    4. Generate notification message
    5. Send via wechat/feishu

    Returns:
        {"sent": bool, "reason": str}
    """
    try:
        if include_utilities and room.room_number.startswith('2501'):
            return {"sent": False, "reason": "2501 room skipped"}

        # 检查租客通知日期限制
        restricted, reason = _is_tenant_notify_restricted(db, room)
        if restricted:
            return {"sent": False, "reason": reason}

        tenant_name = room.tenant_name or room.room_number
        cycle = max(1, room.payment_cycle or 1)

        # 判断是否需要包含房租：
        # payment_cycle > 1 的房间（季度付等），检查目标到期周期是否已付房租
        include_rent = True
        if cycle > 1:
            include_rent = not _has_paid_for_target_cycle(db, room, cycle)

        if include_utilities:
            utility_status = check_if_both_utilities_recorded(
                db, room.id, reading_date
            )

            if not utility_status['both_recorded']:
                return {"sent": False, "reason": "Both utilities not yet recorded"}

            message = generate_rent_notification(
                room_number=room.room_number,
                tenant_name=tenant_name,
                monthly_rent=float(room.monthly_rent),
                payment_cycle=cycle,
                water_amount=utility_status['water_amount'],
                electricity_amount=utility_status['electricity_amount'],
                water_reading=utility_status['water_reading'],
                electricity_reading=utility_status['electricity_reading'],
                water_usage=utility_status.get('water_usage', 0),
                electricity_usage=utility_status.get('electricity_usage', 0),
                last_month_data=utility_status.get('last_month'),
                include_utilities=True,
                include_rent=include_rent,
            )
        else:
            message = generate_rent_notification(
                room_number=room.room_number,
                tenant_name=tenant_name,
                monthly_rent=float(room.monthly_rent),
                payment_cycle=cycle,
                include_utilities=False,
                include_rent=include_rent,
            )

        await send_wechat_message(message)
        return {"sent": True, "reason": "Notification sent"}

    except Exception as e:
        print(f"[Warning] Failed to send rent notification for {room.room_number}: {e}")
        return {"sent": False, "reason": "Send failed", "error": str(e)}
