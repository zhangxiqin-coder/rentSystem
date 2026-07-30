"""
房间居住人管理API（多租客：主租客 + 亲友）
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import RoomOccupant, Room, Tenant
from app.schemas import RoomOccupantCreate, RoomOccupantUpdate, RoomOccupantResponse
from app.api.auth import get_current_user

router = APIRouter(prefix="/room-occupants", tags=["房间居住人管理"])


def _build_response(occ: RoomOccupant) -> RoomOccupantResponse:
    """构造含租客详细信息的响应"""
    return RoomOccupantResponse(
        id=occ.id,
        room_id=occ.room_id,
        tenant_id=occ.tenant_id,
        role=occ.role,
        relation=occ.relation,
        is_active=occ.is_active,
        created_at=occ.created_at,
        updated_at=occ.updated_at,
        tenant_name=occ.tenant.name if occ.tenant else None,
        tenant_phone=occ.tenant.phone if occ.tenant else None,
        tenant_id_card=occ.tenant.id_card if occ.tenant else None,
        tenant_notes=occ.tenant.notes if occ.tenant else None,
    )


@router.get("/room/{room_id}", response_model=List[RoomOccupantResponse])
def list_room_occupants(
    room_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取房间的所有居住人"""
    # 验证房间属于当前用户
    room = db.query(Room).filter(Room.id == room_id, Room.owner_id == current_user.id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    occupants = db.query(RoomOccupant).filter(
        RoomOccupant.room_id == room_id,
        RoomOccupant.owner_id == current_user.id
    ).order_by(
        # 主租客排前面，其次按创建时间
        RoomOccupant.role.desc(),
        RoomOccupant.created_at.asc()
    ).all()

    return [_build_response(o) for o in occupants]


@router.post("/room/{room_id}", response_model=RoomOccupantResponse, status_code=status.HTTP_201_CREATED)
def add_room_occupant(
    room_id: int,
    data: RoomOccupantCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """为房间添加居住人（主租客或亲友）"""
    # 验证房间
    room = db.query(Room).filter(Room.id == room_id, Room.owner_id == current_user.id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    # 验证租客存在且属于当前用户
    tenant = db.query(Tenant).filter(
        Tenant.id == data.tenant_id,
        Tenant.owner_id == current_user.id
    ).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="租客不存在")

    # 检查是否已存在
    existing = db.query(RoomOccupant).filter(
        RoomOccupant.room_id == room_id,
        RoomOccupant.tenant_id == data.tenant_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该租客已在此房间的居住人列表中")

    # 如果角色是 primary，先把房间现有的 primary 降为 secondary（每个房间只能有一个主租客）
    if data.role == "primary":
        db.query(RoomOccupant).filter(
            RoomOccupant.room_id == room_id,
            RoomOccupant.role == "primary"
        ).update({RoomOccupant.role: "secondary"})

    occupant = RoomOccupant(
        room_id=room_id,
        tenant_id=data.tenant_id,
        role=data.role,
        relation=data.relation,
        is_active=data.is_active,
        owner_id=current_user.id
    )
    db.add(occupant)
    db.commit()
    db.refresh(occupant)
    return _build_response(occupant)


@router.put("/{occupant_id}", response_model=RoomOccupantResponse)
def update_room_occupant(
    occupant_id: int,
    data: RoomOccupantUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新居住人信息（角色、关系、状态）"""
    occupant = db.query(RoomOccupant).filter(
        RoomOccupant.id == occupant_id,
        RoomOccupant.owner_id == current_user.id
    ).first()
    if not occupant:
        raise HTTPException(status_code=404, detail="居住人记录不存在")

    # 如果改为 primary，先把同房间其他 primary 降为 secondary
    if data.role == "primary" and occupant.role != "primary":
        db.query(RoomOccupant).filter(
            RoomOccupant.room_id == occupant.room_id,
            RoomOccupant.role == "primary",
            RoomOccupant.id != occupant_id
        ).update({RoomOccupant.role: "secondary"})

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(occupant, field, value)

    db.commit()
    db.refresh(occupant)
    return _build_response(occupant)


@router.delete("/{occupant_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_room_occupant(
    occupant_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """移除居住人（从房间居住人列表删除，不影响租客本身）"""
    occupant = db.query(RoomOccupant).filter(
        RoomOccupant.id == occupant_id,
        RoomOccupant.owner_id == current_user.id
    ).first()
    if not occupant:
        raise HTTPException(status_code=404, detail="居住人记录不存在")

    db.delete(occupant)
    db.commit()
    return None
