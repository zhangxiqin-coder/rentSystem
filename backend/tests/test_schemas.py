"""
Pydantic Schemas 测试
"""
import pytest
from datetime import date, datetime
from decimal import Decimal
from pydantic import ValidationError

from app.schemas import (
    UserCreate, UserResponse,
    RoomCreate, RoomResponse,
    PaymentCreate, PaymentResponse,
    UtilityReadingCreate, UtilityReadingResponse,
    UtilityRateCreate, UtilityRateResponse
)


class TestUserSchemas:
    """测试 User schemas"""
    
    def test_user_create_valid(self):
        """测试 UserCreate schema"""
        user_data = {
            "username": "testuser",
            "password": "password123",
            "email": "test@example.com"
        }
        user = UserCreate(**user_data)
        assert user.username == "testuser"
        assert user.password == "password123"
        assert user.email == "test@example.com"
    
    def test_user_response_orm_mode(self):
        """测试 UserResponse ORM 模式"""
        # 模拟 ORM 对象
        class MockUser:
            id = 1
            username = "testuser"
            email = "test@example.com"
            created_at = datetime(2024, 1, 1, 12, 0, 0)
        
        mock_user = MockUser()
        user_response = UserResponse.model_validate(mock_user)
        assert user_response.id == 1
        assert user_response.username == "testuser"
        assert user_response.email == "test@example.com"


class TestRoomSchemas:
    """测试 Room schemas"""
    
    def test_room_create_valid(self):
        """测试 RoomCreate schema"""
        room_data = {
            "name": "101",
            "monthly_rent": "1000.00",
            "tenant_name": "张三",
            "tenant_phone": "13800138000",
            "lease_start": "2024-01-01",
            "lease_end": "2024-12-31",
            "payment_cycle": 1
        }
        room = RoomCreate(**room_data)
        assert room.name == "101"
        assert room.monthly_rent == Decimal("1000.00")
        assert room.tenant_name == "张三"
        assert room.payment_cycle == 1
    
    def test_room_response_orm_mode(self):
        """测试 RoomResponse ORM 模式"""
        class MockRoom:
            id = 1
            name = "101"
            monthly_rent = Decimal("1000.00")
            tenant_name = "张三"
            tenant_phone = None
            lease_start = None
            lease_end = None
            payment_cycle = 1
            last_payment_date = None
            created_at = datetime(2024, 1, 1, 12, 0, 0)
        
        mock_room = MockRoom()
        room_response = RoomResponse.model_validate(mock_room)
        assert room_response.id == 1
        assert room_response.name == "101"
        assert room_response.tenant_name == "张三"


class TestPaymentSchemas:
    """测试 Payment schemas"""
    
    def test_payment_create_valid(self):
        """测试 PaymentCreate schema"""
        payment_data = {
            "room_id": 1,
            "amount": "1000.00",
            "payment_date": "2024-01-15",
            "payment_method": "支付宝",
            "note": "1月房租"
        }
        payment = PaymentCreate(**payment_data)
        assert payment.room_id == 1
        assert payment.amount == Decimal("1000.00")
        assert payment.payment_method == "支付宝"
    
    def test_payment_response_orm_mode(self):
        """测试 PaymentResponse ORM 模式"""
        class MockPayment:
            id = 1
            room_id = 1
            amount = Decimal("1000.00")
            payment_date = date(2024, 1, 15)
            payment_method = "支付宝"
            note = "1月房租"
            receipt_image = None
            created_at = datetime(2024, 1, 15, 12, 0, 0)
        
        mock_payment = MockPayment()
        payment_response = PaymentResponse.model_validate(mock_payment)
        assert payment_response.id == 1
        assert payment_response.amount == Decimal("1000.00")


class TestUtilityReadingSchemas:
    """测试 UtilityReading schemas"""
    
    def test_utility_reading_create_valid(self):
        """测试 UtilityReadingCreate schema"""
        reading_data = {
            "room_id": 1,
            "utility_type": "electric",
            "reading": "100.50",
            "reading_date": "2024-01-01",
            "note": "1月电表读数"
        }
        reading = UtilityReadingCreate(**reading_data)
        assert reading.room_id == 1
        assert reading.utility_type == "electric"
        assert reading.reading == Decimal("100.50")
    
    def test_utility_reading_response_orm_mode(self):
        """测试 UtilityReadingResponse ORM 模式"""
        class MockReading:
            id = 1
            room_id = 1
            utility_type = "electric"
            reading = Decimal("100.50")
            reading_date = date(2024, 1, 1)
            note = "1月电表读数"
            created_at = datetime(2024, 1, 1, 12, 0, 0)
        
        mock_reading = MockReading()
        reading_response = UtilityReadingResponse.model_validate(mock_reading)
        assert reading_response.id == 1
        assert reading_response.utility_type == "electric"


class TestUtilityRateSchemas:
    """测试 UtilityRate schemas"""
    
    def test_utility_rate_create_valid(self):
        """测试 UtilityRateCreate schema"""
        rate_data = {
            "utility_type": "electric",
            "unit_price": "0.56",
            "effective_date": "2024-01-01"
        }
        rate = UtilityRateCreate(**rate_data)
        assert rate.utility_type == "electric"
        assert rate.unit_price == Decimal("0.56")
    
    def test_utility_rate_response_orm_mode(self):
        """测试 UtilityRateResponse ORM 模式"""
        class MockRate:
            id = 1
            utility_type = "electric"
            unit_price = Decimal("0.56")
            effective_date = date(2024, 1, 1)
            created_at = datetime(2024, 1, 1, 12, 0, 0)
        
        mock_rate = MockRate()
        rate_response = UtilityRateResponse.model_validate(mock_rate)
        assert rate_response.id == 1
        assert rate_response.utility_type == "electric"
        assert rate_response.unit_price == Decimal("0.56")
