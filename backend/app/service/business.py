"""
业务逻辑服务层
实现房租计算、水电费计算等核心业务逻辑
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models import Room, Payment, UtilityReading, UtilityRate, User


# ==================== 房租计算 ====================

def calculate_rent(monthly_rent: Decimal, payment_cycle: int) -> Decimal:
    """
    计算应付租金
    
    Args:
        monthly_rent: 月租金
        payment_cycle: 支付周期（月数）
    
    Returns:
        应付租金总额
    """
    return monthly_rent * payment_cycle


# ==================== 水电费计算 ====================

def get_previous_reading(
    db: Session, 
    room_id: int, 
    utility_type: str, 
    before_date: date
) -> Optional[Decimal]:
    """
    获取上次读数
    
    Args:
        db: 数据库会话
        room_id: 房间ID
        utility_type: 水电类型 (water/electricity/gas)
        before_date: 查询此日期之前的读数
    
    Returns:
        上次读数，如果没有则返回 None
    """
    reading = db.query(UtilityReading).filter(
        and_(
            UtilityReading.room_id == room_id,
            UtilityReading.utility_type == utility_type,
            UtilityReading.reading_date < before_date
        )
    ).order_by(desc(UtilityReading.reading_date)).first()
    
    return reading.reading if reading else None


def get_active_rate(
    db: Session, 
    utility_type: str, 
    on_date: date
) -> Optional[UtilityRate]:
    """
    获取有效费率
    
    Args:
        db: 数据库会话
        utility_type: 水电类型 (water/electricity/gas)
        on_date: 查询此日期生效的费率
    
    Returns:
        有效费率，如果没有则返回 None
    """
    rate = db.query(UtilityRate).filter(
        and_(
            UtilityRate.utility_type == utility_type,
            UtilityRate.effective_date <= on_date,
            UtilityRate.is_active == True
        )
    ).order_by(desc(UtilityRate.effective_date)).first()
    
    return rate


def calculate_utility_cost(
    current: Decimal, 
    previous: Decimal, 
    rate: Decimal
) -> Tuple[Decimal, Decimal]:
    """
    计算水电费用
    
    Args:
        current: 本次读数
        previous: 上次读数
        rate: 费率
    
    Returns:
        (用量, 费用)
    
    Raises:
        ValueError: 如果当前读数小于上次读数
    """
    if current < previous:
        raise ValueError("当前读数不能小于上次读数")
    
    usage = current - previous
    amount = usage * rate
    
    return usage, amount


def create_utility_reading(
    db: Session,
    room_id: int,
    utility_type: str,
    reading: Decimal,
    reading_date: date,
    recorded_by: Optional[int] = None,
    notes: Optional[str] = None
) -> UtilityReading:
    """
    创建水电抄表记录（自动计算用量和费用）
    
    Args:
        db: 数据库会话
        room_id: 房间ID
        utility_type: 水电类型
        reading: 本次读数
        reading_date: 抄表日期
        recorded_by: 记录人ID
        notes: 备注
    
    Returns:
        创建的抄表记录
    
    Raises:
        ValueError: 业务规则验证失败
    """
    # 1. 获取上次读数
    previous_reading = get_previous_reading(db, room_id, utility_type, reading_date)
    if previous_reading is None:
        previous_reading = Decimal('0')
    
    # 2. 验证当前读数
    if reading < previous_reading:
        raise ValueError("当前读数不能小于上次读数")
    
    # 3. 获取有效费率
    rate = get_active_rate(db, utility_type, reading_date)
    if rate is None:
        raise ValueError(f"未找到有效的{utility_type}费率")
    
    # 4. 计算用量和费用
    usage, amount = calculate_utility_cost(reading, previous_reading, rate.rate_per_unit)
    
    # 5. 创建记录
    utility_reading = UtilityReading(
        room_id=room_id,
        utility_type=utility_type,
        reading=reading,
        reading_date=reading_date,
        previous_reading=previous_reading,
        usage=usage,
        amount=amount,
        rate_used=rate.rate_per_unit,
        recorded_by=recorded_by,
        notes=notes
    )
    
    try:
        db.add(utility_reading)
        db.commit()
        db.refresh(utility_reading)
        return utility_reading
    except Exception as e:
        db.rollback()
        raise


# ==================== 支付状态管理 ====================

def check_overdue_payments(db: Session) -> List[Payment]:
    """
    检查并更新逾期支付记录
    
    Args:
        db: 数据库会话
    
    Returns:
        逾期支付列表
    """
    today = date.today()
    
    # 查询所有待支付且已过期的记录
    overdue_payments = db.query(Payment).filter(
        and_(
            Payment.status == 'pending',
            Payment.due_date < today
        )
    ).all()
    
    # 更新状态为逾期
    for payment in overdue_payments:
        payment.status = 'overdue'
    
    db.commit()
    
    return overdue_payments


def create_payment(
    db: Session,
    room_id: int,
    payment_type: str,
    payment_date: date,
    amount: Optional[Decimal] = None,
    due_date: Optional[date] = None,
    status: str = 'completed',
    payment_method: Optional[str] = None,
    description: Optional[str] = None,
    receipt_image: Optional[str] = None
) -> Payment:
    """
    创建支付记录（自动计算租金）
    
    Args:
        db: 数据库会话
        room_id: 房间ID
        payment_type: 支付类型 (rent/deposit/utility/other)
        payment_date: 支付日期
        amount: 支付金额（租金类型会自动计算）
        due_date: 应付日期
        status: 支付状态
        payment_method: 支付方式
        description: 描述
        receipt_image: 收据图片
    
    Returns:
        创建的支付记录
    
    Raises:
        ValueError: 业务规则验证失败
    """
    # 获取房间信息
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise ValueError("房间不存在")
    
    # 如果是租金类型且未指定金额，自动计算
    if payment_type == 'rent' and amount is None:
        amount = calculate_rent(room.monthly_rent, room.payment_cycle)
    
    # 如果金额仍为空，验证
    if amount is None:
        raise ValueError("必须指定支付金额")
    
    # 创建支付记录
    payment = Payment(
        room_id=room_id,
        amount=amount,
        payment_type=payment_type,
        payment_date=payment_date,
        due_date=due_date,
        status=status,
        payment_method=payment_method,
        description=description,
        receipt_image=receipt_image
    )
    
    try:
        db.add(payment)
        db.commit()
        db.refresh(payment)
        
        # 更新房间的最后支付日期
        if payment_type == 'rent' and status == 'completed':
            room.last_payment_date = payment_date
            db.commit()
        
        return payment
    except Exception as e:
        db.rollback()
        raise


# ==================== 房间状态管理 ====================

def update_room_status(room: Room) -> Room:
    """
    根据租客信息自动更新房间状态
    
    Args:
        room: 房间对象
    
    Returns:
        更新后的房间对象
    """
    if room.tenant_name and room.tenant_name.strip():
        room.status = 'occupied'
    else:
        room.status = 'available'
    
    return room


# ==================== 租约到期提醒 ====================

def get_expiring_leases(
    db: Session, 
    days_threshold: int = 30
) -> List[dict]:
    """
    获取即将到期的租约
    
    Args:
        db: 数据库会话
        days_threshold: 天数阈值（默认30天）
    
    Returns:
        即将到期的租约列表
    """
    threshold_date = date.today() + timedelta(days=days_threshold)
    
    rooms = db.query(Room).filter(
        and_(
            Room.lease_end.isnot(None),
            Room.lease_end <= threshold_date,
            Room.status == 'occupied'
        )
    ).all()
    
    result = []
    for room in rooms:
        days_remaining = (room.lease_end - date.today()).days
        result.append({
            'room_id': room.id,
            'room_number': room.room_number,
            'tenant_name': room.tenant_name,
            'lease_end': room.lease_end,
            'days_remaining': days_remaining
        })
    
    return result


# ==================== 统计报表 ====================

def get_room_statistics(db: Session) -> dict:
    """
    获取房间统计信息
    
    Args:
        db: 数据库会话
    
    Returns:
        统计信息字典
    """
    total = db.query(Room).count()
    available = db.query(Room).filter(Room.status == 'available').count()
    occupied = db.query(Room).filter(Room.status == 'occupied').count()
    maintenance = db.query(Room).filter(Room.status == 'maintenance').count()
    
    occupancy_rate = (occupied / total * 100) if total > 0 else 0
    
    return {
        'total_rooms': total,
        'available_rooms': available,
        'occupied_rooms': occupied,
        'maintenance_rooms': maintenance,
        'occupancy_rate': round(occupancy_rate, 2)
    }


def get_revenue_statistics(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> dict:
    """
    获取收入统计信息
    
    Args:
        db: 数据库会话
        start_date: 开始日期
        end_date: 结束日期
    
    Returns:
        收入统计字典
    """
    query = db.query(Payment).filter(Payment.status == 'completed')
    
    if start_date:
        query = query.filter(Payment.payment_date >= start_date)
    if end_date:
        query = query.filter(Payment.payment_date <= end_date)
    
    payments = query.all()
    
    total_revenue = sum(p.amount for p in payments)
    rent_revenue = sum(p.amount for p in payments if p.payment_type == 'rent')
    utility_revenue = sum(p.amount for p in payments if p.payment_type == 'utility')
    deposit_revenue = sum(p.amount for p in payments if p.payment_type == 'deposit')
    
    return {
        'total_revenue': total_revenue,
        'rent_revenue': rent_revenue,
        'utility_revenue': utility_revenue,
        'deposit_revenue': deposit_revenue
    }


def get_overdue_payments(db: Session) -> List[dict]:
    """
    获取逾期支付信息
    
    Args:
        db: 数据库会话
    
    Returns:
        逾期支付列表
    """
    today = date.today()
    
    payments = db.query(Payment).join(Room).filter(
        and_(
            Payment.status == 'overdue',
            Payment.due_date < today
        )
    ).all()
    
    result = []
    for payment in payments:
        overdue_days = (today - payment.due_date).days
        result.append({
            'payment_id': payment.id,
            'room_id': payment.room_id,
            'room_number': payment.room.room_number,
            'tenant_name': payment.room.tenant_name,
            'due_date': payment.due_date,
            'overdue_days': overdue_days,
            'amount': payment.amount
        })
    
    return result
