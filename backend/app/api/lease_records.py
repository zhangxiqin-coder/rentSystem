"""
租赁记录管理 API 路由
"""
from typing import Optional, List
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.deps import get_db, get_current_user
from app.models import User, LeaseRecord, Room, Tenant, RoomOccupant
from app.schemas import (
    LeaseRecordCreate, LeaseRecordUpdate, LeaseRecordResponse,
    EndLeaseRequest, EndLeaseResponse, FinalReadingContextResponse,
    FinalReadingItem
)

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
            # 生效中：日期覆盖今天且未被终止（is_active=True）
            query = query.filter(
                LeaseRecord.lease_start <= today,
                LeaseRecord.lease_end >= today,
                LeaseRecord.is_active == True
            )
        else:
            # "已结束"：日期已过、未开始、或被退租/终止（is_active=False）
            query = query.filter(
                (LeaseRecord.lease_start > today) | (LeaseRecord.lease_end < today) | (LeaseRecord.is_active == False)
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
    new_record = LeaseRecord(**record.model_dump(exclude={"first_payment_made", "first_payment_amount"}), owner_id=current_user.id)
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

    # 入住当天通常已收首期房租：自动落一笔 rent 记录（幂等，可关闭）
    if record.first_payment_made:
        from app.service.business import create_first_rent_payment
        create_first_rent_payment(
            db,
            room,
            payment_date=record.lease_start,
            amount=record.first_payment_amount,
            monthly_rent=record.monthly_rent,
            payment_cycle=room.payment_cycle or 1,
            owner_id=current_user.id,
        )

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
    生效中 = 日期覆盖今天 且 is_active=True。
    （必须过滤 is_active，否则已退租/终止的租约会把房间状态回写为"入住"）
    """
    from datetime import date
    today = date.today()
    
    active_lease = db.query(LeaseRecord).filter(
        LeaseRecord.room_id == room.id,
        LeaseRecord.lease_start <= today,
        LeaseRecord.lease_end >= today,
        LeaseRecord.is_active == True
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


@router.get("/{record_id}/final-reading-context", response_model=FinalReadingContextResponse)
def get_final_reading_context(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取退租水电上下文：上次读数 + 当前费率（供前端预填和费用预览）
    """
    record = db.query(LeaseRecord).filter(
        LeaseRecord.id == record_id,
        LeaseRecord.owner_id == current_user.id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="租赁记录不存在")

    room = db.query(Room).filter(Room.id == record.room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    from app.service.business import get_previous_reading, get_active_rate
    from datetime import date

    def _item(utility_type: str):
        prev = get_previous_reading(db, room.id, utility_type, date.today())
        rate_record = get_active_rate(db, utility_type, date.today())
        return FinalReadingItem(
            previous_reading=prev,
            rate=rate_record.rate_per_unit if rate_record else None
        )

    return FinalReadingContextResponse(
        room_id=room.id,
        room_number=room.room_number,
        water=_item("water"),
        electricity=_item("electricity")
    )


def _create_final_utility_settlement(
    db: Session,
    room: Room,
    current_user: User,
    final_water: Optional[Decimal],
    final_electricity: Optional[Decimal],
    utility_paid: bool,
    payment_method: str
) -> dict:
    """
    退租水电结算（内部函数）：
    1. 生成 UtilityReading（自动算上次读数/用量/金额）
    2. 已收款时生成 utility Payment 并回填 payment_id
    3. 把退租读数写入 Room 初始读数 → 下个租客入住时若不录入，直接用这个值

    返回结算摘要 dict（供 EndLeaseResponse 使用）
    """
    from datetime import date
    from app.models import UtilityReading, Payment
    from app.service.business import create_utility_reading

    today = date.today()
    result = {
        "water_utility_id": None, "electricity_utility_id": None,
        "water_payment_id": None, "electricity_payment_id": None,
        "water_amount": None, "electricity_amount": None,
    }

    for utility_type, final_reading in (
        ("water", final_water),
        ("electricity", final_electricity),
    ):
        if final_reading is None:
            continue

        reading = create_utility_reading(
            db,
            room_id=room.id,
            utility_type=utility_type,
            reading=final_reading,
            reading_date=today,
            recorded_by=current_user.id,
            notes="退租结算",
            owner_id=room.owner_id or current_user.id
        )
        type_name = "水费" if utility_type == "water" else "电费"
        result[f"{utility_type}_utility_id"] = reading.id

        if utility_paid and reading.amount is not None:
            payment = Payment(
                room_id=room.id,
                amount=reading.amount,
                payment_type="utility",
                payment_date=today,
                payment_method=payment_method,
                description=f"{type_name}（退租结算） {room.room_number}",
                owner_id=room.owner_id or current_user.id
            )
            db.add(payment)
            db.flush()  # 拿 payment.id
            reading.payment_id = payment.id
            result[f"{utility_type}_payment_id"] = payment.id

        result[f"{utility_type}_amount"] = reading.amount
        # 读数写入房间初始读数 → 下个租客的起点
        if utility_type == "water":
            room.initial_water_reading = final_reading
        else:
            room.initial_electricity_reading = final_reading

    return result


@router.post("/{record_id}/end-lease", response_model=EndLeaseResponse)
def end_lease(
    record_id: int,
    data: Optional[EndLeaseRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    结束租赁（退租操作）

    可选携带退租水电结算：
    - final_water_reading / final_electricity_reading: 退租时水电表读数
    - utility_paid: True 时自动生成已收款的水电缴费单
    - 退租读数会写入房间初始读数，作为下个租客首次抄表的起点
    """
    record = db.query(LeaseRecord).filter(
        LeaseRecord.id == record_id,
        LeaseRecord.owner_id == current_user.id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="租赁记录不存在")

    from datetime import date
    if record.lease_start > date.today():
        raise HTTPException(status_code=400, detail="该租赁记录尚未生效，请直接删除")

    # 水电结算（在租约标记结束前做，事务包裹）
    settlement = {
        "water_utility_id": None, "electricity_utility_id": None,
        "water_payment_id": None, "electricity_payment_id": None,
        "water_amount": None, "electricity_amount": None,
    }
    room = db.query(Room).filter(Room.id == record.room_id).first()

    if data and room and (data.final_water_reading is not None or data.final_electricity_reading is not None):
        try:
            settlement = _create_final_utility_settlement(
                db, room, current_user,
                data.final_water_reading, data.final_electricity_reading,
                data.utility_paid, data.payment_method
            )
        except ValueError as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

    # 标记为不活跃
    record.is_active = False

    # 重新根据时间同步房间信息
    if room:
        record.is_active = False
        db.flush()
        _sync_room_from_leases(db, room)

    # 清掉本房间的活跃居住人记录（主租客+同住人一并搬离）
    # 否则租客在"入住/未入住/搬离"三个tab都消失
    if room:
        db.query(RoomOccupant).filter(
            RoomOccupant.room_id == room.id,
            RoomOccupant.is_active == True
        ).update({"is_active": False})

    # 租客无其他活跃租约、也不是其他房间的活跃居住人时，置为已搬离（inactive）
    tenant = db.query(Tenant).filter(Tenant.id == record.tenant_id).first()
    if tenant and tenant.status == 'active':
        today = date.today()
        other_active_lease = db.query(LeaseRecord.id).filter(
            LeaseRecord.tenant_id == tenant.id,
            LeaseRecord.id != record.id,
            LeaseRecord.lease_start <= today,
            LeaseRecord.lease_end >= today,
            LeaseRecord.is_active == True
        ).first()
        active_occupant = db.query(RoomOccupant.id).filter(
            RoomOccupant.tenant_id == tenant.id,
            RoomOccupant.is_active == True
        ).first()
        if not other_active_lease and not active_occupant:
            tenant.status = 'inactive'

    db.commit()
    db.refresh(record)

    parts = ["退租成功"]
    if settlement["water_amount"] is not None:
        parts.append(f"水费 ¥{settlement['water_amount']}（{'已收款' if settlement['water_payment_id'] else '未收款'}）")
    if settlement["electricity_amount"] is not None:
        parts.append(f"电费 ¥{settlement['electricity_amount']}（{'已收款' if settlement['electricity_payment_id'] else '未收款'}）")

    return EndLeaseResponse(
        message="，".join(parts),
        lease_record=record,
        **settlement
    )


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

    # 恢复入住时把租客拉回 active（对齐 end-lease 置 inactive 的反向操作）
    tenant = db.query(Tenant).filter(Tenant.id == record.tenant_id).first()
    if tenant and tenant.status == 'inactive':
        tenant.status = 'active'

    # 恢复主租客在本房间的居住人记录（end-lease 清除的反向操作）
    if room and tenant:
        existing = db.query(RoomOccupant).filter(
            RoomOccupant.room_id == room.id,
            RoomOccupant.tenant_id == tenant.id
        ).first()
        if existing:
            existing.is_active = True
        else:
            db.add(RoomOccupant(
                room_id=room.id, tenant_id=tenant.id,
                role="primary", is_active=True, owner_id=record.owner_id
            ))

    db.commit()
    db.refresh(record)
    return record
