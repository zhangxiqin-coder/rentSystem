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
    PaymentCreate, PaymentUpdate, PaymentResponse, PaginatedResponse
)
from app.service.business import create_payment, check_overdue_payments

router = APIRouter(prefix="/payments", tags=["payments"])


def check_payment_permission(user: User):
    """检查支付权限"""
    if user.role == "tenant":
        raise HTTPException(status_code=403, detail="租客无权操作")
    return True


@router.get("", response_model=PaginatedResponse)
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
    
    # 排序
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
