"""
验证数据库模型和表创建
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from app.database import engine, Base, create_tables
from app.models import User, Room, Payment, UtilityReading, UtilityRate
from app.schemas import (
    UserCreate, UserResponse,
    RoomCreate, RoomResponse,
    PaymentCreate, PaymentResponse,
    UtilityReadingCreate, UtilityReadingResponse,
    UtilityRateCreate, UtilityRateResponse
)
from decimal import Decimal
from datetime import date


def test_imports():
    """测试所有导入是否成功"""
    print("测试导入...")
    assert User is not None
    assert Room is not None
    assert Payment is not None
    assert UtilityReading is not None
    assert UtilityRate is not None
    print("✓ 模型导入成功")
    
    assert UserCreate is not None
    assert RoomCreate is not None
    assert PaymentCreate is not None
    assert UtilityReadingCreate is not None
    assert UtilityRateCreate is not None
    print("✓ Schemas 导入成功")


def test_model_creation():
    """测试模型实例化"""
    print("\n测试模型实例化...")
    
    # 测试 User
    user = User(username="testuser", password_hash="hash", email="test@example.com")
    assert user.username == "testuser"
    print("✓ User 模型实例化成功")
    
    # 测试 Room
    room = Room(name="101", monthly_rent=Decimal("1000.00"))
    assert room.name == "101"
    assert hasattr(room, 'payments')
    assert hasattr(room, 'utility_readings')
    print("✓ Room 模型实例化成功")
    
    # 测试 Payment
    payment = Payment(room_id=1, amount=Decimal("1000.00"), payment_date=date.today())
    assert payment.amount == Decimal("1000.00")
    print("✓ Payment 模型实例化成功")
    
    # 测试 UtilityReading
    reading = UtilityReading(room_id=1, utility_type="electric", reading=Decimal("100.50"), reading_date=date.today())
    assert reading.utility_type == "electric"
    print("✓ UtilityReading 模型实例化成功")
    
    # 测试 UtilityRate
    rate = UtilityRate(utility_type="electric", unit_price=Decimal("0.56"), effective_date=date.today())
    assert rate.unit_price == Decimal("0.56")
    print("✓ UtilityRate 模型实例化成功")


def test_schema_validation():
    """测试 Pydantic schema 验证"""
    print("\n测试 Schema 验证...")
    
    # 测试 UserCreate
    user_data = {
        "username": "testuser",
        "password": "password123",
        "email": "test@example.com"
    }
    user_schema = UserCreate(**user_data)
    assert user_schema.username == "testuser"
    print("✓ UserCreate schema 验证成功")
    
    # 测试 RoomCreate
    room_data = {
        "name": "101",
        "monthly_rent": "1000.00",
        "tenant_name": "张三"
    }
    room_schema = RoomCreate(**room_data)
    assert room_schema.name == "101"
    assert room_schema.monthly_rent == Decimal("1000.00")
    print("✓ RoomCreate schema 验证成功")
    
    # 测试 PaymentCreate
    payment_data = {
        "room_id": 1,
        "amount": "1000.00",
        "payment_date": "2024-01-15",
        "payment_method": "支付宝"
    }
    payment_schema = PaymentCreate(**payment_data)
    assert payment_schema.amount == Decimal("1000.00")
    print("✓ PaymentCreate schema 验证成功")
    
    # 测试 UtilityReadingCreate
    reading_data = {
        "room_id": 1,
        "utility_type": "electric",
        "reading": "100.50",
        "reading_date": "2024-01-01"
    }
    reading_schema = UtilityReadingCreate(**reading_data)
    assert reading_schema.utility_type == "electric"
    print("✓ UtilityReadingCreate schema 验证成功")
    
    # 测试 UtilityRateCreate
    rate_data = {
        "utility_type": "electric",
        "unit_price": "0.56",
        "effective_date": "2024-01-01"
    }
    rate_schema = UtilityRateCreate(**rate_data)
    assert rate_schema.unit_price == Decimal("0.56")
    print("✓ UtilityRateCreate schema 验证成功")


def test_create_tables():
    """测试数据库表创建"""
    print("\n测试数据库表创建...")
    
    # 创建所有表
    create_tables()
    print("✓ 数据库表创建成功")
    
    # 验证表是否在数据库中创建
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    expected_tables = ['users', 'rooms', 'payments', 'utility_readings', 'utility_rates']
    for table in expected_tables:
        assert table in tables, f"表 {table} 未创建"
        print(f"  ✓ 表 {table} 已创建")


def test_table_relationships():
    """测试表关系"""
    print("\n测试表关系...")
    
    from sqlalchemy import inspect
    inspector = inspect(engine)
    
    # 检查 rooms 表的外键
    rooms_foreign_keys = inspector.get_foreign_keys('rooms')
    print(f"  ✓ rooms 表外键: {len(rooms_foreign_keys)} 个")
    
    # 检查 payments 表的外键
    payments_foreign_keys = inspector.get_foreign_keys('payments')
    assert len(payments_foreign_keys) > 0, "payments 表应该有外键"
    assert payments_foreign_keys[0]['referred_table'] == 'rooms'
    print("  ✓ payments 表外键指向 rooms 表")
    
    # 检查 utility_readings 表的外键
    readings_foreign_keys = inspector.get_foreign_keys('utility_readings')
    assert len(readings_foreign_keys) > 0, "utility_readings 表应该有外键"
    assert readings_foreign_keys[0]['referred_table'] == 'rooms'
    print("  ✓ utility_readings 表外键指向 rooms 表")


if __name__ == "__main__":
    try:
        print("=" * 60)
        print("开始验证数据库模型和 Schemas")
        print("=" * 60)
        
        test_imports()
        test_model_creation()
        test_schema_validation()
        test_create_tables()
        test_table_relationships()
        
        print("\n" + "=" * 60)
        print("✓ 所有验证测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
