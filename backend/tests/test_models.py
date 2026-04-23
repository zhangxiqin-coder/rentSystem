"""
数据库模型测试
"""
import pytest
from datetime import date, datetime
from decimal import Decimal

from app.models import User, Room, Payment, UtilityReading, UtilityRate
from app.database import Base, engine, get_db
from sqlalchemy.orm import Session


class TestModels:
    """测试所有数据库模型"""
    
    def test_user_model_creation(self):
        """测试 User 模型创建"""
        user = User(
            username="testuser",
            password_hash="hashed_password",
            email="test@example.com"
        )
        assert user.username == "testuser"
        assert user.password_hash == "hashed_password"
        assert user.email == "test@example.com"
        assert user.id is None  # 未保存前没有 ID
    
    def test_room_model_creation(self):
        """测试 Room 模型创建"""
        room = Room(
            name="101",
            monthly_rent=Decimal("1000.00"),
            tenant_name="张三",
            tenant_phone="13800138000",
            lease_start=date(2024, 1, 1),
            lease_end=date(2024, 12, 31),
            payment_cycle=1
        )
        assert room.name == "101"
        assert room.monthly_rent == Decimal("1000.00")
        assert room.tenant_name == "张三"
        assert room.payment_cycle == 1
        assert room.id is None
    
    def test_payment_model_creation(self):
        """测试 Payment 模型创建"""
        payment = Payment(
            room_id=1,
            amount=Decimal("1000.00"),
            payment_date=date(2024, 1, 15),
            payment_method="支付宝",
            note="1月房租"
        )
        assert payment.room_id == 1
        assert payment.amount == Decimal("1000.00")
        assert payment.payment_method == "支付宝"
        assert payment.note == "1月房租"
    
    def test_utility_reading_model_creation(self):
        """测试 UtilityReading 模型创建"""
        reading = UtilityReading(
            room_id=1,
            utility_type="electric",
            reading=Decimal("100.50"),
            reading_date=date(2024, 1, 1),
            note="1月电表读数"
        )
        assert reading.room_id == 1
        assert reading.utility_type == "electric"
        assert reading.reading == Decimal("100.50")
        assert reading.note == "1月电表读数"
    
    def test_utility_rate_model_creation(self):
        """测试 UtilityRate 模型创建"""
        rate = UtilityRate(
            utility_type="electric",
            unit_price=Decimal("0.56"),
            effective_date=date(2024, 1, 1)
        )
        assert rate.utility_type == "electric"
        assert rate.unit_price == Decimal("0.56")
        assert rate.effective_date == date(2024, 1, 1)
    
    def test_user_repr(self):
        """测试 User __repr__ 方法"""
        user = User(username="testuser", password_hash="hash")
        repr_str = repr(user)
        assert "User" in repr_str
        assert "testuser" in repr_str
    
    def test_room_repr(self):
        """测试 Room __repr__ 方法"""
        room = Room(name="101", monthly_rent=Decimal("1000.00"))
        repr_str = repr(room)
        assert "Room" in repr_str
        assert "101" in repr_str


class TestModelRelationships:
    """测试模型关系"""
    
    def test_room_relationships_exist(self):
        """测试 Room 模型关系属性存在"""
        room = Room(name="101", monthly_rent=Decimal("1000.00"))
        # 检查关系属性存在
        assert hasattr(room, 'payments')
        assert hasattr(room, 'utility_readings')
