"""
水电费率管理 API 路由
"""
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.core.deps import get_db, get_current_user
from app.models import User, UtilityRate
from app.schemas import (
    UtilityRateCreate, UtilityRateUpdate, UtilityRateResponse, PaginatedResponse
)

router = APIRouter(prefix="/utility/rates", tags=["utility-rates"])


def check_rate_permission(user: User):
    """检查费率权限"""
    if user.role == "tenant":
        raise HTTPException(status_code=403, detail="租客无权操作")
    return True


@router.get("", response_model=PaginatedResponse[UtilityRateResponse])
def list_utility_rates(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    utility_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    sort_by: str = "effective_date",
    order: str = "desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取水电费率列表
    
    支持分页、筛选和排序
    """
    query = db.query(UtilityRate)
    
    # 筛选
    if utility_type:
        query = query.filter(UtilityRate.utility_type == utility_type)
    if is_active is not None:
        query = query.filter(UtilityRate.is_active == is_active)
    
    # 排序 - 使用白名单验证
    ALLOWED_SORT_FIELDS = {
        'effective_date', 'rate_per_unit', 'utility_type', 'is_active', 'created_at'
    }
    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = 'effective_date'
    sort_column = getattr(UtilityRate, sort_by, UtilityRate.effective_date)
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


@router.get("/active")
def get_active_rates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取所有类型的当前有效费率
    """
    utility_types = ['water', 'electricity', 'gas']
    result = {}
    
    for utility_type in utility_types:
        rate = db.query(UtilityRate).filter(
            and_(
                UtilityRate.utility_type == utility_type,
                UtilityRate.effective_date <= date.today(),
                UtilityRate.is_active == True
            )
        ).order_by(desc(UtilityRate.effective_date)).first()
        
        result[utility_type] = rate
    
    return result


@router.get("/{utility_type}/history")
def get_rate_history(
    utility_type: str,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取某类型的水电费率历史
    """
    if utility_type not in ['water', 'electricity', 'gas']:
        raise HTTPException(status_code=400, detail="无效的水电类型")
    
    query = db.query(UtilityRate).filter(UtilityRate.utility_type == utility_type)
    
    total = query.count()
    items = query.order_by(desc(UtilityRate.effective_date)).offset((page - 1) * size).limit(size).all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }


@router.get("/{rate_id}", response_model=UtilityRateResponse)
def get_utility_rate(
    rate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取水电费率详情
    """
    rate = db.query(UtilityRate).filter(UtilityRate.id == rate_id).first()
    if not rate:
        raise HTTPException(status_code=404, detail="费率不存在")
    
    return rate


@router.post("", response_model=UtilityRateResponse, status_code=201)
def create_utility_rate(
    rate_data: UtilityRateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建水电费率
    
    - 同一类型可创建多个（不同生效日期）
    - 支持未来费率预设置
    """
    check_rate_permission(current_user)
    
    # 检查是否已存在相同类型和生效日期的费率
    existing = db.query(UtilityRate).filter(
        and_(
            UtilityRate.utility_type == rate_data.utility_type,
            UtilityRate.effective_date == rate_data.effective_date
        )
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="该类型在此日期的费率已存在")
    
    rate = UtilityRate(**rate_data.model_dump())
    db.add(rate)
    db.commit()
    db.refresh(rate)
    
    return rate


@router.put("/{rate_id}", response_model=UtilityRateResponse)
def update_utility_rate(
    rate_id: int,
    rate_data: UtilityRateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新水电费率
    
    - 可以禁用费率（软删除）
    - 不建议修改已使用的费率
    """
    check_rate_permission(current_user)
    
    rate = db.query(UtilityRate).filter(UtilityRate.id == rate_id).first()
    if not rate:
        raise HTTPException(status_code=404, detail="费率不存在")
    
    # 更新字段
    update_data = rate_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rate, key, value)
    
    db.commit()
    db.refresh(rate)
    
    return rate


@router.delete("/{rate_id}", status_code=204)
def delete_utility_rate(
    rate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除水电费率（软删除）
    
    - 不物理删除，设置 is_active=false
    - 已关联的抄表记录不受影响（因为冗余存储了 rate_used）
    """
    check_rate_permission(current_user)
    
    rate = db.query(UtilityRate).filter(UtilityRate.id == rate_id).first()
    if not rate:
        raise HTTPException(status_code=404, detail="费率不存在")
    
    # 软删除
    rate.is_active = False
    db.commit()
    
    return None
