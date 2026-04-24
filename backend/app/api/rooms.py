"""
房间管理 API 路由
"""
from typing import Optional
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models import User, Room, Payment, UtilityReading
from app.schemas import (
    RoomCreate, RoomUpdate, RoomResponse, PaginatedResponse,
    PaymentResponse, UtilityReadingResponse
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


@router.get("/expiring-soon", response_model=list[RoomResponse])
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
    
    # 计算每个房间的下次收租日期
    expiring_rooms = []
    for room in rooms:
        # 使用 last_payment_date 或 lease_start 作为起点
        last_payment = room.last_payment_date or room.lease_start
        
        # 计算下次收租日期：起点 + 付款周期（月）
        # 计算方法：起点日期的月份 + payment_cycle
        year = last_payment.year
        month = last_payment.month + room.payment_cycle
        while month > 12:
            month -= 12
            year += 1
        
        # 处理日期溢出（比如1月31日加1个月）
        # 重要：使用 lease_start 的日期（day），而不是 last_payment 的日期
        # 这样可以确保付款日期与租约开始日期一致
        days_in_month = [31, 29 if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
        day = min(room.lease_start.day, days_in_month)
        next_payment = date(year, month, day)
        
        # 检查是否在未来N天内需要收租
        if today <= next_payment <= end_date:
            expiring_rooms.append(room)
    
    # 按下次收租日期排序
    expiring_rooms.sort(key=lambda r: (
        (r.last_payment_date or r.lease_start).year,
        (r.last_payment_date or r.lease_start).month,
        (r.last_payment_date or r.lease_start).day
    ))
    
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
    
    # 创建房间
    room = Room(**room_data.model_dump())
    
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

