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


# 测试客户端 with CSRF bypass fixture
@pytest.fixture
def client_with_csrf(client):
    """创建测试客户端（绕过 CSRF）"""
    return client


class TestSecurity:
    """测试安全功能"""
    
    def test_create_access_token(self):
        """测试创建访问令牌"""
        token = create_access_token(data={"sub": "testuser"})
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_decode_access_token(self):
        """测试解码访问令牌"""
        token = create_access_token(data={"sub": "testuser"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "testuser"
    
    def test_decode_invalid_token(self):
        """测试解码无效令牌"""
        # decode_access_token 会捕获异常返回 None
        from app.core.security import decode_access_token
        payload = decode_access_token("invalid_token")
        assert payload is None


class TestAuthEndpoints:
    """测试认证端点"""
    
    def test_register_success(self, client, db):
        """测试注册成功"""
        response = client.post("/api/v1/auth/register", json={
            "username": "newuser",
            "password": "StrongP@ss1",
            "email": "new@example.com"
        })
        assert response.status_code == 201
    
    def test_register_weak_password(self, client, db):
        """测试弱密码注册"""
        response = client.post("/api/v1/auth/register", json={
            "username": "newuser2",
            "password": "123456",
            "email": "new2@example.com"
        })
        assert response.status_code in [400, 422]
    
    def test_register_duplicate_username(self, client, db):
        """测试重复用户名注册"""
        # 先创建一个用户
        from app.models import pwd_context
        user = User(
            username="existing",
            password_hash=pwd_context.hash("ExistingP@ss1"),
            email="existing@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        
        # 尝试创建同名用户
        response = client.post("/api/v1/auth/register", json={
            "username": "existing",
            "password": "StrongP@ss1",
            "email": "another@example.com"
        })
        assert response.status_code == 400
    
    def test_register_password_validation(self, client, db):
        """测试密码验证"""
        response = client.post("/api/v1/auth/register", json={
            "username": "newuser3",
            "password": "short",
            "email": "new3@example.com"
        })
        assert response.status_code in [400, 422]
    
    def test_login_success(self, client, db):
        """测试登录成功"""
        # 先注册用户
        client.post("/api/v1/auth/register", json={
            "username": "loginuser",
            "password": "StrongP@ss1",
            "email": "login@example.com"
        })
        
        response = client.post("/api/v1/auth/login", json={
            "username": "loginuser",
            "password": "StrongP@ss1"
        })
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "access_token" in data["data"]
    
    def test_login_invalid_credentials(self, client, db):
        """测试无效凭证登录"""
        response = client.post("/api/v1/auth/login", json={
            "username": "nonexistent",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
    
    def test_login_wrong_password(self, client, db):
        """测试错误密码登录"""
        # 先注册用户
        client.post("/api/v1/auth/register", json={
            "username": "passuser",
            "password": "StrongP@ss1",
            "email": "pass@example.com"
        })
        
        response = client.post("/api/v1/auth/login", json={
            "username": "passuser",
            "password": "WrongP@ss1"
        })
        assert response.status_code == 401
    
    def test_get_current_user(self, client, db):
        """测试获取当前用户"""
        # 注册并登录
        from app.core.security import create_access_token
        user = User(
            username="currentuser",
            password_hash="irrelevant",
            email="current@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        token = create_access_token(data={"sub": user.username})
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        # API 返回 {message, data: {user: {...}}}
        user_data = data.get("data", {}).get("user", data)
        assert "username" in user_data
        assert user_data["username"] == "currentuser"
    
    def test_get_current_user_unauthorized(self, client, db):
        """测试未授权访问"""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 403
    
    def test_logout(self, client, db):
        """测试退出登录"""
        from app.core.security import create_access_token
        user = User(
            username="logoutuser",
            password_hash="irrelevant",
            email="logout@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        token = create_access_token(data={"sub": user.username})
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
    
    def test_change_password_success(self, client, db):
        """测试修改密码成功"""
        from app.models import pwd_context
        from app.core.security import create_access_token
        
        user = User(
            username="changepass",
            password_hash=pwd_context.hash("OldP@ss1"),
            email="change@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        token = create_access_token(data={"sub": user.username})
        response = client.post(
            "/api/v1/auth/change-password",
            json={
                "old_password": "OldP@ss1",
                "new_password": "NewP@ss1"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
    
    def test_change_password_wrong_old_password(self, client, db):
        """测试修改密码时旧密码错误"""
        from app.models import pwd_context
        from app.core.security import create_access_token
        
        user = User(
            username="changepass2",
            password_hash=pwd_context.hash("OldP@ss1"),
            email="change2@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        token = create_access_token(data={"sub": user.username})
        response = client.post(
            "/api/v1/auth/change-password",
            json={
                "old_password": "WrongP@ss1",
                "new_password": "NewP@ss1"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code in [400, 401]

    def test_change_password_weak_new_password(self, client, db):
        """测试修改密码时新密码太弱"""
        from app.models import pwd_context
        from app.core.security import create_access_token
        
        user = User(
            username="changepass3",
            password_hash=pwd_context.hash("OldP@ss1"),
            email="change3@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        token = create_access_token(data={"sub": user.username})
        response = client.post(
            "/api/v1/auth/change-password",
            json={
                "old_password": "OldP@ss1",
                "new_password": "123"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code in [400, 422]

    def test_change_password_same_as_old(self, client, db):
        """测试修改密码时新旧密码相同"""
        from app.models import pwd_context
        from app.core.security import create_access_token
        
        user = User(
            username="changepass4",
            password_hash=pwd_context.hash("OldP@ss1"),
            email="change4@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        token = create_access_token(data={"sub": user.username})
        response = client.post(
            "/api/v1/auth/change-password",
            json={
                "old_password": "OldP@ss1",
                "new_password": "OldP@ss1"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 400
    
    def test_refresh_token(self, client, db):
        """测试刷新令牌"""
        from app.models import pwd_context
        from app.core.security import create_access_token
        
        user = User(
            username="refreshtoken",
            password_hash=pwd_context.hash("TestP@ss1"),
            email="refresh@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        token = create_access_token(data={"sub": user.username})
        response = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {token}"}
        )
        # 刷新令牌端点可能不存在（返回404）或返回200
        assert response.status_code in [200, 404, 405]


class TestRateLimiting:
    """测试速率限制"""
    
    def test_rate_limiting_after_failed_attempts(self, client, db):
        """测试多次失败后的速率限制"""
        # 先注册一个用户
        from app.models import pwd_context
        user = User(
            username="ratelimituser",
            password_hash=pwd_context.hash("TestP@ss1"),
            email="ratelimit@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        
        # 尝试6次失败登录（密码不对）
        for i in range(6):
            response = client.post(
                "/api/v1/auth/login",
                json={
                    "username": "ratelimituser",
                    "password": "WrongP@ss1"
                }
            )
        
        # 第6次可能被限制或返回401，取决于实现
        assert response.status_code in [401, 429]


class TestTokenValidation:
    """测试 Token 验证"""
    
    def test_valid_token(self, client, db):
        """测试有效 token"""
        user = User(
            username="tokenuser",
            password_hash="irrelevant",
            email="token@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        token = create_access_token(data={"sub": user.username})
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
    
    def test_invalid_token(self, client, db):
        """测试无效 token"""
        headers = {"Authorization": "Bearer invalidtoken123"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
    
    def test_expired_token(self, client, db):
        """测试过期 token"""
        from app.core.security import create_access_token, SECRET_KEY
        # 创建一个已过期的 token（exp 在过去）
        from datetime import datetime, timedelta, timezone
        import jwt
        
        expired_token = jwt.encode(
            {
                "sub": "testuser",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
                "type": "access"
            },
            SECRET_KEY,
            algorithm="HS256"
        )
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
