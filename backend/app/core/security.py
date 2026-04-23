"""
安全工具函数 - JWT token 生成和验证
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from fastapi import HTTPException, status
import os


# JWT 配置
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 7 * 24 * 60  # 7 days


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT access token
    
    Args:
        data: 要编码到 token 中的数据
        expires_delta: 过期时间增量，默认为 7 天
        
    Returns:
        str: 编码后的 JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow()
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """解码并验证 JWT token
    
    Args:
        token: JWT token 字符串
        
    Returns:
        Dict: 解码后的 token 数据
        
    Raises:
        HTTPException: token 无效或过期时抛出 401 错误
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "detail": "无效的认证凭证",
                "error_code": "AUTH_003",
                "timestamp": datetime.utcnow().isoformat()
            }
        )


def verify_token(token: str) -> Optional[str]:
    """验证 token 并返回用户名
    
    Args:
        token: JWT token 字符串
        
    Returns:
        Optional[str]: 用户名，如果 token 无效则返回 None
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None
