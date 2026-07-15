"""
业务逻辑服务层
实现房租计算、水电费计算等核心业务逻辑
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models import Room, Payment, UtilityReading, UtilityRate, User, LeaseRecord, Tenant


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
    previous_reading: Optional[Decimal] = None,
    recorded_by: Optional[int] = None,
    notes: Optional[str] = None,
    owner_id: Optional[int] = None
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
        owner_id: 所有者ID（用户隔离）

    Returns:
        创建的抄表记录

    Raises:
        ValueError: 业务规则验证失败
    """
    # 1. 获取上次读数（优先使用手工输入）
    if previous_reading is None:
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
        notes=notes,
        owner_id=owner_id
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
    receipt_image: Optional[str] = None,
    owner_id: Optional[int] = None
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
        owner_id: 所有者ID（用户隔离）

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
        receipt_image=receipt_image,
        owner_id=owner_id
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
    days_threshold: int = 30,
    owner_id: int = None
) -> List[dict]:
    """
    获取即将到期的租约（以LeaseRecord为准）
    
    注意：如果租约已经续签（同一房间有后续租约在旧租约到期当天或之后开始），
    则不显示在即将到期列表中
    
    Args:
        db: 数据库会话
        days_threshold: 天数阈值（默认30天）
        owner_id: 用户ID过滤
    
    Returns:
        即将到期的租约列表
    """
    today = date.today()
    threshold_date = today + timedelta(days=days_threshold)
    
    query = db.query(LeaseRecord).filter(
        and_(
            LeaseRecord.lease_start <= today,     # 已开始
            LeaseRecord.lease_end >= today,       # 还未到期
            LeaseRecord.lease_end <= threshold_date,
        )
    )
    
    if owner_id:
        query = query.filter(LeaseRecord.owner_id == owner_id)
    
    leases = query.all()
    
    result = []
    for lease in leases:
        tenant = db.query(Tenant).filter(Tenant.id == lease.tenant_id).first()
        room = db.query(Room).filter(Room.id == lease.room_id).first()
        if not tenant or not room:
            continue
        
        # 检查是否已续签：同一房间是否有后续租约在当前租约到期当天或之后开始
        has_renewal = db.query(LeaseRecord).filter(
            and_(
                LeaseRecord.room_id == lease.room_id,  # 同一房间
                LeaseRecord.tenant_id == lease.tenant_id,  # 同一租客
                LeaseRecord.lease_start >= lease.lease_end,  # 续签在旧租约到期当天或之后开始
                LeaseRecord.id != lease.id  # 排除当前租约
            )
        ).first()
        
        # 如果已续签，跳过该租约
        if has_renewal:
            continue
        
        days_remaining = (lease.lease_end - date.today()).days
        result.append({
            'lease_record_id': lease.id,
            'room_id': room.id,
            'room_number': room.room_number,
            'tenant_id': tenant.id,
            'tenant_name': tenant.name,
            'lease_end': lease.lease_end,
            'days_remaining': days_remaining,
            'monthly_rent': float(lease.monthly_rent) if lease.monthly_rent else 0
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


# ==================== 收租状态（逾期/即将到期）- 前端逻辑迁移 ====================

def _to_start_of_day(d: date) -> date:
    """对齐前端 toStartOfDay"""
    return d


def _build_due_date(year: int, month: int, day: int) -> date:
    """对齐前端 buildDueDate（处理月末溢出）"""
    import calendar
    max_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, max_day))


def _add_months_by_due_day(base: date, months: int, due_day: int) -> date:
    """对齐前端 addMonthsByDueDay"""
    d = date(base.year, base.month, 1)
    # 月份偏移
    new_month = d.month + months
    new_year = d.year + (new_month - 1) // 12
    new_month = ((new_month - 1) % 12) + 1
    return _build_due_date(new_year, new_month, due_day)


