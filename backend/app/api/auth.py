"""
用户认证 API 路由
"""
from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import re
import time
import json

from app.database import get_db
from app.models import User
from app.schemas import (
    UserCreate, UserResponse, LoginRequest, TokenResponse,
    ChangePasswordRequest, MessageResponse
)
from app.core.security import create_access_token, decode_access_token
from app.core.deps import get_current_user


router = APIRouter(prefix="/auth", tags=["认证"])


# Rate limiting 配置
MAX_ATTEMPTS = 5
LOCKOUT_DURATION = 300  # 5 minutes
ATTEMPT_WINDOW = 300  # 5 minutes


# 内存存储（生产环境应使用 Redis）
failed_attempts: Dict[str, Dict[str, Any]] = {}


class RateLimiter:
    """速率限制器 - 防止暴力破解"""
    
    @staticmethod
    def check_rate_limit(identifier: str) -> None:
        """检查是否超过速率限制
        
        Args:
            identifier: 唯一标识符（通常是 IP 或用户名）
            
        Raises:
            HTTPException: 超过速率限制时抛出 429 错误
        """
        now = time.time()
        
        # 清理过期的尝试记录
        if identifier in failed_attempts:
            if now - failed_attempts[identifier]["first_attempt"] > ATTEMPT_WINDOW:
                del failed_attempts[identifier]
                return
        
        # 检查是否在锁定期
        if identifier in failed_attempts:
            attempt_data = failed_attempts[identifier]
            if attempt_data["attempts"] >= MAX_ATTEMPTS:
                lockout_remaining = LOCKOUT_DURATION - (now - attempt_data["last_attempt"])
                if lockout_remaining > 0:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail={
                            "detail": f"尝试次数过多，请在 {int(lockout_remaining)} 秒后重试",
                            "error_code": "AUTH_005",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )
                else:
                    # 锁定期已过，重置计数
                    del failed_attempts[identifier]
    
    @staticmethod
    def record_failed_attempt(identifier: str) -> None:
        """记录失败的登录尝试
        
        Args:
            identifier: 唯一标识符
        """
        now = time.time()
        
        if identifier not in failed_attempts:
            failed_attempts[identifier] = {
                "attempts": 0,
                "first_attempt": now,
                "last_attempt": now
            }
        
        # 如果窗口期已过，重置
        if now - failed_attempts[identifier]["first_attempt"] > ATTEMPT_WINDOW:
            failed_attempts[identifier] = {
                "attempts": 1,
                "first_attempt": now,
                "last_attempt": now
            }
        else:
            failed_attempts[identifier]["attempts"] += 1
            failed_attempts[identifier]["last_attempt"] = now
    
    @staticmethod
    def reset_attempts(identifier: str) -> None:
        """重置尝试记录（登录成功后调用）
        
        Args:
            identifier: 唯一标识符
        """
        if identifier in failed_attempts:
            del failed_attempts[identifier]


def validate_password_strength(password: str) -> None:
    """验证密码强度
    
    Args:
        password: 密码字符串
        
    Raises:
        HTTPException: 密码不符合要求时抛出 400 错误
    """
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": "密码长度至少为 8 个字符",
                "error_code": "AUTH_006",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    if not re.search(r'[A-Z]', password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": "密码必须包含至少一个大写字母",
                "error_code": "AUTH_006",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    if not re.search(r'[a-z]', password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": "密码必须包含至少一个小写字母",
                "error_code": "AUTH_006",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    if not re.search(r'\d', password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": "密码必须包含至少一个数字",
                "error_code": "AUTH_006",
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.post("/register", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """用户注册
    
    Args:
        user_data: 用户创建数据
        db: 数据库会话
        
    Returns:
        Dict: 包含用户信息和消息的响应
    """
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": "用户名已存在",
                "error_code": "AUTH_001",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    # 验证密码强度
    validate_password_strength(user_data.password)
    
    # 创建新用户
    new_user = User(
        username=user_data.username,
        email=user_data.email
    )
    new_user.set_password(user_data.password)
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "message": "用户注册成功",
        "data": {
            "user": {
                "id": new_user.id,
                "username": new_user.username,
                "email": new_user.email,
                "created_at": new_user.created_at.isoformat()
            }
        }
    }


@router.post("/login", response_model=Dict[str, Any])
async def login(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """用户登录
    
    Args:
        login_data: 登录请求数据
        request: FastAPI Request 对象
        db: 数据库会话
        
    Returns:
        Dict: 包含 token 和用户信息的响应
    """
    # 获取客户端 IP
    client_ip = request.client.host if request.client else "unknown"
    
    # 检查速率限制
    RateLimiter.check_rate_limit(client_ip)
    RateLimiter.check_rate_limit(login_data.username)
    
    # 查找用户
    user = db.query(User).filter(User.username == login_data.username).first()
    
    # 验证密码
    if not user or not user.verify_password(login_data.password):
        # 记录失败尝试
        RateLimiter.record_failed_attempt(client_ip)
        RateLimiter.record_failed_attempt(login_data.username)
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "detail": "用户名或密码错误",
                "error_code": "AUTH_002",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    # 登录成功，重置尝试记录
    RateLimiter.reset_attempts(client_ip)
    RateLimiter.reset_attempts(login_data.username)
    
    # 生成 token
    access_token = create_access_token(data={"sub": user.username})
    
    return {
        "message": "登录成功",
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role
            }
        }
    }


@router.get("/me", response_model=Dict[str, Any])
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """获取当前用户信息
    
    Args:
        current_user: 当前用户对象（从依赖注入获取）
        
    Returns:
        Dict: 包含用户信息的响应
    """
    return {
        "message": "获取用户信息成功",
        "data": {
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "email": current_user.email,
                "full_name": current_user.full_name,
                "role": current_user.role,
                "created_at": current_user.created_at.isoformat()
            }
        }
    }


@router.post("/logout", response_model=Dict[str, Any])
async def logout(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """用户登出（客户端应删除 token）
    
    Args:
        current_user: 当前用户对象
        
    Returns:
        Dict: 成功消息
    """
    return {
        "message": "登出成功",
        "data": {}
    }


@router.post("/change-password", response_model=Dict[str, Any])
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """修改密码
    
    Args:
        password_data: 密码修改请求数据
        current_user: 当前用户对象
        db: 数据库会话
        
    Returns:
        Dict: 成功消息
    """
    # 验证旧密码
    if not current_user.verify_password(password_data.old_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "detail": "旧密码错误",
                "error_code": "AUTH_007",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    # 验证新密码强度
    validate_password_strength(password_data.new_password)
    
    # 检查新密码是否与旧密码相同
    if current_user.verify_password(password_data.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": "新密码不能与旧密码相同",
                "error_code": "AUTH_008",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    # 更新密码
    current_user.set_password(password_data.new_password)
    db.commit()
    
    return {
        "message": "密码修改成功",
        "data": {}
    }


@router.post("/refresh-token", response_model=Dict[str, Any])
async def refresh_token(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """刷新 access token
    
    Args:
        current_user: 当前用户对象
        
    Returns:
        Dict: 包含新 token 的响应
    """
    # 生成新的 token
    new_token = create_access_token(data={"sub": current_user.username})
    
    return {
        "message": "Token 刷新成功",
        "data": {
            "access_token": new_token,
            "token_type": "bearer"
        }
    }
