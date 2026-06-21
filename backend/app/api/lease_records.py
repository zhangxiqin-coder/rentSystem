"""
租赁记录管理 API 路由
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.deps import get_db, get_current_user
from app.models import User, LeaseRecord, Room, Tenant
from app.schemas import LeaseRecordCreate, LeaseRecordUpdate, LeaseRecordResponse

router = APIRouter(prefix="/lease-records", tags=["lease_records"])


@router.get("", response_model=List[LeaseRecordResponse])
def list_lease_records(
    tenant_id: Optional[int] = Query(None),
    room_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取租赁记录列表"""
    query = db.query(LeaseRecord).filter(LeaseRecord.owner_id == current_user.id)

    if tenant_id:
        query = query.filter(LeaseRecord.tenant_id == tenant_id)
    if room_id:
        query = query.filter(LeaseRecord.room_id == room_id)
    if is_active is not None:
        from datetime import date
        today = date.today()
        if is_active:
            # 按时间判断"生效中"的租约
            query = query.filter(
                LeaseRecord.lease_start <= today,
                LeaseRecord.lease_end >= today
            )
        else:
            # 按时间判断"已结束"或"待生效"的租约
            query = query.filter(
                (LeaseRecord.lease_start > today) | (LeaseRecord.lease_end < today)
            )

    records = query.order_by(desc(LeaseRecord.created_at)).all()
    return records


@router.get("/{record_id}", response_model=LeaseRecordResponse)
def get_lease_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取单个租赁记录"""
    record = db.query(LeaseRecord).filter(
        LeaseRecord.id == record_id,
        LeaseRecord.owner_id == current_user.id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="租赁记录不存在")

    return record


@router.post("", response_model=LeaseRecordResponse, status_code=201)
def create_lease_record(
    record: LeaseRecordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建租赁记录（入住操作）"""
    # 验证租客存在且属于当前用户
    tenant = db.query(Tenant).filter(
        Tenant.id == record.tenant_id,
        Tenant.owner_id == current_user.id
    ).first()

    if not tenant:
        raise HTTPException(status_code=404, detail="租客不存在")

    # 验证房间存在且属于当前用户
    room = db.query(Room).filter(
        Room.id == record.room_id,
        Room.owner_id == current_user.id
    ).first()

    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    # 验证日期
    if record.lease_end <= record.lease_start:
        raise HTTPException(status_code=400, detail="租期结束日期必须大于开始日期")

    # 创建租赁记录
    new_record = LeaseRecord(**record.model_dump(), owner_id=current_user.id)
    db.add(new_record)

    # 更新房间的当前租客信息
    room.tenant_id = tenant.id
    room.tenant_name = tenant.name
    room.tenant_phone = tenant.phone
    room.tenant_id_card = tenant.id_card
    room.lease_start = record.lease_start
    room.lease_end = record.lease_end
    room.monthly_rent = record.monthly_rent
    room.deposit_amount = record.deposit_amount
    room.status = "occupied"

    # 更新房间的初始水电读数
    if record.initial_electricity_reading:
        room.initial_electricity_reading = record.initial_electricity_reading
    if record.initial_water_reading:
        room.initial_water_reading = record.initial_water_reading

    db.commit()
    db.refresh(new_record)
    return new_record


@router.put("/{record_id}", response_model=LeaseRecordResponse)
def update_lease_record(
    record_id: int,
    record: LeaseRecordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新租赁记录"""
    existing = db.query(LeaseRecord).filter(
        LeaseRecord.id == record_id,
        LeaseRecord.owner_id == current_user.id
    ).first()

    if not existing:
        raise HTTPException(status_code=404, detail="租赁记录不存在")

    update_data = record.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(existing, key, value)

    db.commit()
    db.refresh(existing)
    return existing


@router.delete("/{record_id}")
def delete_lease_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除租赁记录"""
    record = db.query(LeaseRecord).filter(
        LeaseRecord.id == record_id,
        LeaseRecord.owner_id == current_user.id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="租赁记录不存在")

    room = db.query(Room).filter(Room.id == record.room_id).first()
    
    # 删除记录
    db.delete(record)
    db.commit()
    
    # 删除后，检查该房间是否还有其他生效中的租约
    if room:
        _sync_room_from_leases(db, room)
    
    return None


def _sync_room_from_leases(db: Session, room: Room):
    """
    根据房间的有效租赁记录同步房间的租客信息和状态。
    按时间判断（lease_start <= today <= lease_end）为生效中。
    """
    from datetime import date
    today = date.today()
    
    active_lease = db.query(LeaseRecord).filter(
        LeaseRecord.room_id == room.id,
        LeaseRecord.lease_start <= today,
        LeaseRecord.lease_end >= today
    ).order_by(LeaseRecord.lease_start.desc()).first()
    
    if active_lease:
        tenant = db.query(Tenant).filter(Tenant.id == active_lease.tenant_id).first()
        if tenant:
            room.tenant_id = tenant.id
            room.tenant_name = tenant.name
            room.tenant_phone = tenant.phone
            room.tenant_id_card = tenant.id_card
            room.lease_start = active_lease.lease_start
            room.lease_end = active_lease.lease_end
            room.monthly_rent = active_lease.monthly_rent
            room.status = "occupied"
        else:
            _clear_room_tenant(room)
    else:
        _clear_room_tenant(room)


def _clear_room_tenant(room: Room):
    """清空房间的租客信息"""
    room.tenant_id = None
    room.tenant_name = None
    room.tenant_phone = None
    room.tenant_id_card = None
    room.lease_start = None
    room.lease_end = None
    room.status = "available"


@router.post("/{record_id}/end-lease", response_model=LeaseRecordResponse)
def end_lease(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """结束租赁（退租操作）"""
    record = db.query(LeaseRecord).filter(
        LeaseRecord.id == record_id,
        LeaseRecord.owner_id == current_user.id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="租赁记录不存在")

    from datetime import date
    if record.lease_start > date.today():
        raise HTTPException(status_code=400, detail="该租赁记录尚未生效，请直接删除")

    # 标记为不活跃
    record.is_active = False

    # 重新根据时间同步房间信息
    room = db.query(Room).filter(Room.id == record.room_id).first()
    if room:
        record.is_active = False
        db.flush()
        _sync_room_from_leases(db, room)

    db.commit()
    db.refresh(record)
    return record


@router.post("/{record_id}/restore", response_model=LeaseRecordResponse)
def restore_lease(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """恢复租赁（恢复入住操作）"""
    record = db.query(LeaseRecord).filter(
        LeaseRecord.id == record_id,
        LeaseRecord.owner_id == current_user.id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="租赁记录不存在")

    from datetime import date
    if record.lease_start <= date.today() <= record.lease_end:
        raise HTTPException(status_code=400, detail="该租赁记录已是生效状态")

    # 标记为活跃
    record.is_active = True

    # 重新根据时间同步房间信息
    room = db.query(Room).filter(Room.id == record.room_id).first()
    if room:
        record.is_active = True
        db.flush()
        _sync_room_from_leases(db, room)

    db.commit()
    db.refresh(record)
    return record
