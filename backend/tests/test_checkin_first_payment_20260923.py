"""
测试入住登记自动创建首期房租收款记录（2026-09-23 功能）

背景：2-2501-C / 502-2 / 302-2 三位租客 8 月入住时已交首月房租但系统无记录，
导致 8 月收租记录缺失、需要手工补。本功能让入住登记自动落一笔 rent 记录。

覆盖两个入住入口：
1. 房间页入住：POST /api/v1/rooms/{id}/checkin
2. 租客页入住：POST /api/v1/lease-records
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from app.models import Room, Tenant, LeaseRecord, Payment


def _create_available_room(db, room_number, payment_cycle=1, owner_id=None):
    room = Room(
        room_number=room_number,
        monthly_rent=Decimal("800.00"),
        deposit_amount=Decimal("800.00"),
        payment_cycle=payment_cycle,
        status="available",
        owner_id=owner_id,
    )
    db.add(room)
    db.commit()
    return room


def _create_tenant(db, owner_id, name="测试租客甲"):
    tenant = Tenant(name=name, phone="13800000001", status="active", owner_id=owner_id)
    db.add(tenant)
    db.commit()
    return tenant


class TestRoomsCheckinFirstPayment:
    """房间页入住：自动创建首期收款"""

    def test_checkin_creates_first_payment_default_amount(self, client, db, auth_headers):
        """默认金额 = 月租 × 付款周期，日期 = 入住日"""
        room = _create_available_room(db, "9901")

        resp = client.post(
            f"/api/v1/rooms/{room.id}/checkin",
            json={
                "tenant_name": "测试租客甲",
                "tenant_phone": "13800000001",
                "lease_start": str(date.today()),
                "lease_end": str(date.today() + timedelta(days=365)),
                "monthly_rent": "800.00",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["first_payment_id"] is not None, "应返回首期收款记录ID"
        assert Decimal(str(body["first_payment_amount"])) == Decimal("800")

        payment = db.query(Payment).filter(Payment.id == body["first_payment_id"]).first()
        assert payment is not None
        assert payment.payment_type == "rent"
        assert payment.amount == Decimal("800.00")
        assert payment.payment_date == date.today()
        assert payment.status == "completed"
        assert payment.description == "房租 9901"

        # 房间 last_payment_date 同步更新 → 下次收租日正确顺延
        db.refresh(room)
        assert room.last_payment_date == date.today()

    def test_checkin_custom_amount(self, client, db, auth_headers):
        """自定义首期金额（如打折/含杂费）"""
        room = _create_available_room(db, "9902")

        resp = client.post(
            f"/api/v1/rooms/{room.id}/checkin",
            json={
                "tenant_name": "测试租客甲",
                "lease_start": str(date.today()),
                "lease_end": str(date.today() + timedelta(days=365)),
                "monthly_rent": "800.00",
                "first_payment_amount": "700.00",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert Decimal(str(resp.json()["first_payment_amount"])) == Decimal("700")

        payment = db.query(Payment).filter(Payment.room_id == room.id).first()
        assert payment.amount == Decimal("700.00")

    def test_checkin_cycle_multiplies_amount(self, client, db, auth_headers):
        """押一付三：付款周期=3 → 首期默认收 3 个月房租"""
        room = _create_available_room(db, "9903", payment_cycle=3)

        resp = client.post(
            f"/api/v1/rooms/{room.id}/checkin",
            json={
                "tenant_name": "测试租客甲",
                "lease_start": str(date.today()),
                "lease_end": str(date.today() + timedelta(days=365)),
                "monthly_rent": "800.00",
                "payment_cycle": 3,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert Decimal(str(resp.json()["first_payment_amount"])) == Decimal("2400")

    def test_checkin_no_payment_when_disabled(self, client, db, auth_headers):
        """first_payment_made=false：不创建收款记录（入住时未交钱）"""
        room = _create_available_room(db, "9904")

        resp = client.post(
            f"/api/v1/rooms/{room.id}/checkin",
            json={
                "tenant_name": "测试租客甲",
                "lease_start": str(date.today()),
                "lease_end": str(date.today() + timedelta(days=365)),
                "monthly_rent": "800.00",
                "first_payment_made": False,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["first_payment_id"] is None

        payments = db.query(Payment).filter(Payment.room_id == room.id).all()
        assert payments == [], "关闭首期收款时不应创建任何 Payment"

        # last_payment_date 不更新 → 到期计算回退 lease_start（首次付款=入住日）
        db.refresh(room)
        assert room.last_payment_date is None

    def test_checkin_idempotent_no_duplicate_payment(self, client, db, auth_headers, test_user):
        """幂等：入住日当天已有 rent 记录时不再重复创建"""
        room = _create_available_room(db, "9905")
        # 预置一条入住日的房租记录（模拟之前手工补过）
        db.add(Payment(
            room_id=room.id,
            amount=Decimal("800.00"),
            payment_type="rent",
            payment_date=date.today(),
            status="completed",
            owner_id=test_user.id,
        ))
        db.commit()

        resp = client.post(
            f"/api/v1/rooms/{room.id}/checkin",
            json={
                "tenant_name": "测试租客甲",
                "lease_start": str(date.today()),
                "lease_end": str(date.today() + timedelta(days=365)),
                "monthly_rent": "800.00",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["first_payment_id"] is None, "已有记录时应跳过"

        count = db.query(Payment).filter(
            Payment.room_id == room.id,
            Payment.payment_type == "rent",
        ).count()
        assert count == 1, "不应重复创建房租记录"


class TestLeaseRecordsCreateFirstPayment:
    """租客页入住（创建租赁记录）：自动创建首期收款"""

    def test_lease_record_create_first_payment(self, client, db, auth_headers, test_user):
        """租客页入住：默认金额=月租金，日期=租约开始日"""
        room = _create_available_room(db, "9906", owner_id=test_user.id)
        tenant = _create_tenant(db, test_user.id)

        resp = client.post(
            "/api/v1/lease-records",
            json={
                "tenant_id": tenant.id,
                "room_id": room.id,
                "lease_start": str(date.today()),
                "lease_end": str(date.today() + timedelta(days=365)),
                "monthly_rent": "1300.00",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text

        payment = db.query(Payment).filter(Payment.room_id == room.id).first()
        assert payment is not None, "租客页入住也应自动创建首期收款"
        assert payment.amount == Decimal("1300.00")
        assert payment.payment_type == "rent"
        assert payment.payment_date == date.today()

    def test_lease_record_create_disable_first_payment(self, client, db, auth_headers, test_user):
        """租客页入住关闭首期收款"""
        room = _create_available_room(db, "9907", owner_id=test_user.id)
        tenant = _create_tenant(db, test_user.id)

        resp = client.post(
            "/api/v1/lease-records",
            json={
                "tenant_id": tenant.id,
                "room_id": room.id,
                "lease_start": str(date.today()),
                "lease_end": str(date.today() + timedelta(days=365)),
                "monthly_rent": "1300.00",
                "first_payment_made": False,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text

        payments = db.query(Payment).filter(Payment.room_id == room.id).all()
        assert payments == []
