"""房间页退租后租客应进"搬离"tab（2026-09-08 叶大展事故）

事故：房间页 checkout（rooms.py）在检查"租客是否还有其他活跃租约"时，
没有排除本房间自己的租约——而此时本房间租约还没被结束（结束动作在检查
之后），被误判为"其他活跃租约"→ 租客 status 停留 active → 前端归入
"未入住"tab，正确应为"搬离"（inactive）。

对照：租客页退租（lease_records.py end_lease）8月已修，有
`LeaseRecord.id != record.id` 排除自身；房间页漏了同样的排除。

回归覆盖：
1. 房间页退租 → 租客必须置 inactive（掉进搬离tab）
2. 租客在别的房间还有活跃租约 → 不能误伤（保持 active）
3. 租客是别的房间的活跃居住人（同住人）→ 保持 active
4. 韩力场景：退租后新租客入住不受影响（基础回归）
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import LeaseRecord, Room, RoomOccupant, Tenant, User, pwd_context


@pytest.fixture
def checkout_owner(client, db):
    user = User(
        username="checkout_owner_u8",
        email="checkout_owner_u8@test.com",
        password_hash=pwd_context.hash("Test12345"),
        role="landlord",
    )
    db.add(user)
    db.flush()
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "checkout_owner_u8", "password": "Test12345"},
    )
    token = resp.json()["data"]["access_token"]
    return user, {"Authorization": f"Bearer {token}"}


def _make_occupied_room(db, owner, room_number="CO-101", series="CO1", tenant_name="退租租客"):
    """造一个已租房间 + 关联租客 + 当期活跃租约"""
    tenant = Tenant(
        name=tenant_name,
        phone="13800001111",
        owner_id=owner.id,
        status="active",
    )
    db.add(tenant)
    db.flush()
    today = date.today()
    room = Room(
        room_number=room_number,
        series=series,
        monthly_rent=1000,
        status="occupied",
        tenant_name=tenant.name,
        tenant_phone=tenant.phone,
        tenant_id=tenant.id,
        lease_start=today - timedelta(days=30),
        lease_end=today + timedelta(days=335),
        owner_id=owner.id,
    )
    db.add(room)
    db.flush()
    lease = LeaseRecord(
        tenant_id=tenant.id,
        room_id=room.id,
        monthly_rent=Decimal("1000"),
        deposit_amount=Decimal("1000"),
        lease_start=today - timedelta(days=30),
        lease_end=today + timedelta(days=335),
        is_active=True,
        owner_id=owner.id,
    )
    db.add(lease)
    db.commit()
    db.refresh(room)
    db.refresh(tenant)
    db.refresh(lease)
    return room, tenant, lease


def _checkout(client, headers, room_id):
    return client.post(
        f"/api/v1/rooms/{room_id}/checkout",
        json={"refund_amount": 0, "refund_date": str(date.today())},
        headers=headers,
    )


class TestCheckoutTenantStatus:
    def test_checkout_marks_tenant_inactive(self, client, db, checkout_owner):
        """核心场景：房间页退租 → 租客 status 必须变 inactive（搬离tab）"""
        owner, headers = checkout_owner
        room, tenant, lease = _make_occupied_room(db, owner)
        assert tenant.status == "active"

        resp = _checkout(client, headers, room.id)
        assert resp.status_code == 200, resp.text

        db.refresh(tenant)
        db.refresh(lease)
        assert tenant.status == "inactive", (
            "退租后租客应置 inactive 掉进搬离tab（修复前：本房间租约在检查时"
            "还是活跃，被误判为其他活跃租约，跳过置 inactive）"
        )
        assert lease.is_active is False
        assert room.status == "available"

    def test_other_room_active_lease_keeps_active(self, client, db, checkout_owner):
        """租客在另一房间还有活跃租约 → 退租本房间不误伤，保持 active"""
        owner, headers = checkout_owner
        room_a, tenant, lease_a = _make_occupied_room(db, owner, "CO-A", "COA")
        # 另一个房间的活跃租约
        room_b = Room(
            room_number="CO-B",
            series="COB",
            monthly_rent=800,
            status="occupied",
            tenant_name=tenant.name,
            tenant_id=tenant.id,
            lease_start=date.today() - timedelta(days=10),
            lease_end=date.today() + timedelta(days=355),
            owner_id=owner.id,
        )
        db.add(room_b)
        db.flush()
        lease_b = LeaseRecord(
            tenant_id=tenant.id,
            room_id=room_b.id,
            monthly_rent=Decimal("800"),
            deposit_amount=Decimal("800"),
            lease_start=date.today() - timedelta(days=10),
            lease_end=date.today() + timedelta(days=355),
            is_active=True,
            owner_id=owner.id,
        )
        db.add(lease_b)
        db.commit()

        resp = _checkout(client, headers, room_a.id)
        assert resp.status_code == 200

        db.refresh(tenant)
        db.refresh(lease_a)
        db.refresh(lease_b)
        assert tenant.status == "active", "还有别的房间活跃租约，不应置 inactive"
        assert lease_a.is_active is False, "本房间租约应结束"
        assert lease_b.is_active is True, "别的房间租约不能被误伤"

    def test_active_occupant_elsewhere_keeps_active(self, client, db, checkout_owner):
        """租客是另一房间的活跃居住人（同住人）→ 保持 active"""
        owner, headers = checkout_owner
        room_a, tenant, lease_a = _make_occupied_room(db, owner, "CO-A", "COA")
        room_b = Room(
            room_number="CO-B",
            series="COB",
            monthly_rent=800,
            status="occupied",
            owner_id=owner.id,
        )
        db.add(room_b)
        db.flush()
        occ = RoomOccupant(
            room_id=room_b.id,
            tenant_id=tenant.id,
            role="secondary",
            is_active=True,
            owner_id=owner.id,
        )
        db.add(occ)
        db.commit()

        resp = _checkout(client, headers, room_a.id)
        assert resp.status_code == 200

        db.refresh(tenant)
        db.refresh(occ)
        assert tenant.status == "active", "在别的房间还是活跃同住人，不应置 inactive"
        db.refresh(occ)
        assert occ.is_active is True, "别的房间的居住记录不能被误伤"

    def test_new_checkin_after_checkout(self, client, db, checkout_owner):
        """退租后新租客入住 → 新租客 active、房间 occupied（韩力场景）"""
        owner, headers = checkout_owner
        room, tenant, lease = _make_occupied_room(db, owner)

        assert _checkout(client, headers, room.id).status_code == 200
        resp = client.post(
            f"/api/v1/rooms/{room.id}/checkin",
            json={
                "tenant_name": "新租客",
                "tenant_phone": "13900002222",
                "lease_start": str(date.today()),
                "lease_end": str(date.today() + timedelta(days=365)),
                "monthly_rent": 1000,
                "deposit": 1000,
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        db.refresh(room)
        db.refresh(tenant)
        assert room.status == "occupied"
        assert room.tenant_name == "新租客"
        assert tenant.status == "inactive", "老租客保持搬离状态"