def _has_recent_rent_payment(room_id: int, payments: List[Payment], cycle_months: int) -> bool:
    """
    对齐前端 hasRecentRentPayment
    检查最近 cycleMonths*30-5 天内是否有 rent 类型的支付记录
    """
    today = date.today()
    threshold_days = cycle_months * 30 - 5
    for p in payments:
        if p.room_id != room_id:
            continue
        if not p.payment_date:
            continue
        if p.status == 'cancelled':
            continue
        if p.payment_type != 'rent':
            continue
        diff_days = (today - p.payment_date).days
        if 0 <= diff_days <= threshold_days:
            return True
    return False


def _has_any_rent_payment(room_id: int, payments: List[Payment]) -> bool:
    """对齐前端 hasAnyRentPayment"""
    for p in payments:
        if p.room_id != room_id:
            continue
        if p.status == 'cancelled':
            continue
        if p.payment_type != 'rent':
            continue
        return True
    return False


def _has_rent_payment_after(room_id: int, payments: List[Payment], after_date: date) -> bool:
    """对齐前端 hasRentPaymentAfter"""
    for p in payments:
        if p.room_id != room_id:
            continue
        if not p.payment_date:
            continue
        if p.status == 'cancelled':
            continue
        if p.payment_type != 'rent':
            continue
        if p.payment_date > after_date:
            return True
    return False


def _has_paid_this_month(
    room: Room,
    payments: List[Payment],
    get_next_payment_days_func,
    expiring_days: int
) -> bool:
    """
    对齐前端 hasPaidThisMonth
    """
    today = date.today()

    # 检查本月是否有 payment 记录
    for p in payments:
        if p.room_id != room.id:
            continue
        if not p.payment_date:
            continue
        if p.status == 'cancelled':
            continue
        if p.payment_type != 'rent':
            continue
        if p.payment_date.year == today.year and p.payment_date.month == today.month:
            return True  # 本月已交租，不显示在到期/逾期列表

    # 历史导入场景：没有 payment 记录，但 last_payment_date 已更新
    if room.last_payment_date:
        if room.last_payment_date.year == today.year and room.last_payment_date.month == today.month:
            return True

    return False


def _get_payment_due_context(
    room: Room,
    payments: List[Payment],
    overdue_cutoff_date: date,
    expiring_days: int
) -> dict:
    """
    对齐前端 getPaymentDueContext
    计算目标到期日、是否已付当前周期
    """
    today = date.today()
    cycle_months = max(1, room.payment_cycle or 1)

    # anchorSource: lease_start || last_payment_date || today
    anchor_source = room.lease_start or room.last_payment_date or today
    anchor_date = anchor_source  # date already 0:0:0
    due_day = anchor_date.day

    cursor = _build_due_date(anchor_date.year, anchor_date.month, due_day)
    previous_due = None
    prev_prev_due = None

    while cursor <= today:
        prev_prev_due = previous_due
        previous_due = cursor
        cursor = _add_months_by_due_day(cursor, cycle_months, due_day)

    next_due = cursor
    current_cycle_due = previous_due or _build_due_date(today.year, today.month, due_day)

    last_paid = room.last_payment_date

    # paidByRentRecord
    if prev_prev_due:
        paid_by_rent = _has_rent_payment_after(
            room.id, payments,
            date.fromordinal(current_cycle_due.toordinal() - 14)
        )
    else:
        paid_by_rent = _has_any_rent_payment(room.id, payments)

    # paidCurrentCycle
    paid_current_cycle = (
        _has_recent_rent_payment(room.id, payments, cycle_months)
        or (
            last_paid is not None
            and previous_due is not None
            and abs((last_paid - previous_due).days) <= 14
        )
        or paid_by_rent
        or (
            room.room_number != '502-2'
            and current_cycle_due.toordinal() < overdue_cutoff_date.toordinal()
        )
    )

    target_due = next_due if paid_current_cycle else current_cycle_due
    days_to_due = (target_due - today).days

    return {
        'target_due': target_due,
        'next_due': next_due,
        'current_cycle_due': current_cycle_due,
        'paid_current_cycle': paid_current_cycle,
        'days_to_due': days_to_due,
    }


