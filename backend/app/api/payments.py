"""
支付管理 API 路由
"""
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.core.deps import get_db, get_current_user
from app.models import User, Payment, Room
from app.schemas import (
    PaymentCreate, PaymentUpdate, PaymentResponse, PaginatedResponse,
    BulkPaymentCreate, BulkPaymentResponse
)
from app.service.business import create_payment, check_overdue_payments

router = APIRouter(prefix="/payments", tags=["payments"])


def check_payment_permission(user: User):
    """检查支付权限"""
    if user.role == "tenant":
        raise HTTPException(status_code=403, detail="租客无权操作")
    return True


@router.get("", response_model=PaginatedResponse[PaymentResponse])
def list_payments(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    room_id: Optional[int] = None,
    payment_type: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    sort_by: str = "payment_date",
    order: str = "desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取支付记录列表
    
    支持分页、筛选和排序
    """
    # 自动检查逾期
    check_overdue_payments(db)
    
    query = db.query(Payment)
    
    # 租客只能查看自己房间的支付
    if current_user.role == "tenant":
        query = query.join(Room).filter(Room.tenant_name == current_user.full_name)
    
    # 筛选
    if room_id:
        query = query.filter(Payment.room_id == room_id)
    if payment_type:
        query = query.filter(Payment.payment_type == payment_type)
    if status:
        query = query.filter(Payment.status == status)
    if start_date:
        query = query.filter(Payment.payment_date >= start_date)
    if end_date:
        query = query.filter(Payment.payment_date <= end_date)
    
    # 排序 - 使用白名单验证
    ALLOWED_SORT_FIELDS = {
        'payment_date', 'amount', 'payment_type', 'status', 'due_date', 'created_at'
    }
    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = 'payment_date'
    sort_column = getattr(Payment, sort_by, Payment.payment_date)
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # 分页
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }


@router.get("/stats")
def get_payment_statistics(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取支付统计
    """
    check_payment_permission(current_user)
    
    query = db.query(Payment).filter(Payment.status == 'completed')
    
    if start_date:
        query = query.filter(Payment.payment_date >= start_date)
    if end_date:
        query = query.filter(Payment.payment_date <= end_date)
    
    payments = query.all()
    
    total_amount = sum(p.amount for p in payments)
    rent_amount = sum(p.amount for p in payments if p.payment_type == 'rent')
    utility_amount = sum(p.amount for p in payments if p.payment_type == 'utility')
    deposit_amount = sum(p.amount for p in payments if p.payment_type == 'deposit')
    
    return {
        "total_count": len(payments),
        "total_amount": total_amount,
        "rent_amount": rent_amount,
        "utility_amount": utility_amount,
        "deposit_amount": deposit_amount
    }


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取支付记录详情
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="支付记录不存在")
    
    # 租客只能查看自己房间的支付
    if current_user.role == "tenant":
        if payment.room.tenant_name != current_user.full_name:
            raise HTTPException(status_code=403, detail="无权查看此支付记录")
    
    return payment


@router.post("", response_model=PaymentResponse, status_code=201)
def create_payment_record(
    payment_data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建支付记录
    
    - 如果是租金类型且未指定金额，会自动计算（月租金 × 支付周期）
    """
    check_payment_permission(current_user)
    
    try:
        payment = create_payment(
            db,
            room_id=payment_data.room_id,
            payment_type=payment_data.payment_type,
            payment_date=payment_data.payment_date,
            amount=payment_data.amount,
            due_date=payment_data.due_date,
            status=payment_data.status,
            payment_method=payment_data.payment_method,
            description=payment_data.description,
            receipt_image=payment_data.receipt_image
        )
        return payment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{payment_id}", response_model=PaymentResponse)
def update_payment(
    payment_id: int,
    payment_data: PaymentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新支付记录
    """
    check_payment_permission(current_user)
    
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="支付记录不存在")
    
    # 已完成的支付不允许修改金额和日期
    if payment.status == 'completed':
        if payment_data.amount is not None or payment_data.payment_date is not None:
            raise HTTPException(status_code=400, detail="已完成的支付不允许修改金额和日期")
    
    # 更新字段
    update_data = payment_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(payment, key, value)
    
    db.commit()
    db.refresh(payment)
    
    return payment


