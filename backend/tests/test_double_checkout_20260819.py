"""
2026-08-19 修复：双重退租状态回退bug
场景：房间页退租 → 租客页仍显示合同有效 → 再点租客退租 → 房间被回写为该租客入住

根因：
1. _sync_room_from_leases 判断生效租约只看日期不看 is_active
2. status_display 只按日期计算，is_active=False 的已终止租约仍显示"已生效"
3. 房间退租(checkout)不结束租约，租约日期未到 → 各处仍视为生效
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import User, Room, Tenant, LeaseRecord


@pytest.fixture
def scenario(db, test_user):
    """标准场景：一个在租房间+生效租约（owner=test_user，与其认证头匹配）"""
    user = test_user

    tenant = Tenant(name="测试双退租", phone="13600136000", id_card="110101199001011299",
                    owner_id=user.id, status="active")
    db.add(tenant)
    db.commit()

    room = Room(room_number="DBL-1", monthly_rent=Decimal("1000"), payment_cycle=1,
                status="occupied", tenant_id=tenant.id, tenant_name=tenant.name,
                lease_start=date.today() - timedelta(days=100),
                lease_end=date.today() + timedelta(days=60),
                owner_id=user.id)
    db.add(room)
    db.commit()

    lease = LeaseRecord(tenant_id=tenant.id, room_id=room.id,
                        lease_start=date.today() - timedelta(days=100),
                        lease_end=date.today() + timedelta(days=60),
                        monthly_rent=Decimal("1000"), is_active=True,
                        owner_id=user.id)
    db.add(lease)
    db.commit()

    db.expire_all()
    return user, tenant, room, lease


class TestDoubleCheckout:
    def test_room_checkout_then_lease_end_no_revert(self, db, client, scenario, auth_headers):
        """房间退租后，租客页再退租，房间不得回写为入住"""
        user, tenant, room, lease = scenario

        # 第一步：房间页退租
        resp = client.post(
            f"/api/v1/rooms/{room.id}/checkout",
            json={"refund_amount": 0, "refund_date": str(date.today()), "payment_method": "现金"},
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text

        db.expire_all()
        room_after = db.query(Room).filter(Room.id == room.id).first()
        assert room_after.status == "available"
        assert room_after.tenant_id is None

        # 第二步：租客页退租（end-lease）——修复前这里会把房间回写成"入住"
        resp2 = client.post(f"/api/v1/lease-records/{lease.id}/end-lease", headers=auth_headers)
        assert resp2.status_code == 200, resp2.text

        db.expire_all()
        room_final = db.query(Room).filter(Room.id == room.id).first()
        lease_final = db.query(LeaseRecord).filter(LeaseRecord.id == lease.id).first()

        # 核心断言：房间保持空置，不回写成该租客入住
        assert room_final.status == "available", \
            f"双重退租后房间被回写为 {room_final.status}（租客 {room_final.tenant_name}）"
        assert room_final.tenant_id is None
        assert lease_final.is_active is False

    def test_terminated_lease_shows_expired(self, db, client, scenario, auth_headers):
        """退租后（is_active=False），租约状态显示 expired 而非 active"""
        user, tenant, room, lease = scenario

        resp = client.post(f"/api/v1/lease-records/{lease.id}/end-lease", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        # 2026-08-23 起端点返回 EndLeaseResponse 包装结构，记录在 lease_record 字段
        assert resp.json()["lease_record"]["status_display"] == "expired", \
            "已终止租约（日期未到但is_active=False）应显示expired"

    def test_sync_room_ignores_terminated_lease(self, db, scenario):
        """_sync_room_from_leases 必须跳过 is_active=False 的租约"""
        from app.api.lease_records import _sync_room_from_leases
        user, tenant, room, lease = scenario

        lease.is_active = False  # 模拟已退租终止
        db.flush()

        _sync_room_from_leases(db, room)
        assert room.status == "available"
        assert room.tenant_id is None

    def test_terminated_tenant_not_in_active_filter(self, db, client, scenario, auth_headers):
        """退租后，租约不应出现在 is_active=true 的API过滤结果中"""
        user, tenant, room, lease = scenario

        client.post(f"/api/v1/lease-records/{lease.id}/end-lease", headers=auth_headers)

        resp = client.get("/api/v1/lease-records?is_active=true", headers=auth_headers)
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert lease.id not in ids, "已终止租约不应出现在is_active=true结果中"
