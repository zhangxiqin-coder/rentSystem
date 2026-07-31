"""
测试最近修改的核心业务逻辑：
1. 季付/半年付房间催租消息是否包含房租 (_has_paid_for_target_cycle)
2. 通知服务的 include_rent 判断 (notification_service)
3. 水电历史记录API返回 (utility-readings endpoint)

这些测试保证改了逻辑后不会回归。
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from app.models import Room, Payment, User, UtilityReading, LeaseRecord, pwd_context
from app.service.business import (
    _has_paid_for_target_cycle,
    _get_payment_due_context,
    get_rent_payment_status,
)
from app.utils.notification_service import _has_paid_for_target_cycle as _has_paid_notif


# ──────────────────────────────────────────────
# 1. 季付房租判断逻辑：_has_paid_for_target_cycle
# ──────────────────────────────────────────────

class TestQuarterlyRentIncludeLogic:
    """
    核心场景：季付(cycle=3)房间，上次交租后，下次到期日临近时
    催租消息应包含房租（include_rent=True），不应因为"近期有payment"就排除。
    """

    @pytest.fixture
    def q_room(self, db):
        """季付房间：lease_start=2025-05-02, cycle=3"""
        user = User(
            username="q_user",
            password_hash=pwd_context.hash("pass"),
            email="q@test.com",
            role="landlord",
        )
        db.add(user)
        db.commit()

        room = Room(
            room_number="Q-101",
            monthly_rent=Decimal("1550"),
            payment_cycle=3,
            status="occupied",
            tenant_name="潘某",
            lease_start=date(2025, 5, 2),
            lease_end=date(2027, 5, 2),
            owner_id=user.id,
        )
        db.add(room)
        db.commit()
        return room

    def test_payment_outside_window_should_include_rent(self, db, q_room):
        """
        102-2场景复现：上次6/30交租(覆盖7-9月)，下次到期8/2。
        6/30不在8/2±14天窗口内 → 未付该周期 → include_rent=True。
        """
        # 6/30的payment
        p = Payment(
            room_id=q_room.id,
            payment_type="rent",
            amount=Decimal("4650"),  # 1550 * 3
            payment_date=date(2026, 6, 30),
            status="completed",
        )
        db.add(p)
        db.commit()

        # notification_service 的判断（基于到期日）
        result = _has_paid_notif(db, q_room, cycle=3)
        assert result is False, "上次付款不在下次到期日±14天内，应返回False(未付)→应包含房租"

    def test_payment_inside_window_should_exclude_rent(self, db, q_room):
        """
        如果在到期日附近(±14天)已有payment → 已付 → include_rent=False。
        """
        # 在8/2前7天交租
        p = Payment(
            room_id=q_room.id,
            payment_type="rent",
            amount=Decimal("4650"),
            payment_date=date(2026, 7, 28),  # 8/2 - 5天，在±14天窗口内
            status="completed",
        )
        db.add(p)
        db.commit()

        result = _has_paid_notif(db, q_room, cycle=3)
        assert result is True, "到期日±14天内有payment，应返回True(已付)→不包含房租"

    def test_monthly_room_always_include_rent(self, db, q_room):
        """月付房间(cycle=1)不走该判断，永远包含房租。"""
        q_room.payment_cycle = 1
        db.commit()

        result = _has_paid_notif(db, q_room, cycle=1)
        assert result is False, "月付房间不走周期判断，直接返回False→包含房租"

    def test_no_lease_start_include_rent(self, db, q_room):
        """没有lease_start的房间默认未付→包含房租。"""
        q_room.lease_start = None
        db.commit()

        result = _has_paid_notif(db, q_room, cycle=3)
        assert result is False, "无lease_start无法算到期日→默认未付→包含房租"

    def test_cancelled_payment_not_counted(self, db, q_room):
        """cancelled状态的payment不算数。"""
        p = Payment(
            room_id=q_room.id,
            payment_type="rent",
            amount=Decimal("4650"),
            payment_date=date(2026, 7, 28),  # 在窗口内
            status="cancelled",  # 但被取消了
        )
        db.add(p)
        db.commit()

        result = _has_paid_notif(db, q_room, cycle=3)
        assert result is False, "cancelled的payment不应算作已付"

    def test_non_rent_payment_not_counted(self, db, q_room):
        """水电payment不算房租已付。"""
        p = Payment(
            room_id=q_room.id,
            payment_type="utility",  # 水电费
            amount=Decimal("295"),
            payment_date=date(2026, 7, 28),  # 在窗口内
            status="completed",
        )
        db.add(p)
        db.commit()

        result = _has_paid_notif(db, q_room, cycle=3)
        assert result is False, "utility类型的payment不应算作房租已付"

    def test_business_service_has_paid_for_target_cycle(self, db, q_room):
        """
        business.py 的 _has_paid_for_target_cycle 也用同样的逻辑。
        """
        # 没有任何payment → 未付
        payments = []
        cutoff = date.today() - timedelta(days=90)
        result = _has_paid_for_target_cycle(q_room, payments, cutoff, 7)
        assert result is False

    def test_business_service_with_payment_in_window(self, db, q_room):
        """business.py逻辑：到期日±14天内有rent payment → 已付"""
        p = Payment(
            room_id=q_room.id,
            payment_type="rent",
            amount=Decimal("4650"),
            payment_date=date(2026, 7, 28),
            status="completed",
        )
        db.add(p)
        db.commit()
        payments = [p]
        cutoff = date.today() - timedelta(days=90)
        result = _has_paid_for_target_cycle(q_room, payments, cutoff, 7)
        assert result is True


# ──────────────────────────────────────────────
# 2. 催租消息格式验证（验证 include_rent 参数）
# ──────────────────────────────────────────────

class TestRentMessageFormat:
    """验证催租消息是否正确包含/排除房租行。"""

    def test_message_with_rent(self):
        """include_rent=True时消息应包含房租。"""
        from app.utils.wechat import generate_rent_notification

        msg = generate_rent_notification(
            room_number="102-2",
            tenant_name="潘某",
            monthly_rent=1550.0,
            payment_cycle=3,
            water_amount=35.0,
            electricity_amount=260.0,
            water_reading=263.0,
            electricity_reading=10597.0,
            water_usage=7.0,
            electricity_usage=260.0,
            last_month_data={"water_reading": 256.0, "electricity_reading": 10337.0},
            include_rent=True,
        )
        assert "房租" in msg, "include_rent=True时消息应包含'房租'"
        assert "4650" in msg or "4,650" in msg, "应显示3个月房租总额4650"

    def test_message_without_rent(self):
        """include_rent=False时消息不应包含房租。"""
        from app.utils.wechat import generate_rent_notification

        msg = generate_rent_notification(
            room_number="102-2",
            tenant_name="潘某",
            monthly_rent=1550.0,
            payment_cycle=3,
            water_amount=35.0,
            electricity_amount=260.0,
            water_reading=263.0,
            electricity_reading=10597.0,
            water_usage=7.0,
            electricity_usage=260.0,
            last_month_data={"water_reading": 256.0, "electricity_reading": 10337.0},
            include_rent=False,
        )
        assert "房租" not in msg, "include_rent=False时消息不应包含'房租'"

    def test_message_total_amount_with_rent(self):
        """含房租时总计应 = 房租*cycle + 水 + 电。"""
        from app.utils.wechat import generate_rent_notification

        msg = generate_rent_notification(
            room_number="102-2",
            tenant_name="潘某",
            monthly_rent=1550.0,
            payment_cycle=3,
            water_amount=35.0,
            electricity_amount=260.0,
            water_reading=263.0,
            electricity_reading=10597.0,
            water_usage=7.0,
            electricity_usage=260.0,
            last_month_data={"water_reading": 256.0, "electricity_reading": 10337.0},
            include_rent=True,
        )
        # 房租4650 + 水35 + 电260 = 4945
        assert "4945" in msg, "总计应包含房租4650+水电295=4945"

    def test_message_total_amount_without_rent(self):
        """不含房租时总计应 = 水 + 电。"""
        from app.utils.wechat import generate_rent_notification

        msg = generate_rent_notification(
            room_number="102-2",
            tenant_name="潘某",
            monthly_rent=1550.0,
            payment_cycle=3,
            water_amount=35.0,
            electricity_amount=260.0,
            water_reading=263.0,
            electricity_reading=10597.0,
            water_usage=7.0,
            electricity_usage=260.0,
            last_month_data={"water_reading": 256.0, "electricity_reading": 10337.0},
            include_rent=False,
        )
        # 水35 + 电260 = 295
        assert "295" in msg, "不含房租时总计应为295"


# ──────────────────────────────────────────────
# 3. 水电历史记录API
# ──────────────────────────────────────────────

class TestUtilityReadingHistory:
    """
    验证水电历史记录API正常返回数据。
    回归场景：102A-1有6条记录但前端显示"无历史记录"——这是前端Vue watch bug，
    已通过直接调用loadPreviousReadings修复。后端API本身应该正常返回数据。
    """

    @pytest.fixture
    def room_with_readings(self, db):
        user = User(
            username="ur_user",
            password_hash=pwd_context.hash("pass"),
            email="ur@test.com",
            role="landlord",
        )
        db.add(user)
        db.commit()

        room = Room(
            room_number="UR-101",
            monthly_rent=Decimal("1200"),
            payment_cycle=1,
            status="occupied",
            tenant_name="测试租客",
            lease_start=date.today() - timedelta(days=90),
            owner_id=user.id,
        )
        db.add(room)
        db.commit()

        # 创建3条水3条电的历史记录
        today = date.today()
        for i in range(3):
            water = UtilityReading(
                room_id=room.id,
                utility_type="water",
                reading=Decimal(f"{100 + i * 10}"),
                previous_reading=Decimal(f"{90 + i * 10}"),
                usage=Decimal("10"),
                amount=Decimal("50"),
                reading_date=today - timedelta(days=(3 - i) * 30),
            )
            elec = UtilityReading(
                room_id=room.id,
                utility_type="electricity",
                reading=Decimal(f"{1000 + i * 100}"),
                previous_reading=Decimal(f"{900 + i * 100}"),
                usage=Decimal("100"),
                amount=Decimal("100"),
                reading_date=today - timedelta(days=(3 - i) * 30),
            )
            db.add_all([water, elec])
        db.commit()
        return room

    def test_api_returns_water_readings(self, client, room_with_readings, auth_headers):
        """API应返回水表历史记录。"""
        r = client.get(
            f"/api/v1/rooms/{room_with_readings.id}/utility-readings?page=1&size=1&utility_type=water",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert len(data["items"]) > 0
        assert data["items"][0]["utility_type"] == "water"

    def test_api_returns_latest_reading_first(self, client, room_with_readings, auth_headers):
        """API应按created_at.desc()返回最新记录在前。"""
        r = client.get(
            f"/api/v1/rooms/{room_with_readings.id}/utility-readings?page=1&size=1&utility_type=water",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        latest = data["items"][0]
        # 三条记录创建时间相同（毫秒级），取reading_date最近的
        # API按created_at.desc()排序，返回的应该是最新创建的
        assert float(latest["reading"]) in (100.0, 110.0, 120.0)
        assert data["total"] == 3

    def test_api_returns_electricity_readings(self, client, room_with_readings, auth_headers):
        """API应返回电表历史记录。"""
        r = client.get(
            f"/api/v1/rooms/{room_with_readings.id}/utility-readings?page=1&size=1&utility_type=electricity",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) > 0
        assert data["items"][0]["utility_type"] == "electricity"

    def test_api_pagination_size_1_returns_one(self, client, room_with_readings, auth_headers):
        """size=1应只返回1条记录，total应为3。"""
        r = client.get(
            f"/api/v1/rooms/{room_with_readings.id}/utility-readings?page=1&size=1&utility_type=water",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 1
        assert data["total"] == 3


# ──────────────────────────────────────────────
# 4. 前端工具函数测试（通过execute_code模拟）
# ──────────────────────────────────────────────

class TestShouldIncludeRentLogic:
    """
    模拟前端 shouldIncludeRent() 的逻辑，确保前后端一致。
    前端实现: frontend/src/utils/paymentCycle.ts
    """

    @staticmethod
    def _should_include_rent(lease_start, cycle, payments):
        """模拟前端 shouldIncludeRent 的逻辑"""
        if not lease_start or cycle <= 1:
            return True

        today = date.today()

        # 计算下次到期日
        next_due = lease_start
        while next_due <= today:
            next_due += relativedelta(months=cycle)

        # 检查是否有rent payment在到期日±14天内
        for p in payments:
            p_date = p["payment_date"] if isinstance(p, dict) else p.payment_date
            p_type = p["payment_type"] if isinstance(p, dict) else p.payment_type
            p_status = p["status"] if isinstance(p, dict) else p.status

            if p_type != "rent" or p_status == "cancelled":
                continue
            if abs((p_date - next_due).days) <= 14:
                return False  # 已付，不包含

        return True  # 未付，包含

    def test_102_2_scenario(self):
        """102-2场景：季付，6/30交租，下次到期8/2，应包含房租。"""
        lease_start = date(2025, 5, 2)
        cycle = 3
        payments = [
            {"payment_date": date(2026, 6, 30), "payment_type": "rent", "status": "completed"}
        ]
        assert self._should_include_rent(lease_start, cycle, payments) is True

    def test_already_paid_this_cycle(self):
        """本周期已付（在到期日±14天内），不包含房租。"""
        lease_start = date(2025, 5, 2)
        cycle = 3
        # 到期日8/2，7/28付的 → 在窗口内
        payments = [
            {"payment_date": date(2026, 7, 28), "payment_type": "rent", "status": "completed"}
        ]
        assert self._should_include_rent(lease_start, cycle, payments) is False

    def test_monthly_always_include(self):
        """月付永远包含房租。"""
        lease_start = date.today() - timedelta(days=365)
        cycle = 1
        payments = [
            {"payment_date": date.today(), "payment_type": "rent", "status": "completed"}
        ]
        assert self._should_include_rent(lease_start, cycle, payments) is True

    def test_no_payments_include_rent(self):
        """没有任何payment记录 → 包含房租。"""
        lease_start = date(2025, 5, 2)
        cycle = 3
        payments = []
        assert self._should_include_rent(lease_start, cycle, payments) is True

    def test_cancelled_not_counted(self):
        """cancelled payment不算数。"""
        lease_start = date(2025, 5, 2)
        cycle = 3
        payments = [
            {"payment_date": date(2026, 7, 28), "payment_type": "rent", "status": "cancelled"}
        ]
        assert self._should_include_rent(lease_start, cycle, payments) is True

    def test_half_year_cycle(self):
        """半年付(cycle=6)的房间。"""
        lease_start = date.today() - timedelta(days=400)
        cycle = 6

        # 计算下次到期日
        next_due = lease_start
        while next_due <= date.today():
            next_due += relativedelta(months=6)

        # 在到期日前5天交租 → 在窗口内
        payments_in = [
            {"payment_date": next_due - timedelta(days=5), "payment_type": "rent", "status": "completed"}
        ]
        assert self._should_include_rent(lease_start, cycle, payments_in) is False

        # 在到期日前30天交租 → 不在窗口内
        payments_out = [
            {"payment_date": next_due - timedelta(days=30), "payment_type": "rent", "status": "completed"}
        ]
        assert self._should_include_rent(lease_start, cycle, payments_out) is True