@router.delete("/{payment_id}", status_code=204)
def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除支付记录
    """
    check_payment_permission(current_user)
    
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="支付记录不存在")
    
    db.delete(payment)
    db.commit()
    
    return None


@router.post("/bulk", response_model=BulkPaymentResponse, status_code=201)
def create_bulk_payment(
    payment_data: BulkPaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量创建收租记录（房租 + 水费 + 电费）
    
    支持打折，分别记录房租、水费、电费
    """
    from app.models import UtilityReading
    from decimal import Decimal
    
    check_payment_permission(current_user)
    
    # 验证房间存在
    room = db.query(Room).filter(Room.id == payment_data.room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    
    created_payments = []
    total_original = payment_data.rent_original
    total_actual = payment_data.rent_amount
    total_discount = payment_data.rent_original - payment_data.rent_amount
    
    # 1. 创建房租记录
    if payment_data.rent_amount > 0:
        rent_payment = Payment(
            room_id=payment_data.room_id,
            amount=payment_data.rent_amount,
            payment_type="rent",
            payment_date=payment_data.payment_date,
            payment_method=payment_data.payment_method,
            description=f"房租 {payment_data.notes or ''}",
            status="completed"
        )
        db.add(rent_payment)
        db.flush()  # 获取ID
        created_payments.append(rent_payment)
    
    # 2. 创建水费记录
    if payment_data.water_charge:
        water = payment_data.water_charge
        water_payment = Payment(
            room_id=payment_data.room_id,
            amount=water.amount,
            payment_type="utility",
            payment_date=payment_data.payment_date,
            payment_method=payment_data.payment_method,
            description=f"水费 {water.original_amount}吨/度",  # 简化显示，原为用水量
            status="completed"
        )
        db.add(water_payment)
        db.flush()
        created_payments.append(water_payment)
        
        total_original += water.original_amount
        total_actual += water.amount
        total_discount += water.discount
    
    # 3. 创建电费记录
    if payment_data.electricity_charge:
        electricity = payment_data.electricity_charge
        electricity_payment = Payment(
            room_id=payment_data.room_id,
            amount=electricity.amount,
            payment_type="utility",
            payment_date=payment_data.payment_date,
            payment_method=payment_data.payment_method,
            description=f"电费 {electricity.original_amount}度",
            status="completed"
        )
        db.add(electricity_payment)
        db.flush()
        created_payments.append(electricity_payment)
        
        total_original += electricity.original_amount
        total_actual += electricity.amount
        total_discount += electricity.discount
    
    # 4. 更新房间的上次付款日期
    room.last_payment_date = payment_data.payment_date
    
    db.commit()
    
    # 刷新所有payment以获取完整数据
    for p in created_payments:
        db.refresh(p)
    
    # Convert Payment objects to PaymentResponse
    payment_responses = [
        PaymentResponse(
            id=p.id,
            room_id=p.room_id,
            amount=p.amount,
            payment_type=p.payment_type,
            payment_date=p.payment_date,
            payment_method=p.payment_method,
            description=p.description,
            status=p.status,
            created_at=p.created_at,
            updated_at=p.updated_at
        )
        for p in created_payments
    ]
    
    return BulkPaymentResponse(
        success=True,
        message="收租记录创建成功",
        payments=payment_responses,
        total_original=total_original,
        total_actual=total_actual,
        total_discount=total_discount
    )


@router.get("/stats/yearly", response_model=list[dict])
def get_yearly_stats(
    year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取年度收入统计
    
    可按年份筛选，默认显示所有年份
    """
    from sqlalchemy import func, extract
    from decimal import Decimal
    
    query = db.query(
        extract('year', Payment.payment_date).label('year'),
        Payment.payment_type,
        func.sum(Payment.amount).label('total_amount'),
        func.count(Payment.id).label('count')
    ).filter(Payment.status == 'completed')
    
    if year:
        query = query.filter(extract('year', Payment.payment_date) == year)
    
    stats = query.group_by(
        extract('year', Payment.payment_date),
        Payment.payment_type
    ).order_by(extract('year', Payment.payment_date).desc()).all()
    
    result = []
    for stat in stats:
        result.append({
            'year': int(stat.year),
            'type': stat.payment_type,
            'total_amount': float(stat.total_amount),
            'count': stat.count
        })
    
    return result


@router.get("/stats/room/{room_id}", response_model=dict)
def get_room_billing(
    room_id: int,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取房间账单统计
    
    按月份汇总房租和水电费用
    """
    from sqlalchemy import func, extract
    
    # 验证房间存在
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    
    query = db.query(
        extract('year', Payment.payment_date).label('year'),
        extract('month', Payment.payment_date).label('month'),
        Payment.payment_type,
        func.sum(Payment.amount).label('total_amount'),
        func.count(Payment.id).label('count')
    ).filter(
        Payment.room_id == room_id,
        Payment.status == 'completed'
    )
    
    if year:
        query = query.filter(extract('year', Payment.payment_date) == year)
    
    stats = query.group_by(
        extract('year', Payment.payment_date),
        extract('month', Payment.payment_date),
        Payment.payment_type
    ).order_by(
        extract('year', Payment.payment_date).desc(),
        extract('month', Payment.payment_date).desc()
    ).all()
    
    # 按年月分组
    billing = {}
    for stat in stats:
        key = f"{int(stat.year)}-{int(stat.month):02d}"
        if key not in billing:
            billing[key] = {
                'year': int(stat.year),
                'month': int(stat.month),
                'rent': 0,
                'water': 0,
                'electricity': 0,
                'total': 0
            }
        
        billing[key][stat.payment_type] = float(stat.total_amount)
        billing[key]['total'] += float(stat.total_amount)
    
    return {
        'room': {
            'id': room.id,
            'room_number': room.room_number,
            'monthly_rent': float(room.monthly_rent)
        },
        'billing': list(billing.values())
    }
