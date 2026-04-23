"""
依赖注入函数
"""
from typing import Optional
from datetime import datetime
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.core.security import decode_access_token


# HTTP Bearer token 认证
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """从 JWT token 中获取当前用户
    
    Args:
        credentials: HTTP Bearer credentials
        db: 数据库会话
        
    Returns:
        User: 当前用户对象
        
    Raises:
        HTTPException: token 无效或用户不存在时抛出 401 错误
    """
    token = credentials.credentials
    
    # 解码 token
    payload = decode_access_token(token)
    username: str = payload.get("sub")
    
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "detail": "无效的认证凭证",
                "error_code": "AUTH_003",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    # 从数据库获取用户
    user = db.query(User).filter(User.username == username).first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "detail": "用户不存在",
                "error_code": "AUTH_004",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """获取当前活跃用户（可以扩展为检查用户状态）
    
    Args:
        current_user: 当前用户对象
        
    Returns:
        User: 当前活跃用户对象
    """
    # 这里可以添加用户状态检查（如 is_active 等）
    return current_user
