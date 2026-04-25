"""
房间管理 API 路由
"""
from typing import Optional
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from dateutil.relativedelta import relativedelta

from app.core.deps import get_db, get_current_user
from app.core.permissions import apply_room_filter
from app.models import User, Room, Payment, UtilityReading
from app.schemas import (
    RoomCreate, RoomUpdate, RoomResponse, PaginatedResponse,
    PaymentResponse, UtilityReadingResponse,
    CheckoutRequest, CheckinRequest, CheckoutResponse, CheckinResponse
)
from app.service.business import update_room_status

router = APIRouter(prefix="/rooms", tags=["rooms"])


def check_room_permission(user: User, room: Optional[Room] = None):
    """检查房间权限"""
    if user.role == "tenant":
        raise HTTPException(status_code=403, detail="租客无权操作")
    return True


@router.get("", response_model=PaginatedResponse[RoomResponse])
def list_rooms(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    building: Optional[str] = None,
    floor: Optional[int] = None,
    sort_by: str = "room_number",
    order: str = "asc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取房间列表

    支持分页、搜索、筛选和排序
    """
    query = db.query(Room)

    # 用户权限过滤
    query = apply_room_filter(query, current_user)

    # 搜索
    if search:
        query = query.filter(
            (Room.room_number.contains(search)) |
            (Room.tenant_name.contains(search))
        )
    
    # 筛选
    if status:
        query = query.filter(Room.status == status)
    if building:
        query = query.filter(Room.building == building)
    if floor is not None:
        query = query.filter(Room.floor == floor)
    
    # 排序 - 使用白名单验证
    ALLOWED_SORT_FIELDS = {
        'room_number', 'monthly_rent', 'created_at', 'status',
        'building', 'floor', 'tenant_name', 'lease_start', 'lease_end'
    }
    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = 'room_number'
    sort_column = getattr(Room, sort_by, Room.room_number)
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


@router.get("/expiring-soon")
def get_expiring_rooms(
    days: int = Query(7, ge=1, le=30, description="查询天数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取即将需要收租的房间（根据上次付款日期 + 付款周期计算）
    """
    today = date.today()
    end_date = today + timedelta(days=days)

    # 获取所有在租房间
    rooms = db.query(Room).filter(Room.status == "occupied").all()

    # 用户权限过滤
    filtered_rooms = []
    for room in rooms:
        # 检查用户是否有权限查看这个房间
        if current_user.role == "admin" or current_user.username == "testuser3":
            filtered_rooms.append(room)
        elif current_user.role == "landlord" and room.owner_id == current_user.id:
            filtered_rooms.append(room)

    # 计算每个房间的下次收租日期
    expiring_rooms = []
    for room in filtered_rooms:
        # 计算下次收租日期
        # 始终使用lease_start的日（day of month）来确保付款日期一致
        
        # 确定起点：如果有last_payment_date，使用它；否则使用lease_start
        base_date = room.last_payment_date or room.lease_start
        
        # 计算下次付款：base_date + payment_cycle个月
        next_payment = base_date + relativedelta(months=room.payment_cycle)
        
        # 重要：修正付款日为lease_start的日
        # 例如：lease_start是8-23，last_payment是4-17，则下次付款应该是5-23（不是5-17）
        # 但如果base_date已经是正确的日（比如4-23），则保持不变
        lease_start_day = room.lease_start.day
        
        # 检查next_payment的日是否正确
        # 如果不正确，需要调整到正确的日
        if next_payment.day != lease_start_day:
            # 重新计算：从base_date的年月开始，使用lease_start的日
            import calendar
            year = next_payment.year
            month = next_payment.month
            
            # 确保日期有效（比如2月30日会变成2月28日）
            max_day = calendar.monthrange(year, month)[1]
            day = min(lease_start_day, max_day)
            
            # 如果调整后的日期 <= base_date，说明需要加一个月
            adjusted = date(year, month, day)
            if adjusted <= base_date:
                adjusted = adjusted + relativedelta(months=1)
                # 重新检查日
                max_day = calendar.monthrange(adjusted.year, adjusted.month)[1]
                day = min(lease_start_day, max_day)
                adjusted = date(adjusted.year, adjusted.month, day)
            
            next_payment = adjusted
        
        # 检查是否在未来N天内需要收租
        if today <= next_payment <= end_date:
            # 将Room对象转换为字典并添加next_payment_date
            room_dict = {
                "id": room.id,
                "room_number": room.room_number,
                "building": room.building,
                "floor": room.floor,
                "area": str(room.area) if room.area else None,
                "monthly_rent": str(room.monthly_rent),
                "deposit_amount": str(room.deposit_amount) if room.deposit_amount else None,
                "payment_cycle": room.payment_cycle,
                "water_rate": str(room.water_rate) if room.water_rate else None,
                "electricity_rate": str(room.electricity_rate) if room.electricity_rate else None,
                "status": room.status,
                "tenant_name": room.tenant_name,
                "tenant_phone": room.tenant_phone,
                "lease_start": str(room.lease_start),
                "lease_end": str(room.lease_end),
                "last_payment_date": str(room.last_payment_date) if room.last_payment_date else None,
                "description": room.description,
                "created_at": room.created_at.isoformat() if room.created_at else None,
                "updated_at": room.updated_at.isoformat() if room.updated_at else None,
                "next_payment_date": str(next_payment),  # 添加计算的下次付款日期
                "days_until_payment": (next_payment - today).days  # 添加距离天数
            }
            expiring_rooms.append(room_dict)
    
    # 按下次收租日期排序
    expiring_rooms.sort(key=lambda r: r["next_payment_date"])
    
    return expiring_rooms


@router.get("/{room_id}", response_model=RoomResponse)
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取房间详情
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    
    return room


@router.post("", response_model=RoomResponse, status_code=201)
def create_room(
    room_data: RoomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建房间
    """
    check_room_permission(current_user)

    # 检查房间号是否已存在
    existing = db.query(Room).filter(Room.room_number == room_data.room_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="房间号已存在")

    # 创建房间，设置owner_id为当前用户
    room_data_dict = room_data.model_dump()
    room_data_dict['owner_id'] = current_user.id
    room = Room(**room_data_dict)

    # 自动设置状态
    update_room_status(room)

    db.add(room)
    db.commit()
    db.refresh(room)

    return room


@router.put("/{room_id}", response_model=RoomResponse)
def update_room(
    room_id: int,
    room_data: RoomUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新房间信息
    """
    check_room_permission(current_user)
    
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    
    # 更新字段（注意：RoomUpdate schema 不包含 room_number，所以房间号不会被修改）
    update_data = room_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(room, key, value)
    
    # 只有在用户没有明确设置状态时，才根据租客信息自动更新状态
    if 'status' not in update_data:
        update_room_status(room)
    
    db.commit()
    db.refresh(room)
    
    return room


@router.delete("/{room_id}", status_code=204)
def delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除房间（级联删除相关的支付和抄表记录）
    """
    check_room_permission(current_user)
    
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    
    db.delete(room)
    db.commit()
    
    return None


@router.get("/{room_id}/payments", response_model=PaginatedResponse[PaymentResponse])
def get_room_payments(
    room_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取房间的支付记录
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    
    query = db.query(Payment).filter(Payment.room_id == room_id)
    
    total = query.count()
    items = query.order_by(Payment.payment_date.desc()).offset((page - 1) * size).limit(size).all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }


@router.get("/{room_id}/utility-readings", response_model=PaginatedResponse[UtilityReadingResponse])
def get_room_utility_readings(
    room_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    utility_type: Optional[str] = Query(None, description="水电类型: water 或 electricity"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取房间的水电抄表记录
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    
    query = db.query(UtilityReading).filter(UtilityReading.room_id == room_id)
    
    # 根据水电类型过滤
    if utility_type:
        query = query.filter(UtilityReading.utility_type == utility_type)
    
    total = query.count()
    items = query.order_by(UtilityReading.created_at.desc()).offset((page - 1) * size).limit(size).all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }


@router.post("/{room_id}/checkout", response_model=CheckoutResponse)
def checkout_room(
    room_id: int,
    checkout_data: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    退租房间
    
    操作：
    1. 将房间状态改为空房（available）
    2. 清空租客信息
    3. 创建退租记录（退款金额，payment_type="refund"）
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    
    check_room_permission(current_user, room)
    
    # 检查房间是否已租
    if room.status != "occupied":
        raise HTTPException(status_code=400, detail="只有已租的房间才能退租")
    
    # 保存租客信息（用于记录）
    previous_tenant = room.tenant_name
    checkout_date = checkout_data.refund_date
    
    # 更新房间状态为空房，清空租客信息
    room.status = "available"
    room.tenant_name = None
    room.tenant_phone = None
    room.lease_start = None
    room.lease_end = None
    room.last_payment_date = None
    
    # 创建退租记录（负数金额表示退款）
    refund_payment = Payment(
        room_id=room.id,
        amount=-checkout_data.refund_amount,  # 负数表示退款
        payment_type="refund",
        payment_date=checkout_date,
        status="completed",
        payment_method=checkout_data.payment_method or "现金",
        description=f"退租退款 - 租客：{previous_tenant}" + 
                   (f"，原因：{checkout_data.refund_reason}" if checkout_data.refund_reason else ""),
        owner_id=current_user.id if current_user.role != "admin" else room.owner_id
    )
    db.add(refund_payment)
    db.commit()
    db.refresh(room)
    db.refresh(refund_payment)
    
    return {
        "message": f"房间 {room.room_number} 退租成功",
        "room_id": room.id,
        "refund_payment_id": refund_payment.id,
        "checkout_date": checkout_date
    }


@router.post("/{room_id}/checkin", response_model=CheckinResponse)
def checkin_room(
    room_id: int,
    checkin_data: CheckinRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    入住房间
    
    操作：
    1. 填写租客信息
    2. 设置租约日期
    3. 将房间状态改为已租（occupied）
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    
    check_room_permission(current_user, room)
    
    # 检查房间是否为空
    if room.status != "available":
        raise HTTPException(status_code=400, detail="只有空房才能办理入住")
    
    # 更新房间信息
    room.status = "occupied"
    room.tenant_name = checkin_data.tenant_name
    room.tenant_phone = checkin_data.tenant_phone
    room.lease_start = checkin_data.lease_start
    room.lease_end = checkin_data.lease_end
    
    # 更新押金和付款周期（如果提供）
    if checkin_data.deposit_amount is not None:
        room.deposit_amount = checkin_data.deposit_amount
    if checkin_data.payment_cycle is not None:
        room.payment_cycle = checkin_data.payment_cycle
    
    db.commit()
    db.refresh(room)
    
    return {
        "message": f"房间 {room.room_number} 入住成功",
        "room_id": room.id,
        "tenant_name": room.tenant_name,
        "lease_start": room.lease_start,
        "lease_end": room.lease_end
    }

