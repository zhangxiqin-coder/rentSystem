"""
支付记录API
"""
from typing import Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
import logging

from app.database import get_db
from app.models import Payment, Room, User
from app.schemas import (
    PaymentResponse, PaymentCreate,
    PaginatedResponse, BulkPaymentCreate, BulkPaymentResponse,
    PaymentType, PaymentMethod
)
from app.core.deps import get_current_user

router = APIRouter(prefix="/payments", tags=["payments"])


# ==================== 具体路径路由（优先匹配） ====================

@router.get("/stats/yearly")
def get_yearly_stats(
    year: Optional[int] = Query(None, description="年份，默认当前年份"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取年度收租统计"""
    if not year:
        year = datetime.now().year

    # 查询当年所有支付记录
    payments = db.query(Payment).join(Room).filter(
        Room.owner_id == current_user.id,
        func.strftime('%Y', Payment.payment_date) == str(year)
    ).all()

    # 按类型和月份统计
    stats = {
        "year": year,
        "total": 0,
        "by_type": {},
        "by_month": {}
    }

    for payment in payments:
        amount = float(payment.amount) if payment.amount else 0
        month = payment.payment_date.month if payment.payment_date else 1

        stats["total"] += amount

        # 按类型统计
        ptype = payment.payment_type
        if ptype not in stats["by_type"]:
            stats["by_type"][ptype] = 0
        stats["by_type"][ptype] += amount

        # 按月份统计
        if month not in stats["by_month"]:
            stats["by_month"][month] = 0
        stats["by_month"][month] += amount

    return stats


@router.get("/stats/room/{room_id}")
def get_room_billing(
    room_id: int,
    year: Optional[int] = Query(None, description="年份，默认当前年份"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取房间账单统计"""
    # 验证房间权限
    room = db.query(Room).filter(
        Room.id == room_id,
        Room.owner_id == current_user.id
    ).first()

    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    if not year:
        year = datetime.now().year

    # 查询该房间当年所有支付记录
    payments = db.query(Payment).filter(
        Payment.room_id == room_id,
        func.strftime('%Y', Payment.payment_date) == str(year)
    ).all()

    billing = {
        "room_id": room_id,
        "room_number": room.room_number,
        "year": year,
        "total": 0,
        "by_type": {},
        "payments": []
    }

    for payment in payments:
        amount = float(payment.amount) if payment.amount else 0
        billing["total"] += amount

        ptype = payment.payment_type
        if ptype not in billing["by_type"]:
            billing["by_type"][ptype] = 0
        billing["by_type"][ptype] += amount

        billing["payments"].append({
            "id": payment.id,
            "amount": amount,
            "payment_type": ptype,
            "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
            "payment_method": payment.payment_method,
            "description": payment.description
        })

    return billing


# ==================== 列表和创建路由 ====================

@router.get("/", response_model=PaginatedResponse)
def get_payments(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=1000, description="每页数量"),
    room_id: Optional[int] = Query(None, description="房间ID筛选"),
    payment_type: Optional[str] = Query(None, description="支付类型筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取支付记录列表（分页）

    支持按房间、支付类型、状态筛选
    """
    # 构建查询条件
    # testuser3（房东姐姐）可以查看所有支付记录
    if current_user.username == "testuser3":
        query = db.query(Payment).join(Room)
    else:
        query = db.query(Payment).join(Room).filter(Room.owner_id == current_user.id)

    if room_id:
        query = query.filter(Payment.room_id == room_id)
    if payment_type:
        query = query.filter(Payment.payment_type == payment_type)
    if status:
        query = query.filter(Payment.status == status)

    # 计算总数
    total = query.count()

    # 分页查询
    offset = (page - 1) * size
    payments = query.order_by(Payment.payment_date.desc(), Payment.created_at.desc()).offset(offset).limit(size).all()

    # 转换为响应格式
    items = []
    for payment in payments:
        items.append({
            "id": payment.id,
            "room_id": payment.room_id,
            "room_number": payment.room.room_number if payment.room else None,
            "amount": float(payment.amount) if payment.amount else 0,
            "payment_type": payment.payment_type,
            "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
            "due_date": payment.due_date.isoformat() if payment.due_date else None,
            "status": payment.status,
            "payment_method": payment.payment_method,
            "description": payment.description,
            "created_at": payment.created_at.isoformat() if payment.created_at else None
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }


@router.post("/", response_model=PaymentResponse)
def create_payment(
    payment_data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建支付记录"""
    # 验证房间权限
    room = db.query(Room).filter(
        Room.id == payment_data.room_id,
        Room.owner_id == current_user.id
    ).first()

    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    # 创建支付记录（确保payment_type有值）
    payment_data_dict = payment_data.model_dump()
    if not payment_data_dict.get('payment_type'):
        payment_data_dict['payment_type'] = PaymentType.RENT

    payment = Payment(**payment_data_dict)
    db.add(payment)
    db.commit()
    db.refresh(payment)

    return payment


@router.post("/bulk", response_model=BulkPaymentResponse)
def create_bulk_payment(
    request: Request,
    data: BulkPaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量创建收租记录（房租 + 水电费）

    会自动创建：
    - 1条房租支付记录
    - 1条水费支付记录（如果有）
    - 1条电费支付记录（如果有）
    """
    # 记录请求数据（调试用）
    import json
    logger = logging.getLogger(__name__)
    logger.info(f"Bulk payment request: user={current_user.username}, room_id={data.room_id}")
    logger.info(f"Request body: {json.dumps(data.model_dump(exclude_unset=True), ensure_ascii=False, default=str)}")
    
    # 验证房间权限
    # testuser3（房东姐姐）可以为所有房间创建支付记录
    if current_user.username == "testuser3":
        room = db.query(Room).filter(Room.id == data.room_id).first()
    else:
        room = db.query(Room).filter(
            Room.id == data.room_id,
            Room.owner_id == current_user.id
        ).first()

    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    # 检查是否已经收过租（防止重复）
    from app.models import Payment
    from datetime import date
    
    payment_date = data.payment_date
    existing_payments = db.query(Payment).filter(
        Payment.room_id == data.room_id,
        Payment.payment_date == payment_date
    ).all()
    
    # 如果当天已经有支付记录，拒绝重复支付
    if existing_payments:
        raise HTTPException(
            status_code=400, 
            detail=f"{payment_date}已存在收租记录，请勿重复操作"
        )

    payments = []
    water_payment = None
    electricity_payment = None

    # 创建房租支付记录
    rent_payment = Payment(
        room_id=data.room_id,
        amount=data.rent_amount,
        payment_type=PaymentType.RENT,
        payment_date=data.payment_date,
        payment_method=data.payment_method,
        description=f"房租 {room.room_number}",
        owner_id=current_user.id
    )
    db.add(rent_payment)
    payments.append(rent_payment)

    # 创建水费支付记录（如果有）
    if data.water_charge:
        water_payment = Payment(
            room_id=data.room_id,
            amount=data.water_charge.amount,
            payment_type=PaymentType.UTILITY,
            payment_date=data.payment_date,
            payment_method=data.payment_method,
            description=f"水费 {room.room_number}",
            owner_id=current_user.id
        )
        db.add(water_payment)
        payments.append(water_payment)

    # 创建电费支付记录（如果有）
    if data.electricity_charge:
        electricity_payment = Payment(
            room_id=data.room_id,
            amount=data.electricity_charge.amount,
            payment_type=PaymentType.UTILITY,
            payment_date=data.payment_date,
            payment_method=data.payment_method,
            description=f"电费 {room.room_number}",
            owner_id=current_user.id
        )
        db.add(electricity_payment)
        payments.append(electricity_payment)

    db.commit()

    # 刷新所有支付记录以获取ID
    for payment in payments:
        db.refresh(payment)

    # 更新水电记录的payment_id
    # 使用payment_date而不是reading_date（因为reading_date可能是None或错误的）
    if data.water_charge and water_payment:
        water_reading = db.query(UtilityReading).filter(
            UtilityReading.room_id == data.room_id,
            UtilityReading.utility_type == 'water',
            UtilityReading.reading_date == data.payment_date  # 使用payment_date
        ).first()
        if water_reading:
            water_reading.payment_id = water_payment.id
    
    if data.electricity_charge and electricity_payment:
        elec_reading = db.query(UtilityReading).filter(
            UtilityReading.room_id == data.room_id,
            UtilityReading.utility_type == 'electricity',
            UtilityReading.reading_date == data.payment_date  # 使用payment_date
        ).first()
        if elec_reading:
            elec_reading.payment_id = electricity_payment.id
    
    # 更新房间的last_payment_date
    room.last_payment_date = data.payment_date
    
    db.commit()

    # 计算总额
    total_original = float(data.rent_original)
    total_actual = float(data.rent_amount)
    total_discount = total_original - total_actual

    if data.water_charge:
        total_original += float(data.water_charge.original_amount)
        total_actual += float(data.water_charge.amount)
        total_discount += float(data.water_charge.discount)

    if data.electricity_charge:
        total_original += float(data.electricity_charge.original_amount)
        total_actual += float(data.electricity_charge.amount)
        total_discount += float(data.electricity_charge.discount)

    return BulkPaymentResponse(
        success=True,
        message="批量收租成功",
        payments=[p.id for p in payments],
        total_original=total_original,
        total_actual=total_actual,
        total_discount=total_discount
    )


# ==================== 参数化路由（最后匹配） ====================

@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取单个支付记录详情"""
    payment = db.query(Payment).join(Room).filter(
        Payment.id == payment_id,
        Room.owner_id == current_user.id
    ).first()

    if not payment:
        raise HTTPException(status_code=404, detail="支付记录不存在")

    return payment


@router.delete("/{payment_id}", status_code=204)
def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除支付记录

    删除支付记录时，需要同时清理关联的水电记录的payment_id字段
    """
    # testuser3（房东姐姐）可以删除任何房间的支付记录
    if current_user.username == "testuser3":
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
    else:
        payment = db.query(Payment).join(Room).filter(
            Payment.id == payment_id,
            Room.owner_id == current_user.id
        ).first()

    if not payment:
        raise HTTPException(status_code=404, detail="支付记录不存在")

    # 如果是水电费支付，需要清理关联的水电记录的payment_id
    if payment.payment_type in ['water', 'electricity', 'utility']:
        # 导入UtilityReading模型
        from app.models import UtilityReading

        # 查找并更新关联的水电记录
        utility_readings = db.query(UtilityReading).filter(
            UtilityReading.payment_id == payment_id
        ).all()

        for reading in utility_readings:
            reading.payment_id = None

        db.commit()

    # 删除支付记录
    db.delete(payment)
    db.commit()

    return None


@router.delete("/batch", status_code=204)
def batch_delete_payments(
    payment_ids: list[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量删除支付记录

    支持一次性删除多条支付记录
    会自动清理关联的水电记录的payment_id字段
    """
    if not payment_ids:
        raise HTTPException(status_code=400, detail="请提供要删除的支付记录ID列表")

    # 导入UtilityReading模型
    from app.models import UtilityReading

    # testuser3（房东姐姐）可以删除任何房间的支付记录
    if current_user.username == "testuser3":
        payments = db.query(Payment).filter(
            Payment.id.in_(payment_ids)
        ).all()
    else:
        payments = db.query(Payment).join(Room).filter(
            Payment.id.in_(payment_ids),
            Room.owner_id == current_user.id
        ).all()

    if not payments:
        raise HTTPException(status_code=404, detail="未找到可删除的支付记录")

    # 清理水电记录的payment_id
    for payment in payments:
        if payment.payment_type in ['water', 'electricity', 'utility']:
            utility_readings = db.query(UtilityReading).filter(
                UtilityReading.payment_id == payment.id
            ).all()

            for reading in utility_readings:
                reading.payment_id = None

    # 批量删除支付记录
    for payment in payments:
        db.delete(payment)

    db.commit()

    return None
