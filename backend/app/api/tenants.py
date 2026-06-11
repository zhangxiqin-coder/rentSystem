"""
租客管理API
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import date

from app.database import get_db
from app.models import Tenant, LeaseRecord, Room, User
from app.schemas import TenantCreate, TenantUpdate, TenantResponse, LeaseRecordCreate, LeaseRecordResponse
from app.api.auth import get_current_user

router = APIRouter(prefix="/tenants", tags=["租客管理"])


@router.get("", response_model=List[TenantResponse])
def list_tenants(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取租客列表"""
    query = db.query(Tenant).filter(Tenant.owner_id == current_user.id)
    tenants = query.order_by(Tenant.created_at.desc()).offset(skip).limit(limit).all()
    return tenants


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取租客详情"""
    tenant = db.query(Tenant).filter(
        Tenant.id == tenant_id,
        Tenant.owner_id == current_user.id
    ).first()
    
    if not tenant:
        raise HTTPException(status_code=404, detail="租客不存在")
    
    return tenant


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    tenant: TenantCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建租客"""
    # 检查身份证号是否已存在
    existing = db.query(Tenant).filter(Tenant.id_card == tenant.id_card).first()
    if existing:
        raise HTTPException(status_code=400, detail="该身份证号已存在")
    
    new_tenant = Tenant(**tenant.model_dump(), owner_id=current_user.id)
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)
    return new_tenant


@router.put("/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    tenant_id: int,
    tenant_update: TenantUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新租客信息"""
    tenant = db.query(Tenant).filter(
        Tenant.id == tenant_id,
        Tenant.owner_id == current_user.id
    ).first()
    
    if not tenant:
        raise HTTPException(status_code=404, detail="租客不存在")
    
    # 如果要更新身份证号，检查是否重复
    if tenant_update.id_card and tenant_update.id_card != tenant.id_card:
        existing = db.query(Tenant).filter(Tenant.id_card == tenant_update.id_card).first()
        if existing:
            raise HTTPException(status_code=400, detail="该身份证号已存在")
    
    # 更新字段
    update_data = tenant_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)
    
    # 如果租客有最新的租赁记录，同步更新关联房间的租期
    latest_lease = db.query(LeaseRecord).filter(
        LeaseRecord.tenant_id == tenant.id
    ).order_by(LeaseRecord.lease_start.desc()).first()
    
    if latest_lease:
        # 查找该租客在当前房间的租约对应房间
        rooms = db.query(Room).filter(
            Room.tenant_id == tenant.id,
            Room.status == 'occupied'
        ).all()
        for room in rooms:
            room.lease_start = latest_lease.lease_start
            room.lease_end = latest_lease.lease_end
    
    db.commit()
    db.refresh(tenant)
    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除租客"""
    tenant = db.query(Tenant).filter(
        Tenant.id == tenant_id,
        Tenant.owner_id == current_user.id
    ).first()
    
    if not tenant:
        raise HTTPException(status_code=404, detail="租客不存在")
    
    # 检查是否有活跃的租赁记录
    active_leases = db.query(LeaseRecord).filter(
        LeaseRecord.tenant_id == tenant_id,
        LeaseRecord.is_active == True
    ).count()
    
    if active_leases > 0:
        raise HTTPException(status_code=400, detail="该租客有活跃的租赁记录，无法删除")
    
    db.delete(tenant)
    db.commit()
    return None


@router.get("/{tenant_id}/leases", response_model=List[LeaseRecordResponse])
def get_tenant_leases(
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取租客的所有租赁记录"""
    # 验证租客属于当前用户
    tenant = db.query(Tenant).filter(
        Tenant.id == tenant_id,
        Tenant.owner_id == current_user.id
    ).first()
    
    if not tenant:
        raise HTTPException(status_code=404, detail="租客不存在")
    
    leases = db.query(LeaseRecord).filter(
        LeaseRecord.tenant_id == tenant_id
    ).order_by(LeaseRecord.lease_start.desc()).all()
    
    return leases
