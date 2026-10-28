"""
转租空窗期房间回归测试（2026-10-28 302-1 案例）

场景：老租客退租、新租约未来几天才生效（transfer 时 lease_start > today）。
退房 sync 后房间 status=available、lease_start=None。
- expiring-soon 必须包含该房间，next_payment_date = 新租约起租日
- _has_paid_for_target_cycle（通知口径）必须判"已付"→ 通知不含房租
- 前端 shouldIncludeRent 对 status≠occupied 判 false（不收房租，Node 同构模拟）
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest


@pytest.fixture
def gap_period_env(client, auth_headers, db, test_user):
    """造一个转租空窗期房间：老租约已结束、新租约 7 天后生效、房间 available。"""
    from app.models import Room, Tenant, LeaseRecord

    room = Room(
        room_number="T-GAP-301",
        building="测试楼",
        monthly_rent=Decimal("1180"),
        payment_cycle=1,
        status="available",
        owner_id=test_user.id,
    )
    db.add(room)
    db.flush()

    old_tenant = Tenant(name="老张", phone="13800000001", status="inactive", owner_id=test_user.id)
    new_tenant = Tenant(name="小李", phone="13800000002", status="active", owner_id=test_user.id)
    db.add_all([old_tenant, new_tenant])
    db.flush()

    today = date.today()
    # 老租约：已结束
    db.add(LeaseRecord(
        room_id=room.id, tenant_id=old_tenant.id,
        lease_start=today - timedelta(days=180), lease_end=today - timedelta(days=1),
        monthly_rent=Decimal("1180"), is_active=False, owner_id=test_user.id,
    ))
    # 新租约：未来 7 天生效（转租空窗期）
    db.add(LeaseRecord(
        room_id=room.id, tenant_id=new_tenant.id,
        lease_start=today + timedelta(days=7), lease_end=today + timedelta(days=7 + 180),
        monthly_rent=Decimal("1180"), is_active=True, owner_id=test_user.id,
    ))
    db.commit()
    return {"room_id": room.id, "new_lease_start": today + timedelta(days=7)}


class TestExpiringSoonGapPeriod:
    def test_gap_room_in_expiring_list(self, client, auth_headers, gap_period_env):
        """转租空窗期房间必须出现在即将收租列表，应收日=新租约起租日。"""
        resp = client.get("/api/v1/rooms/expiring-soon?days=14", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        rooms = {r["id"]: r for r in resp.json()}
        assert gap_period_env["room_id"] in rooms, \
            f"转租空窗期房间未出现在列表: {[r['room_number'] for r in rooms.values()]}"
        entry = rooms[gap_period_env["room_id"]]
        assert entry["next_payment_date"] == str(gap_period_env["new_lease_start"])
        assert entry["days_until_payment"] == 7
        assert entry["tenant_name"] == "小李"

    def test_gap_room_outside_window(self, client, auth_headers, gap_period_env):
        """新租约超出查询窗口时不出现（days 窗口语义不变）。"""
        resp = client.get("/api/v1/rooms/expiring-soon?days=3", headers=auth_headers)
        assert resp.status_code == 200
        assert gap_period_env["room_id"] not in {r["id"] for r in resp.json()}

    def test_occupied_room_not_duplicated(self, client, auth_headers, db, test_user):
        """occupied 房间（含生效租约）不因 upcoming 分支重复出现。"""
        from app.models import Room, Tenant, LeaseRecord
        from datetime import date
        today = date.today()
        room = Room(room_number="T-OCC-302", building="测试楼", status="occupied",
                    monthly_rent=Decimal("1000"), payment_cycle=1,
                    lease_start=today - timedelta(days=30), lease_end=today + timedelta(days=300),
                    owner_id=test_user.id)
        db.add(room)
        db.flush()
        t = Tenant(name="在租客", phone="13800000003", status="active", owner_id=test_user.id)
        db.add(t)
        db.flush()
        db.add(LeaseRecord(room_id=room.id, tenant_id=t.id, lease_start=today - timedelta(days=30),
                           lease_end=today + timedelta(days=300), monthly_rent=Decimal("1000"),
                           is_active=True, owner_id=test_user.id))
        db.commit()

        resp = client.get("/api/v1/rooms/expiring-soon?days=30", headers=auth_headers)
        ids = [r["id"] for r in resp.json()]
        assert ids.count(room.id) <= 1, "occupied 房间在列表中出现了两次"


class TestNotificationGapPeriod:
    def test_gap_room_no_rent_in_notification(self, db, gap_period_env):
        """空窗期房间：_has_paid_for_target_cycle 返回 False（已付口径）→ 通知不含房租。"""
        from app.models import Room
        from app.utils.notification_service import _has_paid_for_target_cycle

        room = db.query(Room).get(gap_period_env["room_id"])
        db.refresh(room)
        assert room.status == "available"
        # status≠occupied → 判"已付"（include_rent=False，水电通知只含水电）
        assert _has_paid_for_target_cycle(db, room, cycle=1) is False


class TestRentPaymentStatusGapPeriod:
    """水电页收租状态接口（statistics/rent-payment-status）的空窗期覆盖。"""

    def test_gap_room_in_rent_payment_status(self, client, auth_headers, gap_period_env):
        """转租空窗期房间必须出现在 expiring_rooms，days=距新起租日天数。"""
        resp = client.get(
            "/api/v1/stats/rent-payment-status",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        expiring = {r["room_id"]: r for r in data.get("expiring_rooms", [])}
        assert gap_period_env["room_id"] in expiring, \
            f"空窗期房间未在 expiring_rooms: {data.get('expiring_rooms')}"
        entry = expiring[gap_period_env["room_id"]]
        assert entry["days_until_payment"] == 7
        assert entry["tenant_name"] == "小李"
        # 逾期列表不应包含空窗期房间（还没到起租日，谈不上欠租）
        overdue_ids = {r["room_id"] for r in data.get("overdue_rooms", [])}
        assert gap_period_env["room_id"] not in overdue_ids
