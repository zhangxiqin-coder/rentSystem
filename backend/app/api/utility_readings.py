"""
水电抄表管理 API 路由
"""
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.core.deps import get_db, get_current_user
from app.models import User, UtilityReading, Room
from app.schemas import (
    UtilityReadingCreate, UtilityReadingUpdate, UtilityReadingResponse, PaginatedResponse
)
from app.service.business import create_utility_reading, get_previous_reading

router = APIRouter(prefix="/utility/readings", tags=["utility-readings"])


def check_utility_permission(user: User):
    """检查水电权限"""
    if user.role == "tenant":
        raise HTTPException(status_code=403, detail="租客无权操作")
    return True


@router.get("", response_model=PaginatedResponse[UtilityReadingResponse])
def list_utility_readings(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    room_id: Optional[int] = None,
    utility_type: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    sort_by: str = "reading_date",
    order: str = "desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取水电抄表记录列表
    
    支持分页、筛选和排序
    """
    query = db.query(UtilityReading)
    
    # 租客只能查看自己房间的抄表
    if current_user.role == "tenant":
        query = query.join(Room).filter(Room.tenant_name == current_user.full_name)
    
    # 筛选
    if room_id:
        query = query.filter(UtilityReading.room_id == room_id)
    if utility_type:
        query = query.filter(UtilityReading.utility_type == utility_type)
    if start_date:
        query = query.filter(UtilityReading.reading_date >= start_date)
    if end_date:
        query = query.filter(UtilityReading.reading_date <= end_date)
    
    # 排序 - 使用白名单验证
    ALLOWED_SORT_FIELDS = {
        'reading_date', 'reading', 'amount', 'usage', 'utility_type', 'created_at'
    }
    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = 'reading_date'
    sort_column = getattr(UtilityReading, sort_by, UtilityReading.reading_date)
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


@router.get("/{reading_id}", response_model=UtilityReadingResponse)
def get_utility_reading(
    reading_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取水电抄表记录详情
    """
    reading = db.query(UtilityReading).filter(UtilityReading.id == reading_id).first()
    if not reading:
        raise HTTPException(status_code=404, detail="抄表记录不存在")
    
    # 租客只能查看自己房间的抄表
    if current_user.role == "tenant":
        if reading.room.tenant_name != current_user.full_name:
            raise HTTPException(status_code=403, detail="无权查看此抄表记录")
    
    return reading


@router.post("", response_model=UtilityReadingResponse, status_code=201)
def create_utility_reading_record(
    reading_data: UtilityReadingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建水电抄表记录
    
    自动执行：
    1. 查询上次读数
    2. 查询有效费率
    3. 计算用量和费用
    4. 冗余存储相关数据
    """
    check_utility_permission(current_user)
    
    try:
        reading = create_utility_reading(
            db,
            room_id=reading_data.room_id,
            utility_type=reading_data.utility_type,
            reading=reading_data.reading,
            reading_date=reading_data.reading_date,
            recorded_by=current_user.id,
            notes=reading_data.notes
        )
        return reading
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{reading_id}", response_model=UtilityReadingResponse)
def update_utility_reading(
    reading_id: int,
    reading_data: UtilityReadingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新水电抄表记录
    
    仅允许更新备注字段，其他字段不允许修改
    """
    check_utility_permission(current_user)
    
    reading = db.query(UtilityReading).filter(UtilityReading.id == reading_id).first()
    if not reading:
        raise HTTPException(status_code=404, detail="抄表记录不存在")
    
    # 只允许更新备注
    if reading_data.notes is not None:
        reading.notes = reading_data.notes
    
    db.commit()
    db.refresh(reading)
    
    return reading


@router.delete("/{reading_id}", status_code=204)
def delete_utility_reading(
    reading_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除水电抄表记录
    """
    check_utility_permission(current_user)
    
    reading = db.query(UtilityReading).filter(UtilityReading.id == reading_id).first()
    if not reading:
        raise HTTPException(status_code=404, detail="抄表记录不存在")
    
    db.delete(reading)
    db.commit()
    
    return None


@router.get("/previous/{room_id}/{utility_type}")
def get_previous_reading_info(
    room_id: int,
    utility_type: str,
    before_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取某房间某类型的上次读数
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    
    # 租客只能查看自己房间的读数
    if current_user.role == "tenant":
        if room.tenant_name != current_user.full_name:
            raise HTTPException(status_code=403, detail="无权查看此房间信息")
    
    if before_date is None:
        before_date = date.today()
    
    previous = get_previous_reading(db, room_id, utility_type, before_date)
    
    return {
        "room_id": room_id,
        "utility_type": utility_type,
        "previous_reading": previous,
        "before_date": before_date
    }