def _get_next_payment_days(room: Room, payments: List[Payment], cutoff: Optional[date] = None, expiring: int = 7) -> int:
    """对齐前端 getNextPaymentDays"""
    if cutoff is None:
        cutoff = date(2026, 4, 22)
    ctx = _get_payment_due_context(room, payments, cutoff, expiring)
    return ctx['days_to_due']


def get_rent_payment_status(
    db: Session,
    owner_id: int = None,
    overdue_cutoff_date_str: str = '2026-04-22',
    advance_rent_days: int = 0,
    expiring_days: int = 7,
    recent_reading_days: int = 45,
) -> dict:
    """
    获取收租状态（逾期房间 + 即将到期房间）
    完全对齐前端 useOverdueManagement 的逻辑

    Args:
        db: 数据库会话
        owner_id: 用户ID过滤
        overdue_cutoff_date_str: 逾期截止日期字符串（默认 2026-04-22）
        advance_rent_days: 提前收租天数（默认 0）
        expiring_days: 即将到期天数阈值（默认 7）
        recent_reading_days: 最近水电录天数（默认 45）

    Returns:
        {
            'overdue_rooms': [...],
            'expiring_rooms': [...],
        }
    """
    today = date.today()
    cutoff = datetime.strptime(overdue_cutoff_date_str, '%Y-%m-%d').date()

    # 查询房间
    query = db.query(Room).filter(Room.status == 'occupied')
    if owner_id:
        from sqlalchemy import or_
        query = query.filter(or_(Room.owner_id == owner_id, Room.owner_id.is_(None)))
    rooms = query.all()

    # 查询所有相关支付记录
    room_ids = [r.id for r in rooms]
    payments = []
    if room_ids:
        payments = db.query(Payment).filter(
            Payment.room_id.in_(room_ids),
            Payment.status != 'cancelled'
        ).all()

    # 查询水电记录（近45天未支付）
    recent_readings_raw = []
    if room_ids:
        reading_start = today - timedelta(days=recent_reading_days)
        recent_readings_raw = db.query(UtilityReading).filter(
            UtilityReading.room_id.in_(room_ids),
            UtilityReading.reading_date >= reading_start,
            UtilityReading.reading_date <= today,
        ).all()

    # 构建每个房间最近未付水电金额
    # 前端逻辑：取每个房间最近45天内最新的water和electricity记录，
    # 如果合并记录(is_paid=False)则累加金额
    latest_unpaid_utility = {}
    # 按reading_date倒序排序，保证取到最新的
    recent_readings_raw.sort(key=lambda r: (r.reading_date or date.min, r.id or 0), reverse=True)

    # 用字典记录每个房间已处理的合并对：water_id + electricity_id = 合并记录
    # 前端是用 mergeReadings 实现的，后端需要模拟
    # 简单方案：将water和electricity按(date, room_id)配对
    room_paired = {}  # room_id -> set of reading_date
    for room_id in room_ids:
        water_list = [r for r in recent_readings_raw if r.room_id == room_id and r.utility_type == 'water']
        electric_list = [r for r in recent_readings_raw if r.room_id == room_id and r.utility_type == 'electricity']

        # 按reading_date配对（同一天的水电通常是一起录入的）
        water_by_date = {}
        for w in water_list:
            wd = str(w.reading_date)
            if wd not in water_by_date or w.id > (water_by_date[wd].id or 0):
                water_by_date[wd] = w

        electric_by_date = {}
        for e in electric_list:
            ed = str(e.reading_date)
            if ed not in electric_by_date or e.id > (electric_by_date[ed].id or 0):
                electric_by_date[ed] = e

        # 合并所有日期的水电记录
        all_dates = set(list(water_by_date.keys()) + list(electric_by_date.keys()))
        paired_utility = {}

        for d in sorted(all_dates, reverse=True):
            wt = water_by_date.get(d)
            et = electric_by_date.get(d)
            key = d
            amount = Decimal('0')
            if wt:
                amount += wt.amount or Decimal('0')
            if et:
                amount += et.amount or Decimal('0')
            if amount > 0:
                paired_utility[key] = {
                    'amount': amount,
                    'water_id': wt.id if wt else None,
                    'electric_id': et.id if et else None,
                    'date': d,
                }

        if paired_utility:
            # 检查是否已经有相关的utility payment
            has_utility_payment = any(
                p.payment_type == 'utility' and p.room_id == room_id
                for p in payments
            )
            if not has_utility_payment:
                # 取最近的日期
                latest_date = sorted(paired_utility.keys(), reverse=True)[0]
                latest_unpaid_utility[room_id] = paired_utility[latest_date]['amount']

    # 创建一个携带当前配置的 getNextPaymentDays 副本
    def _get_next_payment_days_with_config(room: Room, payments_list: List[Payment]) -> int:
        return _get_next_payment_days(room, payments_list, cutoff, expiring_days)

    # 计算逾期房间
    overdue_rooms = []
    for room in rooms:
        if room.status != 'occupied':
            continue
        if _has_paid_this_month(room, payments, _get_next_payment_days_with_config, expiring_days):
            continue
        if _has_recent_rent_payment(room.id, payments, max(1, room.payment_cycle or 1)):
            continue
        # 租期未开始的不纳入逾期
        if room.lease_start and room.lease_start > today:
            continue

        ctx = _get_payment_due_context(room, payments, cutoff, expiring_days)
        days_to_due = ctx['days_to_due']
        target_due = ctx['target_due']

        if days_to_due <= advance_rent_days:
            overdue_days = max(0, -days_to_due)
            last_payment_date = room.last_payment_date or room.lease_start
            cycle = max(1, room.payment_cycle or 1)
            utility_amount = float(latest_unpaid_utility.get(room.id, Decimal('0')))
            overdue_amount = float(room.monthly_rent or 0) * cycle + utility_amount

            overdue_rooms.append({
                'room_id': room.id,
                'room_number': room.room_number,
                'tenant_name': room.tenant_name,
                'overdue_days': overdue_days,
                'overdue_amount': overdue_amount,
                'last_payment_date': str(last_payment_date) if last_payment_date else None,
                'next_payment_date': str(target_due) if target_due else None,
                'monthly_rent': float(room.monthly_rent or 0),
                'payment_cycle': room.payment_cycle or 1,
            })

    # 按欠租天数排序
    overdue_rooms.sort(key=lambda r: r['overdue_days'], reverse=True)

    # 计算即将到期房间
    expiring_rooms = []
    for room in rooms:
        if room.status != 'occupied':
            continue
        if _has_paid_this_month(room, payments, _get_next_payment_days_with_config, expiring_days):
            continue
        # 注意：不跳过 lease_start > today 的房间
        # 因为新租约即使尚未开始，首次付款日可能在即将到期的窗口内
        # 注意：也不使用 _has_recent_rent_payment 过滤，因为刚交了上个月的租
        # 不代表下个月不需要交（如502-3: 6/21交了6月租，7/21到期仍应在列表中）

        days = _get_next_payment_days_with_config(room, payments)
        if days > advance_rent_days and days <= expiring_days:
            expiring_rooms.append({
                'room_id': room.id,
                'room_number': room.room_number,
                'tenant_name': room.tenant_name,
                'days_until_payment': days,
                'monthly_rent': float(room.monthly_rent or 0),
                'payment_cycle': room.payment_cycle or 1,
            })

    # 按到期天数排序
    expiring_rooms.sort(key=lambda r: r['days_until_payment'])

    return {
        'overdue_rooms': overdue_rooms,
        'expiring_rooms': expiring_rooms,
    }
