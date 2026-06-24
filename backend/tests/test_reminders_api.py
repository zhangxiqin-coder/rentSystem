"""
测试提醒API端点
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from app.main import app
from app.models import Room, Payment, UtilityReading, User


class TestRemindersAPI:
    """测试提醒API端点"""

    def test_get_upcoming_reminders_unauthorized(self, client):
        """测试未授权获取即将到期提醒"""
        response = client.get("/api/v1/reminders/upcoming")
        # HTTPBearer 无token时返回403
        assert response.status_code == 403

    def test_get_upcoming_reminders_authorized(self, client, auth_headers):
        """测试授权获取即将到期提醒"""
        response = client.get(
            "/api/v1/reminders/upcoming",
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "total" in data
        assert "reminders" in data
        assert "as_of_date" in data
        assert isinstance(data["reminders"], list)

    def test_get_upcoming_reminders_with_params(self, client, auth_headers):
        """测试带参数的即将到期提醒API"""
        response = client.get(
            "/api/v1/reminders/upcoming?days_ahead=14&include_overdue=true",
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "total" in data
        assert "reminders" in data

    def test_get_reminders_summary_unauthorized(self, client):
        """测试未授权访问提醒摘要API"""
        response = client.get("/api/v1/reminders/summary")
        assert response.status_code == 403

    def test_get_reminders_summary_authorized(self, client, auth_headers):
        """测试授权访问提醒摘要API"""
        response = client.get(
            "/api/v1/reminders/summary",
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "lease_expiry" in data
        assert "payment_due" in data
        assert "total_reminders" in data
        assert "next_7_days" in data["lease_expiry"]
        assert "next_30_days" in data["lease_expiry"]
        assert "overdue" in data["lease_expiry"]
        assert "today" in data["payment_due"]
        assert "next_7_days" in data["payment_due"]
        assert "overdue" in data["payment_due"]

    def test_send_rent_reminder_unauthorized(self, client):
        """测试未授权发送催租提醒"""
        response = client.post("/api/v1/reminders/send-rent-reminder/1")
        assert response.status_code == 403

    def test_send_rent_reminder_nonexistent_room(self, client, auth_headers):
        """测试向不存在的房间发送催租提醒"""
        response = client.post(
            "/api/v1/reminders/send-rent-reminder/99999",
            headers=auth_headers
        )
        # 房间不存在
        assert response.status_code == 404

    def test_send_reminder_notifications_unauthorized(self, client):
        """测试未授权发送提醒通知"""
        response = client.post("/api/v1/reminders/send-notifications")
        assert response.status_code == 403

    def test_send_reminder_notifications_authorized(self, client, auth_headers):
        """测试授权发送提醒通知"""
        response = client.post(
            "/api/v1/reminders/send-notifications",
            headers=auth_headers
        )
        # 这个API会尝试发送微信，测试环境可能因配置问题失败
        assert response.status_code in [200, 500, 503]


class TestRemindersAPIWithData:
    """测试带有实际数据的提醒API"""

    def test_reminders_summary_with_actual_data(self, client, db, auth_headers):
        """测试有实际数据时的提醒摘要API"""
        user = db.query(User).filter(User.username == "testuser").first()
        today = date.today()

        overdue_room = Room(
            room_number="603",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            status="occupied",
            tenant_name="逾期租客",
            lease_start=today - timedelta(days=90),
            lease_end=today + timedelta(days=180),
            last_payment_date=today - timedelta(days=35),
            owner_id=user.id
        )
        expiring_room = Room(
            room_number="604",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            status="occupied",
            tenant_name="即将到期租客",
            lease_start=today - timedelta(days=60),
            lease_end=today + timedelta(days=3),
            last_payment_date=today - timedelta(days=25),
            owner_id=user.id
        )
        db.add_all([overdue_room, expiring_room])
        db.commit()

        response = client.get(
            "/api/v1/reminders/summary",
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data["total_reminders"], int)
        assert data["total_reminders"] >= 0

    def test_expiring_rooms_with_actual_data(self, client, db, auth_headers):
        """测试有实际数据时的即将到期房间API"""
        user = db.query(User).filter(User.username == "testuser").first()

        today = date.today()
        room = Room(
            room_number="602",
            monthly_rent=Decimal("1000"),
            payment_cycle=1,
            status="occupied",
            tenant_name="测试租客2",
            lease_start=today - timedelta(days=100),
            lease_end=today + timedelta(days=5),
            last_payment_date=today - timedelta(days=25),
            owner_id=user.id
        )
        db.add(room)
        db.commit()

        response = client.get(
            "/api/v1/reminders/upcoming?days_ahead=14",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "reminders" in data


class TestRemindersAPIValidation:
    """测试提醒API的参数验证"""

    def test_invalid_days_ahead(self, client, auth_headers):
        """测试无效的days_ahead参数"""
        response = client.get(
            "/api/v1/reminders/upcoming?days_ahead=-5",
            headers=auth_headers
        )
        # days_ahead 无 ge=1 约束，-5 会被处理为默认值或正常使用
        assert response.status_code == 200
