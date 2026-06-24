"""
Pytest 配置和 fixtures
"""
import os
os.environ["TESTING"] = "1"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_rent_management.db"
test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# 替换 app.database 的 engine 和 SessionLocal
from app import database as db_module
db_module.engine = test_engine
db_module.SessionLocal = TestingSessionLocal

from app.main import app
from app.database import get_db, Base
from app.models import User, pwd_context


@pytest.fixture(scope="function")
def db():
    """创建测试数据库会话"""
    Base.metadata.create_all(bind=test_engine)
    db_session = TestingSessionLocal()
    try:
        yield db_session
    finally:
        db_session.rollback()
        db_session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db):
    """创建测试客户端"""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db):
    """创建测试用户"""
    user = User(
        username="testuser",
        password_hash=pwd_context.hash("testpass123"),
        email="test@example.com",
        full_name="Test User",
        role="landlord"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_admin(db):
    """创建测试管理员"""
    admin = User(
        username="admin",
        password_hash=pwd_context.hash("admin123"),
        email="admin@example.com",
        full_name="Admin User",
        role="admin"
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@pytest.fixture
def auth_headers(client, test_user):
    """获取测试用户的认证头"""
    from app.core.security import create_access_token
    token = create_access_token(data={"sub": test_user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client, test_admin):
    """获取管理员的认证头"""
    from app.core.security import create_access_token
    token = create_access_token(data={"sub": test_admin.username})
    return {"Authorization": f"Bearer {token}"}
