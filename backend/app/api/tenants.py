"""
租客管理API
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.database import get_db
from app.models import Tenant, LeaseRecord, Room, User
from app.schemas import TenantCreate, TenantUpdate, TenantResponse, LeaseRecordCreate, LeaseRecordResponse, RenewLeaseRequest
from app.api.auth import get_current_user

router = APIRouter(prefix="/tenants", tags=["租客管理"])


@router.get("", response_model=List[TenantResponse])
def list_tenants(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取租客列表"""
    from sqlalchemy import or_
    query = db.query(Tenant).filter(Tenant.owner_id == current_user.id)
    
    # 状态筛选：未入住(unassigned)/入住(active)/搬离(inactive)
    if status == 'unassigned':
        # 未入住：active但没有活跃租约（根据时间判断）
        active_subquery = db.query(LeaseRecord.id).filter(
            LeaseRecord.tenant_id == Tenant.id,
            LeaseRecord.lease_start <= date.today(),
            LeaseRecord.lease_end >= date.today()
        )
        query = query.filter(Tenant.status == 'active', ~active_subquery.exists())
    elif status == 'active':
        # 入住：active且有活跃租约（根据时间判断）
        active_subquery = db.query(LeaseRecord.id).filter(
            LeaseRecord.tenant_id == Tenant.id,
            LeaseRecord.lease_start <= date.today(),
            LeaseRecord.lease_end >= date.today()
        )
        query = query.filter(Tenant.status == 'active', active_subquery.exists())
    elif status == 'inactive':
        # 搬离
        query = query.filter(Tenant.status == 'inactive')
    
    # 搜索（姓名/电话/身份证号）
    if search:
        keyword = f"%{search}%"
        query = query.filter(
            or_(
                Tenant.name.like(keyword),
                Tenant.phone.like(keyword),
                Tenant.id_card.like(keyword),
            )
        )
    
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
    # 检查身份证号是否已存在（只检查有身份证号的）
    if tenant.id_card:
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
    
    # 检查是否有活跃的租赁记录（根据时间判断）
    active_leases = db.query(LeaseRecord).filter(
        LeaseRecord.tenant_id == tenant_id,
        LeaseRecord.lease_start <= date.today(),
        LeaseRecord.lease_end >= date.today()
    ).count()
    
    if active_leases > 0:
        raise HTTPException(status_code=400, detail="该租客有活跃的租赁记录，无法删除")
    
    db.delete(tenant)
    db.commit()
    return None


@router.post("/{tenant_id}/renew", response_model=LeaseRecordResponse)
def renew_tenant_lease(
    tenant_id: int,
    renew_data: RenewLeaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    租客续租 — 生成一条新的租赁记录
    
    逻辑：
    1. 找到租客当前的活跃租约
    2. 将旧租约 is_active 设为 False
    3. 创建新的 LeaseRecord
    4. 更新 Room 的租期信息
    5. 租客状态改为 active（如果之前是 inactive）
    """
    from dateutil.relativedelta import relativedelta
    
    # 验证租客
    tenant = db.query(Tenant).filter(
        Tenant.id == tenant_id,
        Tenant.owner_id == current_user.id
    ).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="租客不存在")
    
    # 找到当前活跃租约（按时间判断）
    active_lease = db.query(LeaseRecord).filter(
        LeaseRecord.tenant_id == tenant_id,
        LeaseRecord.lease_start <= date.today(),
        LeaseRecord.lease_end >= date.today()
    ).order_by(LeaseRecord.lease_start.desc()).first()
    
    if not active_lease:
        raise HTTPException(status_code=400, detail="该租客没有活跃的租赁记录，无法续租")
    
    # 获取关联房间
    room = db.query(Room).filter(Room.id == active_lease.room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="关联房间不存在")
    
    # 1. 旧租约失效（标记is_active，但前端显示按时间计算）
    active_lease.is_active = False
    
    # 2. 计算新租期
    old_lease_end = active_lease.lease_end
    new_lease_start = old_lease_end + relativedelta(days=1)  # 接着旧租约结束的下一天
    new_lease_end = new_lease_start + relativedelta(months=renew_data.months) - relativedelta(days=1)
    
    # 新月租金
    new_monthly_rent = renew_data.monthly_rent if renew_data.monthly_rent else active_lease.monthly_rent
    
    # 3. 创建新租赁记录
    new_lease = LeaseRecord(
        tenant_id=tenant_id,
        room_id=active_lease.room_id,
        lease_start=new_lease_start,
        lease_end=new_lease_end,
        monthly_rent=new_monthly_rent,
        deposit_amount=active_lease.deposit_amount,
        is_active=True,
        notes=renew_data.notes,
        owner_id=current_user.id
    )
    db.add(new_lease)
    
    # 4. 更新房间租期
    room.lease_start = new_lease_start
    room.lease_end = new_lease_end
    room.monthly_rent = new_monthly_rent
    
    # 5. 租客状态改为 active
    tenant.status = 'active'
    
    db.commit()
    db.refresh(new_lease)
    return new_lease


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
