"""
认证 API 单元测试
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from app.main import app
from app.database import get_db
from app.models import User
from app.core.security import create_access_token, decode_access_token


# 测试客户端
client = TestClient(app)


# 测试客户端 with CSRF bypass fixture
@pytest.fixture
def client_with_csrf():
    """创建测试客户端（绕过 CSRF）"""
    from fastapi.testclient import TestClient
    from app.main import app
    
    # 创建一个不触发 CSRF 的客户端
    return TestClient(app, headers={"X-CSRF-Token": "test-csrf-token-12345678901234567890"})


# 测试数据库 fixture
@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
        # 清理测试数据
        db.query(User).filter(User.username.like("test%")).delete()
        db.query(User).filter(User.username.like("user%")).delete()
        db.query(User).filter(User.username.like("weak%")).delete()
        db.query(User).filter(User.username.like("new%")).delete()
        db.query(User).filter(User.username.like("ratelimit%")).delete()
        db.query(User).filter(User.username.like("nonexistent")).delete()
        db.commit()
    finally:
        db.close()


# 测试用户 fixture
@pytest.fixture
def test_user(db_session):
    """创建测试用户"""
    # 先检查是否已存在，如果存在则删除
    existing = db_session.query(User).filter(User.username == "testuser").first()
    if existing:
        db_session.delete(existing)
        db_session.commit()
    
    user = User(
        username="testuser",
        email="test@example.com"
    )
    user.set_password("TestPass123")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """创建认证头"""
    token = create_access_token(data={"sub": test_user.username})
    return {"Authorization": f"Bearer {token}"}


class TestSecurity:
    """测试安全工具函数"""
    
    def test_create_access_token(self):
        """测试创建 access token"""
        token = create_access_token(data={"sub": "testuser"})
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_decode_access_token(self):
        """测试解码 access token"""
        token = create_access_token(data={"sub": "testuser"})
        payload = decode_access_token(token)
        assert payload["sub"] == "testuser"
        assert "exp" in payload
        assert "iat" in payload
    
    def test_decode_invalid_token(self):
        """测试解码无效 token"""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token("invalid_token")
        assert exc_info.value.status_code == 401


class TestAuthEndpoints:
    """测试认证端点"""
    
    def test_register_success(self, db_session):
        """测试成功注册"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "NewPass123"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "用户注册成功"
        assert "user" in data["data"]
        assert data["data"]["user"]["username"] == "newuser"
    
    def test_register_weak_password(self):
        """测试弱密码注册"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "weakuser",
                "email": "weak@example.com",
                "password": "weak"
            }
        )
        # Pydantic validation happens first, so we get 422
        assert response.status_code in [400, 422]
        data = response.json()
        # Should have error information
        assert "detail" in data or "detail" in str(data)
    
    def test_register_duplicate_username(self, test_user):
        """测试重复用户名注册"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "another@example.com",
                "password": "TestPass123"
            }
        )
        assert response.status_code == 400
        data = response.json()
        assert "AUTH_001" in data["detail"]["error_code"]
    
    def test_register_password_validation(self):
        """测试密码验证规则"""
        # 测试无大写字母
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "user1",
                "password": "lowercase123"
            }
        )
        assert response.status_code in [400, 422]
        
        # 测试无小写字母
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "user2",
                "password": "UPPERCASE123"
            }
        )
        assert response.status_code in [400, 422]
        
        # 测试无数字
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "user3",
                "password": "NoNumbers"
            }
        )
        assert response.status_code in [400, 422]
        
        # 测试少于8个字符
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "user4",
                "password": "Short1A"
            }
        )
        # Pydantic validation happens first for length, so we get 422
        assert response.status_code in [400, 422]
    
    def test_login_success(self, test_user):
        """测试成功登录"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "testuser",
                "password": "TestPass123"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "登录成功"
        assert "access_token" in data["data"]
        assert data["data"]["token_type"] == "bearer"
    
    def test_login_invalid_credentials(self):
        """测试无效凭据登录"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "nonexistent",
                "password": "WrongPass123"
            }
        )
        assert response.status_code == 401
        data = response.json()
        assert "AUTH_002" in data["detail"]["error_code"]
    
    def test_login_wrong_password(self, test_user):
        """测试错误密码登录"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "testuser",
                "password": "WrongPass123"
            }
        )
        assert response.status_code == 401
        data = response.json()
        assert "AUTH_002" in data["detail"]["error_code"]
    
    def test_get_current_user(self, auth_headers):
        """测试获取当前用户信息"""
        response = client.get(
            "/api/v1/auth/me",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "获取用户信息成功"
        assert data["data"]["user"]["username"] == "testuser"
    
    def test_get_current_user_unauthorized(self):
        """测试未授权获取用户信息"""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 403  # CSRF protection
    
    def test_logout(self, auth_headers):
        """测试登出"""
        response = client.post(
            "/api/v1/auth/logout",
            headers={**auth_headers, "X-CSRF-Token": "test-csrf-token-12345678901234567890"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "登出成功"
    
    def test_change_password_success(self, auth_headers):
        """测试成功修改密码"""
        response = client.post(
            "/api/v1/auth/change-password",
            headers={**auth_headers, "X-CSRF-Token": "test-csrf-token-12345678901234567890"},
            json={
                "old_password": "TestPass123",
                "new_password": "NewPass456"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "密码修改成功"
    
    def test_change_password_wrong_old_password(self, auth_headers):
        """测试修改密码时旧密码错误"""
        response = client.post(
            "/api/v1/auth/change-password",
            headers={**auth_headers, "X-CSRF-Token": "test-csrf-token-12345678901234567890"},
            json={
                "old_password": "WrongPass123",
                "new_password": "NewPass456"
            }
        )
        assert response.status_code == 401
        data = response.json()
        assert "AUTH_007" in data["detail"]["error_code"]
    
    def test_change_password_weak_new_password(self, auth_headers):
        """测试修改密码时新密码过弱"""
        response = client.post(
            "/api/v1/auth/change-password",
            headers={**auth_headers, "X-CSRF-Token": "test-csrf-token-12345678901234567890"},
            json={
                "old_password": "TestPass123",
                "new_password": "weak"
            }
        )
        # Pydantic validation happens first, so we get 422
        assert response.status_code in [400, 422]
    
    def test_change_password_same_as_old(self, auth_headers):
        """测试修改密码时新密码与旧密码相同"""
        response = client.post(
            "/api/v1/auth/change-password",
            headers={**auth_headers, "X-CSRF-Token": "test-csrf-token-12345678901234567890"},
            json={
                "old_password": "TestPass123",
                "new_password": "TestPass123"
            }
        )
        assert response.status_code == 400
        data = response.json()
        assert "AUTH_008" in data["detail"]["error_code"]
    
    def test_refresh_token(self, auth_headers):
        """测试刷新 token"""
        response = client.post(
            "/api/v1/auth/refresh-token",
            headers={**auth_headers, "X-CSRF-Token": "test-csrf-token-12345678901234567890"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Token 刷新成功"
        assert "access_token" in data["data"]
        assert data["data"]["token_type"] == "bearer"


class TestRateLimiting:
    """测试速率限制"""
    
    def test_rate_limiting_after_failed_attempts(self):
        """测试多次失败后的速率限制"""
        # 尝试6次失败登录
        for i in range(6):
            response = client.post(
                "/api/v1/auth/login",
                json={
                    "username": "ratelimituser",
                    "password": "WrongPass123"
                }
            )
        
        # 第6次应该被限制
        assert response.status_code == 429
        data = response.json()
        assert "AUTH_005" in data["detail"]["error_code"]


class TestTokenValidation:
    """测试 Token 验证"""
    
    def test_valid_token(self, test_user):
        """测试有效 token"""
        token = create_access_token(data={"sub": test_user.username})
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
    
    def test_invalid_token(self):
        """测试无效 token"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
    
    def test_expired_token(self):
        """测试过期 token"""
        from app.core.security import SECRET_KEY, ALGORITHM
        from jose import jwt
        
        # 创建一个已过期的 token
        expire = datetime.utcnow() - timedelta(minutes=1)
        payload = {
            "sub": "testuser",
            "exp": expire,
            "iat": datetime.utcnow()
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
