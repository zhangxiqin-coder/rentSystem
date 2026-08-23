"""
测试房间页入住同步创建 LeaseRecord（2026-08-22 修复）

背景：刘嘉运 2501-C 入住后租客页无租房记录。
根因：房间页入住（POST /rooms/{id}/checkin）只更新房间字段，不创建 LeaseRecord。
修复：checkin 接口自动创建/关联租客 + 创建 LeaseRecord（幂等：已有生效租约则跳过）。
"""
import pytest
from fastapi.testclient import TestClient
from datetime import date, timedelta
from decimal import Decimal

from app.models import Room, Tenant, LeaseRecord


def _create_available_room(db, room_number="9901"):
    room = Room(
        room_number=room_number,
        monthly_rent=Decimal("800.00"),
        deposit_amount=Decimal("800.00"),
        payment_cycle=1,
        status="available",
    )
    db.add(room)
    db.commit()
    return room


class TestCheckinCreatesLeaseRecord:
    """房间页入住必须落 lease_records，租客页才有租赁历史"""

    def test_checkin_creates_lease_record_for_new_tenant(self, client, db, auth_headers):
        """新租客入住：自动创建租客档案 + 租赁记录"""
        room = _create_available_room(db)

        resp = client.post(
            f"/api/v1/rooms/{room.id}/checkin",
            json={
                "tenant_name": "测试租客甲",
                "tenant_phone": "13800000001",
                "lease_start": str(date.today()),
                "lease_end": str(date.today() + timedelta(days=180)),
                "monthly_rent": "800.00",
                "deposit_amount": "800.00",
                "initial_electricity_reading": "100.5",
                "initial_water_reading": "50.2",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text

        # 租客已创建并关联
        tenant = db.query(Tenant).filter(Tenant.name == "测试租客甲").first()
        assert tenant is not None, "入住后应自动创建租客档案"

        # 租赁记录已创建且字段正确
        lease = db.query(LeaseRecord).filter(LeaseRecord.room_id == room.id).first()
        assert lease is not None, "入住后必须创建 LeaseRecord"
        assert lease.tenant_id == tenant.id
        assert str(lease.lease_start) == str(date.today())
        assert lease.monthly_rent == Decimal("800.00")
        assert lease.initial_electricity_reading == Decimal("100.5")
        assert lease.initial_water_reading == Decimal("50.2")

    def test_checkin_links_existing_tenant_no_duplicate(self, client, db, auth_headers, test_user):
        """已有同名租客：关联而不是重复创建"""
        room = _create_available_room(db, "9902")
        existing = Tenant(
            name="测试租客乙",
            phone="13900000002",
            status="active",
            owner_id=test_user.id,
        )
        db.add(existing)
        db.commit()

        resp = client.post(
            f"/api/v1/rooms/{room.id}/checkin",
            json={
                "tenant_name": "测试租客乙",
                "lease_start": str(date.today()),
                "lease_end": str(date.today() + timedelta(days=180)),
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text

        count = db.query(Tenant).filter(Tenant.name == "测试租客乙").count()
        assert count == 1, "不应重复创建同名租客"

        lease = db.query(LeaseRecord).filter(LeaseRecord.room_id == room.id).first()
        assert lease is not None
        assert lease.tenant_id == existing.id

    def test_checkin_idempotent_existing_lease(self, client, db, auth_headers, test_user):
        """房间已有未到期租约时入住：不重复创建租约"""
        room = _create_available_room(db, "9903")
        tenant = Tenant(name="测试租客丙", phone="13800000003", status="active", owner_id=test_user.id)
        db.add(tenant)
        db.commit()

        # 预置一条未到期租约（房间仍 available，模拟退租后又被恢复等场景）
        db.add(LeaseRecord(
            tenant_id=tenant.id,
            room_id=room.id,
            lease_start=date.today() - timedelta(days=10),
            lease_end=date.today() + timedelta(days=170),
            monthly_rent=Decimal("800.00"),
            is_active=True,
            owner_id=test_user.id,
        ))
        db.commit()

        resp = client.post(
            f"/api/v1/rooms/{room.id}/checkin",
            json={
                "tenant_name": "测试租客丙",
                "lease_start": str(date.today()),
                "lease_end": str(date.today() + timedelta(days=365)),
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text

        active_leases = db.query(LeaseRecord).filter(
            LeaseRecord.room_id == room.id,
            LeaseRecord.lease_end >= date.today(),
        ).all()
        assert len(active_leases) == 1, "已有未到期租约时入住不应重复创建租约"
