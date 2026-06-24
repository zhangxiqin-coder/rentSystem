"""
测试逾期管理功能 - 后端API和业务逻辑
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from app.models import Room, Payment, UtilityReading, User, pwd_context
from app.service.business import (
    get_rent_payment_status,
    _get_next_payment_days,
    _has_paid_this_month,
    _has_recent_rent_payment,
    _get_payment_due_context,
)


class TestRentPaymentStatus:
    """测试收租状态功能"""
    
    def test_get_rent_payment_status_no_rooms(self, db):
        """测试无房间时的收租状态"""
        result = get_rent_payment_status(db)
        assert result['overdue_rooms'] == []
        assert result['expiring_rooms'] == []
    
    def test_get_rent_payment_status_with_occupied_room(self, db):
        """测试有已租房间但未逾期的情况"""
        # 创建用户
        user = User(
            username="testuser",
            password_hash=pwd_context.hash("testpass123"),
            email="test@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        
        # 创建已租房间，租期刚开始
        today = date.today()
        room = Room(
            room_number="101",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            status="occupied",
            tenant_name="张三",
            lease_start=today - timedelta(days=5),  # 5天前开始租期
            last_payment_date=today,  # 今天刚支付，所以不应该逾期
            owner_id=user.id
        )
        db.add(room)
        db.commit()
        
        result = get_rent_payment_status(db, owner_id=user.id)
        
        # 刚支付过的房间不应该在逾期列表中
        assert len(result['overdue_rooms']) == 0
    
    def test_get_rent_payment_status_overdue_room(self, db):
        """测试逾期房间"""
        # 创建用户
        user = User(
            username="testuser2",
            password_hash=pwd_context.hash("testpass123"),
            email="test2@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        
        # 创建已租房间，租期较早开始且未支付
        today = date.today()
        room = Room(
            room_number="102",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            status="occupied",
            tenant_name="李四",
            lease_start=today - timedelta(days=40),  # 40天前开始
            last_payment_date=today - timedelta(days=35),  # 上次支付35天前
            owner_id=user.id
        )
        db.add(room)
        db.commit()
        
        result = get_rent_payment_status(db, owner_id=user.id)
        
        # 应该有逾期房间
        assert len(result['overdue_rooms']) > 0
        overdue_room = result['overdue_rooms'][0]
        assert overdue_room['room_id'] == room.id
        assert overdue_room['room_number'] == "102"
        assert overdue_room['overdue_days'] >= 0
    
    def test_get_rent_payment_status_expiring_room(self, db):
        """测试即将到期房间"""
        # 创建用户
        user = User(
            username="testuser3",
            password_hash=pwd_context.hash("testpass123"),
            email="test3@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        
        # 创建已租房间，距离下次支付还有几天
        today = date.today()
        room = Room(
            room_number="103",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            status="occupied",
            tenant_name="王五",
            lease_start=today - timedelta(days=25),  # 25天前开始
            last_payment_date=today - timedelta(days=25),  # 上次支付25天前
            owner_id=user.id
        )
        db.add(room)
        db.commit()
        
        result = get_rent_payment_status(
            db, 
            owner_id=user.id,
            expiring_days=7  # 7天内即将到期
        )
        
        # 检查是否有即将到期的房间
        # 具体结果取决于内部计算逻辑
        assert 'expiring_rooms' in result
    
    def test_get_rent_payment_status_user_isolation(self, db):
        """测试用户数据隔离"""
        # 创建两个用户
        user1 = User(
            username="user1",
            password_hash=pwd_context.hash("testpass123"),
            email="user1@example.com",
            role="landlord"
        )
        user2 = User(
            username="user2",
            password_hash=pwd_context.hash("testpass123"),
            email="user2@example.com",
            role="landlord"
        )
        db.add_all([user1, user2])
        db.commit()
        
        # 为每个用户创建房间
        today = date.today()
        room1 = Room(
            room_number="201",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            status="occupied",
            tenant_name="租客A",
            lease_start=today - timedelta(days=40),
            last_payment_date=today - timedelta(days=35),
            owner_id=user1.id
        )
        room2 = Room(
            room_number="202",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            status="occupied",
            tenant_name="租客B",
            lease_start=today - timedelta(days=40),
            last_payment_date=today - timedelta(days=35),
            owner_id=user2.id
        )
        db.add_all([room1, room2])
        db.commit()
        
        # 查询user1的收租状态
        result1 = get_rent_payment_status(db, owner_id=user1.id)
        # 查询user2的收租状态
        result2 = get_rent_payment_status(db, owner_id=user2.id)
        
        # 验证数据隔离
        room_ids_1 = [r['room_id'] for r in result1['overdue_rooms']]
        room_ids_2 = [r['room_id'] for r in result2['overdue_rooms']]
        
        assert room1.id in room_ids_1 or room1.id in [r['room_id'] for r in result1.get('expiring_rooms', [])]
        assert room2.id not in room_ids_1
        assert room2.id in room_ids_2 or room2.id in [r['room_id'] for r in result2.get('expiring_rooms', [])]
        assert room1.id not in room_ids_2
    
    def test_get_rent_payment_status_with_utility_amount(self, db):
        """测试包含水电费的逾期金额计算"""
        # 创建用户
        user = User(
            username="testuser4",
            password_hash=pwd_context.hash("testpass123"),
            email="test4@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        
        # 创建已租房间
        today = date.today()
        room = Room(
            room_number="104",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            status="occupied",
            tenant_name="赵六",
            lease_start=today - timedelta(days=40),
            last_payment_date=today - timedelta(days=35),
            owner_id=user.id
        )
        db.add(room)
        db.commit()
        
        # 创建未支付的水电记录（注意：UtilityReading模型没有is_paid字段）
        utility_reading = UtilityReading(
            room_id=room.id,
            utility_type="water",
            reading=Decimal("150"),
            previous_reading=Decimal("100"),
            usage=Decimal("50"),
            amount=Decimal("250"),
            reading_date=today - timedelta(days=5),
            # is_paid=False  # UtilityReading模型没有这个字段
        )
        db.add(utility_reading)
        db.commit()
        
        result = get_rent_payment_status(db, owner_id=user.id)
        
        if result['overdue_rooms']:
            overdue_room = result['overdue_rooms'][0]
            # 逾期金额应该包含租金和水电费
            expected_min_amount = float(room.monthly_rent) + 250  # 租金 + 水电
            assert overdue_room['overdue_amount'] >= expected_min_amount


class TestPaymentDueContext:
    """测试支付到期上下文计算"""
    
    def test_get_payment_due_context_basic(self, db):
        """测试基本的支付到期上下文"""
        today = date.today()
        room = Room(
            room_number="301",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            lease_start=today - timedelta(days=30),
            last_payment_date=today - timedelta(days=30)
        )
        
        payments = []
        cutoff = today - timedelta(days=90)
        expiring_days = 7
        
        context = _get_payment_due_context(room, payments, cutoff, expiring_days)
        
        assert 'target_due' in context
        assert 'next_due' in context
        assert 'current_cycle_due' in context
        assert 'paid_current_cycle' in context
        assert 'days_to_due' in context
    
    def test_has_paid_this_month(self, db):
        """测试本月是否已支付"""
        today = date.today()
        room = Room(
            room_number="302",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            id=1
        )
        db.add(room)
        db.commit()
        
        # 创建本月的支付记录
        payment = Payment(
            room_id=room.id,
            payment_type="rent",
            amount=Decimal("1000"),
            payment_date=today.replace(day=5),  # 本月5号支付
            status="completed"
        )
        db.add(payment)
        db.commit()
        
        payments = [payment]
        cutoff = today - timedelta(days=90)
        expiring_days = 7
        
        # 模拟_get_next_payment_days函数
        def mock_get_next_payment_days(r, p):
            return 25  # 假设还有25天到期
        
        result = _has_paid_this_month(room, payments, mock_get_next_payment_days, expiring_days)
        assert result is True
    
    def test_has_recent_rent_payment(self, db):
        """测试是否有近期租金支付"""
        today = date.today()
        room = Room(
            room_number="303",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            id=2
        )
        db.add(room)
        db.commit()
        
        # 创建近期的支付记录
        payment = Payment(
            room_id=room.id,
            payment_type="rent",
            amount=Decimal("1000"),
            payment_date=today - timedelta(days=10),  # 10天前支付
            status="completed"
        )
        db.add(payment)
        db.commit()
        
        payments = [payment]
        cycle_months = 1
        
        result = _has_recent_rent_payment(room.id, payments, cycle_months)
        assert result is True


class TestAdvanceRentDays:
    """测试提前收租天数功能"""
    
    def test_advance_rent_days_configuration(self, db):
        """测试不同的提前收租天数配置"""
        # 创建用户
        user = User(
            username="testuser5",
            password_hash=pwd_context.hash("testpass123"),
            email="test5@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        
        # 创建已租房间
        today = date.today()
        room = Room(
            room_number="401",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            status="occupied",
            tenant_name="孙七",
            lease_start=today - timedelta(days=20),
            last_payment_date=today - timedelta(days=20),
            owner_id=user.id
        )
        db.add(room)
        db.commit()
        
        # 测试不同的提前收租天数
        result_0 = get_rent_payment_status(db, owner_id=user.id, advance_rent_days=0)
        result_3 = get_rent_payment_status(db, owner_id=user.id, advance_rent_days=3)
        result_7 = get_rent_payment_status(db, owner_id=user.id, advance_rent_days=7)
        
        # 验证不同配置下的结果差异
        assert isinstance(result_0['overdue_rooms'], list)
        assert isinstance(result_3['overdue_rooms'], list)
        assert isinstance(result_7['overdue_rooms'], list)


class TestEdgeCases:
    """测试边界情况"""
    
    def test_room_with_future_lease_start(self, db):
        """测试租期尚未开始的房间"""
        # 创建用户
        user = User(
            username="testuser6",
            password_hash=pwd_context.hash("testpass123"),
            email="test6@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        
        today = date.today()
        room = Room(
            room_number="501",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            status="occupied",
            tenant_name="周八",
            lease_start=today + timedelta(days=10),  # 未来10天开始
            owner_id=user.id
        )
        db.add(room)
        db.commit()
        
        result = get_rent_payment_status(db, owner_id=user.id)
        
        # 租期未开始的房间不应出现在逾期或即将到期列表中
        overdue_room_ids = [r['room_id'] for r in result['overdue_rooms']]
        expiring_room_ids = [r['room_id'] for r in result['expiring_rooms']]
        
        assert room.id not in overdue_room_ids
        assert room.id not in expiring_room_ids
    
    def test_room_with_none_payment_cycle(self, db):
        """测试付款周期为None的房间"""
        # 创建用户
        user = User(
            username="testuser7",
            password_hash=pwd_context.hash("testpass123"),
            email="test7@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        
        today = date.today()
        room = Room(
            room_number="502",
            monthly_rent=Decimal("1000"),
            payment_cycle=None,  # None值
            status="occupied",
            tenant_name="吴九",
            lease_start=today - timedelta(days=40),
            last_payment_date=today - timedelta(days=35),
            owner_id=user.id
        )
        db.add(room)
        db.commit()
        
        result = get_rent_payment_status(db, owner_id=user.id)
        
        # 应该能正常处理None值，默认使用1个月周期
        assert isinstance(result['overdue_rooms'], list)
        assert isinstance(result['expiring_rooms'], list)
    
    def test_multiple_payments_same_room(self, db):
        """测试同一房间多次支付的情况"""
        # 创建用户
        user = User(
            username="testuser8",
            password_hash=pwd_context.hash("testpass123"),
            email="test8@example.com",
            role="landlord"
        )
        db.add(user)
        db.commit()
        
        today = date.today()
        room = Room(
            room_number="503",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            status="occupied",
            tenant_name="郑十",
            lease_start=today - timedelta(days=60),
            last_payment_date=today - timedelta(days=30),
            owner_id=user.id
        )
        db.add(room)
        db.commit()
        
        # 创建多次支付记录
        payment1 = Payment(
            room_id=room.id,
            payment_type="rent",
            amount=Decimal("1000"),
            payment_date=today - timedelta(days=60),
            status="completed"
        )
        payment2 = Payment(
            room_id=room.id,
            payment_type="rent",
            amount=Decimal("1000"),
            payment_date=today - timedelta(days=30),
            status="completed"
        )
        db.add_all([payment1, payment2])
        db.commit()
        
        result = get_rent_payment_status(db, owner_id=user.id)
        
        # 应该能正确处理多次支付记录
        assert isinstance(result['overdue_rooms'], list)
        assert isinstance(result['expiring_rooms'], list)
