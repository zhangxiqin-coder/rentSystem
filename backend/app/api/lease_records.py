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
    FinalReadingItem, TransferRequest, TransferResponse
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

    # 同步房间表冗余字段（2026-10-02 2-2501-A事故根因之一：
    # 改租约不回写房间表，收租周期锚点 rooms.lease_start 与租约脱节→房租误判）
    # 仅当该租约生效中且覆盖今天时同步（历史/未来租约不动房间当前状态）
    from datetime import date as _date
    if existing.is_active and existing.lease_start <= _date.today() <= existing.lease_end:
        room = db.query(Room).filter(Room.id == existing.room_id).first()
        if room:
            tenant = db.query(Tenant).filter(Tenant.id == existing.tenant_id).first() if existing.tenant_id else None
            if tenant:
                room.tenant_id = tenant.id
                room.tenant_name = tenant.name
                room.tenant_phone = tenant.phone
                room.tenant_id_card = tenant.id_card
            room.lease_start = existing.lease_start
            room.lease_end = existing.lease_end
            room.monthly_rent = existing.monthly_rent
            room.deposit_amount = existing.deposit_amount
            room.status = "occupied"

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


@router.post("/{record_id}/transfer", response_model=TransferResponse)
def transfer_lease(
    record_id: int,
    data: TransferRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    转租：老租客退租结算 + 新租客入住，单事务完成。

    流程：
    1. 验证老租约存在、生效中、覆盖今天
    2. 老租客水电结算（可选读数 → 复用 _create_final_utility_settlement，
       退租读数自动写入房间初始读数 = 新租客起点）
    3. 老租约置 is_active=False、清本房间居住人、老租客按条件置 inactive（退租三件套）
    4. 匹配或新建新租客（同名同电话优先匹配）
    5. 创建新租约（初始读数=退租读数，实现水电无缝衔接）
    6. 新租客首期房租（复用 create_first_rent_payment，幂等可关闭）
    7. 房间换绑新租客（_sync_room_from_leases 自动完成）
    """
    from datetime import date

    record = db.query(LeaseRecord).filter(
        LeaseRecord.id == record_id,
        LeaseRecord.owner_id == current_user.id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="租赁记录不存在")

    today = date.today()
    if record.lease_start > today:
        raise HTTPException(status_code=400, detail="该租赁记录尚未生效，不能转租，请直接删除后重新入住")
    if not (record.lease_start <= today <= record.lease_end and record.is_active):
        raise HTTPException(status_code=400, detail="该租赁记录已结束，不能转租")

    room = db.query(Room).filter(Room.id == record.room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    # ===== 第一段：老租客水电结算（在租约标记结束前做）=====
    settlement = {
        "water_utility_id": None, "electricity_utility_id": None,
        "water_payment_id": None, "electricity_payment_id": None,
        "water_amount": None, "electricity_amount": None,
    }
    if data.final_water_reading is not None or data.final_electricity_reading is not None:
        try:
            settlement = _create_final_utility_settlement(
                db, room, current_user,
                data.final_water_reading, data.final_electricity_reading,
                data.utility_paid, data.utility_payment_method
            )
        except ValueError as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

    # ===== 第二段：老租约退租三件套 =====
    record.is_active = False
    db.flush()

    # 清本房间所有活跃居住人（主租客+同住人一并搬离）
    db.query(RoomOccupant).filter(
        RoomOccupant.room_id == room.id,
        RoomOccupant.is_active == True
    ).update({"is_active": False})

    # 老租客：无其他活跃租约且无其他房间活跃居住记录时置 inactive
    old_tenant = db.query(Tenant).filter(Tenant.id == record.tenant_id).first()
    if old_tenant and old_tenant.status == 'active':
        other_active_lease = db.query(LeaseRecord.id).filter(
            LeaseRecord.tenant_id == old_tenant.id,
            LeaseRecord.id != record.id,
            LeaseRecord.lease_start <= today,
            LeaseRecord.lease_end >= today,
            LeaseRecord.is_active == True
        ).first()
        other_active_occupant = db.query(RoomOccupant.id).filter(
            RoomOccupant.tenant_id == old_tenant.id,
            RoomOccupant.room_id != room.id,
            RoomOccupant.is_active == True
        ).first()
        if not other_active_lease and not other_active_occupant:
            old_tenant.status = 'inactive'

    # ===== 第三段：新租客入住 =====
    new_name = data.new_tenant_name.strip()
    new_phone = (data.new_tenant_phone or "").strip()
    if new_phone == "13800000000":
        new_phone = ""  # 占位符一律视为未填，防止覆盖库里真实电话

    # 匹配已有租客：owner 名下同名优先复用（不重复建档），电话/身份证按新录入补齐
    new_tenant = db.query(Tenant).filter(
        Tenant.name == new_name,
        Tenant.owner_id == current_user.id
    ).first()
    if new_tenant:
        # 电话：填了才覆盖（换号场景），留空保留库里原号
        if new_phone and new_tenant.phone != new_phone:
            new_tenant.phone = new_phone
        # 身份证：终身唯一，只补空不覆盖
        if data.new_tenant_id_card and not new_tenant.id_card:
            new_tenant.id_card = data.new_tenant_id_card
    else:
        new_tenant = Tenant(
            name=new_name,
            phone=new_phone or "13800000000",  # phone 非空约束兜底
            id_card=data.new_tenant_id_card,
            status="active",
            owner_id=current_user.id
        )
        db.add(new_tenant)
        db.flush()  # 拿 new_tenant.id

    # 水电衔接：新租约初始读数 = 老租客退租读数（结算时已写入 room.initial_*），
    # 新租客没另填初始读数的字段就天然衔接；这里显式取房间当前值落进租约
    effective_rent = data.monthly_rent if data.monthly_rent is not None else room.monthly_rent
    effective_deposit = data.deposit_amount if data.deposit_amount is not None else None
    effective_cycle = data.payment_cycle if data.payment_cycle is not None else (room.payment_cycle or 1)
    if data.payment_cycle is not None:
        room.payment_cycle = data.payment_cycle

    new_lease = LeaseRecord(
        tenant_id=new_tenant.id,
        room_id=room.id,
        lease_start=data.lease_start,
        lease_end=data.lease_end,
        monthly_rent=effective_rent,
        deposit_amount=effective_deposit,
        is_active=True,
        owner_id=record.owner_id,
        notes=data.notes,
        initial_electricity_reading=room.initial_electricity_reading or 0,
        initial_water_reading=room.initial_water_reading or 0,
    )
    db.add(new_lease)
    db.flush()

    # 新租客首期房租（幂等，可关闭）
    first_payment = None
    first_amount = None
    if data.first_payment_made:
        from app.service.business import create_first_rent_payment
        first_payment, _status = create_first_rent_payment(
            db,
            room,
            payment_date=data.lease_start,
            amount=data.first_payment_amount,
            monthly_rent=effective_rent,
            payment_cycle=effective_cycle,
            owner_id=record.owner_id,
        )
        if first_payment is not None:
            first_amount = first_payment.amount

    # 房间换绑新租客（按生效租约重算房间状态）
    _sync_room_from_leases(db, room)

    db.commit()
    db.refresh(new_lease)
    db.refresh(new_tenant)

    parts = [f"转租成功：{old_tenant.name if old_tenant else '老租客'} → {new_tenant.name}"]
    if settlement["water_amount"] is not None:
        parts.append(f"老租客水费 ¥{settlement['water_amount']}（{'已收款' if settlement['water_payment_id'] else '未收款'}）")
    if settlement["electricity_amount"] is not None:
        parts.append(f"老租客电费 ¥{settlement['electricity_amount']}（{'已收款' if settlement['electricity_payment_id'] else '未收款'}）")
    if first_amount is not None:
        parts.append(f"新租客首期房租 ¥{first_amount}")

    return TransferResponse(
        message="，".join(parts),
        room_id=room.id,
        room_number=room.room_number,
        old_lease_id=record.id,
        old_tenant_id=record.tenant_id,
        new_lease_id=new_lease.id,
        new_tenant_id=new_tenant.id,
        first_payment_id=first_payment.id if first_payment is not None else None,
        first_payment_amount=first_amount,
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
