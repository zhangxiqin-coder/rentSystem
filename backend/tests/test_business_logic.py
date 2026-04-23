"""
测试业务逻辑服务
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from app.database import SessionLocal
from app.models import Room, Payment, UtilityReading, UtilityRate, User
from app.service.business import (
    calculate_rent,
    get_previous_reading,
    get_active_rate,
    calculate_utility_cost,
    create_utility_reading,
    create_payment,
    update_room_status,
    get_expiring_leases,
    get_room_statistics,
    get_revenue_statistics
)


class TestBusinessLogic:
    """业务逻辑测试类"""
    
    def test_calculate_rent_monthly(self):
        """测试月租金计算"""
        result = calculate_rent(Decimal("1000"), 1)
        assert result == Decimal("1000")
    
    def test_calculate_rent_quarterly(self):
        """测试季度租金计算"""
        result = calculate_rent(Decimal("1000"), 3)
        assert result == Decimal("3000")
    
    def test_calculate_rent_yearly(self):
        """测试年租金计算"""
        result = calculate_rent(Decimal("1000"), 12)
        assert result == Decimal("12000")
    
    def test_get_previous_reading_none(self, db):
        """测试获取上次读数 - 无记录"""
        result = get_previous_reading(db, 999, "water", date.today())
        assert result is None
    
    def test_get_previous_reading_exists(self, db):
        """测试获取上次读数 - 有记录"""
        room = Room(room_number="101", monthly_rent=Decimal("1000"), payment_cycle=1)
        db.add(room)
        db.commit()
        
        reading1 = UtilityReading(
            room_id=room.id,
            utility_type="water",
            reading=Decimal("100"),
            reading_date=date(2024, 1, 1),
            previous_reading=Decimal("0"),
            usage=Decimal("100"),
            amount=Decimal("500")
        )
        reading2 = UtilityReading(
            room_id=room.id,
            utility_type="water",
            reading=Decimal("150"),
            reading_date=date(2024, 2, 1),
            previous_reading=Decimal("100"),
            usage=Decimal("50"),
            amount=Decimal("250")
        )
        db.add_all([reading1, reading2])
        db.commit()
        
        result = get_previous_reading(db, room.id, "water", date(2024, 3, 1))
        assert result == Decimal("150")
    
    def test_calculate_utility_cost_normal(self):
        """测试水电费计算 - 正常情况"""
        usage, amount = calculate_utility_cost(
            Decimal("150"),
            Decimal("100"),
            Decimal("5.0")
        )
        assert usage == Decimal("50")
        assert amount == Decimal("250")
    
    def test_calculate_utility_cost_invalid(self):
        """测试水电费计算 - 读数减少"""
        with pytest.raises(ValueError, match="当前读数不能小于上次读数"):
            calculate_utility_cost(Decimal("90"), Decimal("100"), Decimal("5.0"))
    
    def test_create_utility_reading_auto_calculate(self, db):
        """测试创建抄表记录 - 自动计算"""
        # 创建房间
        room = Room(room_number="102", monthly_rent=Decimal("1000"), payment_cycle=1)
        db.add(room)
        
        # 创建费率
        rate = UtilityRate(
            utility_type="water",
            rate_per_unit=Decimal("5.0"),
            effective_date=date(2024, 1, 1)
        )
        db.add(rate)
        db.commit()
        
        # 创建首次抄表
        reading1 = create_utility_reading(
            db,
            room_id=room.id,
            utility_type="water",
            reading=Decimal("100"),
            reading_date=date(2024, 1, 15)
        )
        assert reading1.previous_reading == Decimal("0")
        assert reading1.usage == Decimal("100")
        assert reading1.amount == Decimal("500")
        
        # 创建第二次抄表
        reading2 = create_utility_reading(
            db,
            room_id=room.id,
            utility_type="water",
            reading=Decimal("150"),
            reading_date=date(2024, 2, 15)
        )
        assert reading2.previous_reading == Decimal("100")
        assert reading2.usage == Decimal("50")
        assert reading2.amount == Decimal("250")
    
    def test_create_utility_reading_no_rate(self, db):
        """测试创建抄表记录 - 无有效费率"""
        room = Room(room_number="103", monthly_rent=Decimal("1000"), payment_cycle=1)
        db.add(room)
        db.commit()
        
        with pytest.raises(ValueError, match=r"未找到有效的\w+费率"):
            create_utility_reading(
                db,
                room_id=room.id,
                utility_type="water",
                reading=Decimal("100"),
                reading_date=date.today()
            )
    
    def test_create_payment_rent_auto_calculate(self, db):
        """测试创建支付记录 - 租金自动计算"""
        room = Room(
            room_number="104",
            monthly_rent=Decimal("1000"),
            payment_cycle=3
        )
        db.add(room)
        db.commit()
        
        payment = create_payment(
            db,
            room_id=room.id,
            payment_type="rent",
            payment_date=date.today(),
            amount=None  # 自动计算
        )
        
        assert payment.amount == Decimal("3000")
    
    def test_create_payment_with_amount(self, db):
        """测试创建支付记录 - 指定金额"""
        room = Room(room_number="105", monthly_rent=Decimal("1000"), payment_cycle=1)
        db.add(room)
        db.commit()
        
        payment = create_payment(
            db,
            room_id=room.id,
            payment_type="deposit",
            payment_date=date.today(),
            amount=Decimal("2000")
        )
        
        assert payment.amount == Decimal("2000")
    
    def test_update_room_status_to_occupied(self, db):
        """测试房间状态更新 - 变为已租"""
        room = Room(
            room_number="106",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            tenant_name="张三"
        )
        db.add(room)
        db.commit()
        
        update_room_status(room)
        assert room.status == "occupied"
    
    def test_update_room_status_to_available(self, db):
        """测试房间状态更新 - 变为空置"""
        room = Room(
            room_number="107",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            status="occupied"
        )
        db.add(room)
        db.commit()
        
        room.tenant_name = None
        update_room_status(room)
        assert room.status == "available"
    
    def test_get_expiring_leases(self, db):
        """测试获取即将到期租约"""
        today = date.today()
        
        room1 = Room(
            room_number="108",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            tenant_name="张三",
            lease_end=today + timedelta(days=10),
            status="occupied"
        )
        room2 = Room(
            room_number="109",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            tenant_name="李四",
            lease_end=today + timedelta(days=40),
            status="occupied"
        )
        db.add_all([room1, room2])
        db.commit()
        
        expiring = get_expiring_leases(db, days_threshold=30)
        assert len(expiring) == 1
        assert expiring[0]['room_number'] == "108"
        assert expiring[0]['days_remaining'] == 10
    
    def test_get_room_statistics(self, db):
        """测试房间统计"""
        room1 = Room(room_number="110", monthly_rent=Decimal("1000"), payment_cycle=1, status="available")
        room2 = Room(room_number="111", monthly_rent=Decimal("1000"), payment_cycle=1, status="occupied")
        room3 = Room(room_number="112", monthly_rent=Decimal("1000"), payment_cycle=1, status="maintenance")
        db.add_all([room1, room2, room3])
        db.commit()
        
        stats = get_room_statistics(db)
        assert stats['total_rooms'] == 3
        assert stats['available_rooms'] == 1
        assert stats['occupied_rooms'] == 1
        assert stats['maintenance_rooms'] == 1
        assert stats['occupancy_rate'] == 33.33
    
    def test_get_revenue_statistics(self, db):
        """测试收入统计"""
        room = Room(room_number="113", monthly_rent=Decimal("1000"), payment_cycle=1)
        db.add(room)
        db.commit()
        
        payment1 = Payment(
            room_id=room.id,
            amount=Decimal("1000"),
            payment_type="rent",
            payment_date=date.today(),
            status="completed"
        )
        payment2 = Payment(
            room_id=room.id,
            amount=Decimal("500"),
            payment_type="utility",
            payment_date=date.today(),
            status="completed"
        )
        db.add_all([payment1, payment2])
        db.commit()
        
        stats = get_revenue_statistics(db)
        assert stats['total_revenue'] == Decimal("1500")
        assert stats['rent_revenue'] == Decimal("1000")
        assert stats['utility_revenue'] == Decimal("500")
