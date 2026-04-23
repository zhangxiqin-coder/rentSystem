"""
用户管理 API 路由
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.deps import get_db, get_current_user
from app.models import User, pwd_context
from app.schemas import UserCreate, UserUpdate, UserResponse, PaginatedResponse, UserRole

router = APIRouter(prefix="/users", tags=["users"])


def check_user_permission(current_user: User, target_user_id: Optional[int] = None):
    """检查用户权限"""
    # 管理员可以操作所有用户
    if current_user.role == "admin":
        return True
    
    # 其他角色只能操作自己
    if target_user_id is not None and current_user.id != target_user_id:
        raise HTTPException(status_code=403, detail="无权操作其他用户")
    
    return True


@router.get("", response_model=PaginatedResponse[UserResponse])
def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户列表
    
    仅管理员可访问
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可查看用户列表")
    
    query = db.query(User)
    
    # 筛选
    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if search:
        query = query.filter(
            (User.username.contains(search)) |
            (User.email.contains(search)) |
            (User.full_name.contains(search))
        )
    
    # 分页
    total = query.count()
    items = query.order_by(User.created_at.desc()).offset((page - 1) * size).limit(size).all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户详情
    
    管理员可查看所有用户，其他用户只能查看自己
    """
    check_user_permission(current_user, user_id)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新用户信息
    
    管理员可修改所有字段，其他用户只能修改自己的基本信息
    """
    check_user_permission(current_user, user_id)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 非管理员不能修改角色和激活状态
    if current_user.role != "admin":
        if user_data.role is not None or user_data.is_active is not None:
            raise HTTPException(status_code=403, detail="无权修改角色或激活状态")
    
    # 更新字段
    update_data = user_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除用户（软删除）
    
    仅管理员可操作，设置 is_active=false
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可删除用户")
    
    # 不允许删除自己
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 软删除
    user.is_active = False
    db.commit()
    
    return None


@router.put("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    role: UserRole,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    修改用户角色
    
    仅管理员可操作
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可修改用户角色")
    
    # 不允许修改自己的角色
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="不能修改自己的角色")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user.role = role
    db.commit()
    db.refresh(user)
    
    return user
