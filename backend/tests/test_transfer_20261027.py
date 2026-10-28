"""
转租功能测试（2026-10-27）
覆盖：
1. 完整转租：老租客水电结算 + 新租客租约 + 首期房租 + 房间换绑，单事务
2. 水电衔接：老租客退租读数 → 新租约初始读数 → 新租客首次抄表回退链路
3. 老租客状态：退租三件套（租约结束/居住人清理/按条件置inactive）
4. 不带水电读数转租（跳过结算）
5. 新租客匹配：同名租客不重复建档，补电话/身份证
6. 首期房租可关闭 / 金额自定义
7. 校验拒绝：已结束租约、日期倒挂、读数过小
8. 房间状态与冗余字段同步（_sync_room_from_leases）
9. 老租客在别的房间还有活跃租约时不置 inactive
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from app.models import (
    User, Room, Tenant, LeaseRecord, UtilityReading, UtilityRate,
    Payment, RoomOccupant
)


@pytest.fixture
def landlord(db, test_user):
    """复用 conftest 的 test_user 作为房东（auth_headers 就是这个用户）"""
    return test_user


@pytest.fixture
def rates(db):
    """创建水5元/电1元费率"""
    today = date.today()
    db.add_all([
        UtilityRate(utility_type="water", rate_per_unit=Decimal("5"),
                    effective_date=today - timedelta(days=365), is_active=True),
        UtilityRate(utility_type="electricity", rate_per_unit=Decimal("1"),
                    effective_date=today - timedelta(days=365), is_active=True),
    ])
    db.commit()


@pytest.fixture
def occupied_room(db, landlord, rates):
    """已出租房间：房间+老租客(+同住人)+生效租约+上月水电记录（水100/电1000）"""
    room = Room(
        room_number="TR-501", monthly_rent=Decimal("1000"), payment_cycle=1,
        status="occupied", owner_id=landlord.id,
        initial_electricity_reading=Decimal("900"),
        initial_water_reading=Decimal("90"),
        deposit_amount=Decimal("500"),
    )
    db.add(room)
    db.flush()

    tenant = Tenant(name="老租客", phone="13800000001", status="active", owner_id=landlord.id)
    db.add(tenant)
    db.flush()

    lease = LeaseRecord(
        tenant_id=tenant.id, room_id=room.id,
        lease_start=date.today() - timedelta(days=200),
        lease_end=date.today() + timedelta(days=100),
        monthly_rent=Decimal("1000"), is_active=True, owner_id=landlord.id
    )
    db.add(lease)
    db.flush()

    # 主租客居住人记录 + 一个同住人
    mate = Tenant(name="老租客同住人", phone="13800000009", status="active", owner_id=landlord.id)
    db.add(mate)
    db.flush()
    db.add_all([
        RoomOccupant(room_id=room.id, tenant_id=tenant.id, role="primary",
                     is_active=True, owner_id=landlord.id),
        RoomOccupant(room_id=room.id, tenant_id=mate.id, role="secondary",
                     relation="朋友", is_active=True, owner_id=landlord.id),
    ])

    # 上月水电记录：水 90→100（10吨），电 900→1000（100度）
    last_month = date.today() - timedelta(days=30)
    db.add_all([
        UtilityReading(room_id=room.id, utility_type="water", reading=Decimal("100"),
                       reading_date=last_month, previous_reading=Decimal("90"),
                       usage=Decimal("10"), amount=Decimal("50"), owner_id=landlord.id),
        UtilityReading(room_id=room.id, utility_type="electricity", reading=Decimal("1000"),
                       reading_date=last_month, previous_reading=Decimal("900"),
                       usage=Decimal("100"), amount=Decimal("100"), owner_id=landlord.id),
    ])
    db.commit()
    db.refresh(lease)
    return {"room": room, "tenant": tenant, "lease": lease, "mate": mate}


def _transfer_payload(**overrides):
    """默认转租请求体"""
    today = date.today()
    payload = {
        "final_water_reading": 120,          # 100→120 = 20吨 × 5 = ¥100
        "final_electricity_reading": 1100,   # 1000→1100 = 100度 × 1 = ¥100
        "utility_paid": True,
        "utility_payment_method": "现金",
        "new_tenant_name": "新租客",
        "new_tenant_phone": "13900000002",
        "lease_start": today.isoformat(),
        "lease_end": (today + timedelta(days=364)).isoformat(),
        "monthly_rent": 1100,
        "deposit_amount": 600,
        "first_payment_made": True,
    }
    payload.update(overrides)
    return payload


class TestTransferFullFlow:

    def test_full_transfer(self, client, auth_headers, db, occupied_room, landlord):
        """完整转租：水电结算+新租客+首期房租+房间换绑，全部单事务落库"""
        lease = occupied_room["lease"]
        room = occupied_room["room"]
        old_tenant = occupied_room["tenant"]

        resp = client.post(
            f"/api/v1/lease-records/{lease.id}/transfer",
            json=_transfer_payload(),
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "转租成功" in data["message"]
        assert data["room_number"] == "TR-501"

        # —— 老租客水电结算 ——
        assert data["water_amount"] is not None
        assert Decimal(str(data["water_amount"])) == Decimal("100")
        assert data["electricity_amount"] is not None
        assert Decimal(str(data["electricity_amount"])) == Decimal("100")
        assert data["water_payment_id"] is not None
        assert data["electricity_payment_id"] is not None

        # —— 老租约结束 ——
        old_lease = db.query(LeaseRecord).filter(LeaseRecord.id == lease.id).first()
        assert old_lease.is_active is False

        # —— 新租客 + 新租约 ——
        new_tenant = db.query(Tenant).filter(Tenant.id == data["new_tenant_id"]).first()
        assert new_tenant.name == "新租客"
        assert new_tenant.phone == "13900000002"
        assert new_tenant.status == "active"
        new_lease = db.query(LeaseRecord).filter(LeaseRecord.id == data["new_lease_id"]).first()
        assert new_lease.is_active is True
        assert new_lease.tenant_id == new_tenant.id
        assert Decimal(str(new_lease.monthly_rent)) == Decimal("1100")
        assert Decimal(str(new_lease.deposit_amount)) == Decimal("600")

        # —— 新租约初始读数 = 老租客退租读数（水电衔接核心）——
        assert Decimal(str(new_lease.initial_water_reading)) == Decimal("120")
        assert Decimal(str(new_lease.initial_electricity_reading)) == Decimal("1100")
        assert Decimal(str(room.initial_water_reading)) == Decimal("120")
        assert Decimal(str(room.initial_electricity_reading)) == Decimal("1100")

        # —— 首期房租 ——
        first = db.query(Payment).filter(Payment.id == data["first_payment_id"]).first()
        assert first is not None
        assert Decimal(str(first.amount)) == Decimal("1100")  # 月租1100×1周期
        assert first.payment_type == "rent"
        assert first.payment_date == date.today()
        # room.last_payment_date 是日期字段
        db.refresh(room)
        assert room.last_payment_date == date.today()

        # —— 房间换绑 ——
        db.refresh(room)
        assert room.status == "occupied"
        assert room.tenant_id == new_tenant.id
        assert room.tenant_name == "新租客"

        # —— 老租客退租三件套 ——
        db.refresh(old_tenant)
        assert old_tenant.status == "inactive"
        occupants = db.query(RoomOccupant).filter(RoomOccupant.room_id == room.id).all()
        assert all(o.is_active is False for o in occupants)  # 含同住人

    def test_utility_chained_to_new_tenant_first_reading(self, client, auth_headers, db, occupied_room):
        """新租客首次抄表：previous_reading 自动取老租客退租读数"""
        lease = occupied_room["lease"]
        resp = client.post(
            f"/api/v1/lease-records/{lease.id}/transfer",
            json=_transfer_payload(),
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text

        # 模拟新租客住一个月后抄表：水 120→130
        reading_resp = client.post(
            "/api/v1/utility/readings",
            json={
                "room_id": occupied_room["room"].id,
                "utility_type": "water",
                "reading": 130,
                "reading_date": (date.today() + timedelta(days=30)).isoformat(),
            },
            headers=auth_headers
        )
        assert reading_resp.status_code in (200, 201), reading_resp.text
        rdata = reading_resp.json()
        r = rdata.get("data", rdata)
        assert Decimal(str(r["previous_reading"])) == Decimal("120")
        assert Decimal(str(r["usage"])) == Decimal("10")

    def test_transfer_without_utility_readings(self, client, auth_headers, db, occupied_room):
        """不带水电读数转租：跳过结算，其余流程正常"""
        lease = occupied_room["lease"]
        resp = client.post(
            f"/api/v1/lease-records/{lease.id}/transfer",
            json=_transfer_payload(
                final_water_reading=None, final_electricity_reading=None
            ),
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["water_amount"] is None
        assert data["electricity_amount"] is None

    def test_transfer_utility_unpaid(self, client, auth_headers, db, occupied_room):
        """utility_paid=False：生成读数记录但无缴费单"""
        lease = occupied_room["lease"]
        resp = client.post(
            f"/api/v1/lease-records/{lease.id}/transfer",
            json=_transfer_payload(utility_paid=False),
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["water_utility_id"] is not None
        assert data["water_payment_id"] is None
        assert data["electricity_utility_id"] is not None
        assert data["electricity_payment_id"] is None


class TestTransferTenantMatching:

    def test_existing_tenant_reused(self, client, auth_headers, db, occupied_room, landlord):
        """同名已有租客不重复建档，补齐电话"""
        existing = Tenant(name="回头客", phone="13800000000", status="inactive",
                          owner_id=landlord.id)
        db.add(existing)
        db.commit()

        resp = client.post(
            f"/api/v1/lease-records/{occupied_room['lease'].id}/transfer",
            json=_transfer_payload(
                new_tenant_name="回头客", new_tenant_phone="13700000003"
            ),
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["new_tenant_id"] == existing.id
        db.refresh(existing)
        assert existing.phone == "13700000003"       # 占位符被真实号码覆盖
        assert existing.status == "inactive"          # 转租不复活历史租客状态字段

    def test_existing_tenant_phone_preserved_when_blank(self, client, auth_headers, db, occupied_room, landlord):
        """电话留空（或仍传占位符）：保留库里已有真实电话，不被覆盖成空/占位符"""
        existing = Tenant(name="老朋友", phone="13911112222", status="inactive",
                          owner_id=landlord.id)
        db.add(existing)
        db.commit()

        # 场景1：完全不传电话
        resp = client.post(
            f"/api/v1/lease-records/{occupied_room['lease'].id}/transfer",
            json=_transfer_payload(new_tenant_name="老朋友", new_tenant_phone=""),
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        db.refresh(existing)
        assert existing.phone == "13911112222"  # 原号保留

    def test_existing_tenant_phone_preserved_with_placeholder(self, client, auth_headers, db, occupied_room, landlord):
        """老前端兼容：仍传占位符 13800000000 也不覆盖真实电话"""
        existing = Tenant(name="老朋友2", phone="13933334444", status="inactive",
                          owner_id=landlord.id)
        db.add(existing)
        db.commit()

        resp = client.post(
            f"/api/v1/lease-records/{occupied_room['lease'].id}/transfer",
            json=_transfer_payload(new_tenant_name="老朋友2", new_tenant_phone="13800000000"),
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        db.refresh(existing)
        assert existing.phone == "13933334444"  # 占位符被识别为"未填"，原号保留

    def test_first_payment_disabled(self, client, auth_headers, db, occupied_room):
        """first_payment_made=False：不生成首期房租"""
        resp = client.post(
            f"/api/v1/lease-records/{occupied_room['lease'].id}/transfer",
            json=_transfer_payload(first_payment_made=False),
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["first_payment_id"] is None
        assert data["first_payment_amount"] is None

    def test_first_payment_custom_amount(self, client, auth_headers, db, occupied_room):
        """首期房租自定义金额（押一付三场景：1100×3）"""
        resp = client.post(
            f"/api/v1/lease-records/{occupied_room['lease'].id}/transfer",
            json=_transfer_payload(
                first_payment_amount=3300, payment_cycle=3
            ),
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert Decimal(str(data["first_payment_amount"])) == Decimal("3300")


class TestTransferValidation:

    def test_transfer_terminated_lease_rejected(self, client, auth_headers, db, occupied_room):
        """已结束租约不能转租"""
        lease = occupied_room["lease"]
        lease.is_active = False
        db.commit()

        resp = client.post(
            f"/api/v1/lease-records/{lease.id}/transfer",
            json=_transfer_payload(),
            headers=auth_headers
        )
        assert resp.status_code == 400
        assert "不能转租" in resp.json()["detail"]

    def test_transfer_bad_dates_rejected(self, client, auth_headers, db, occupied_room):
        """新租约日期倒挂 → 422"""
        today = date.today()
        resp = client.post(
            f"/api/v1/lease-records/{occupied_room['lease'].id}/transfer",
            json=_transfer_payload(
                lease_start=today.isoformat(),
                lease_end=(today - timedelta(days=1)).isoformat()
            ),
            headers=auth_headers
        )
        assert resp.status_code == 422

    def test_transfer_reading_too_small_rejected(self, client, auth_headers, db, occupied_room):
        """退租读数小于上次读数 → 400，事务回滚（老租约不受影响）"""
        lease = occupied_room["lease"]
        resp = client.post(
            f"/api/v1/lease-records/{lease.id}/transfer",
            json=_transfer_payload(final_water_reading=50),
            headers=auth_headers
        )
        assert resp.status_code == 400
        db.refresh(lease)
        assert lease.is_active is True  # 回滚，未误伤

    def test_transfer_not_found(self, client, auth_headers, db):
        """不存在的租约 → 404"""
        resp = client.post(
            "/api/v1/lease-records/999999/transfer",
            json=_transfer_payload(),
            headers=auth_headers
        )
        assert resp.status_code == 404


class TestTransferOldTenantMultiRoom:

    def test_old_tenant_keeps_active_in_other_room(self, client, auth_headers, db, occupied_room, landlord):
        """老租客在别的房间还有活跃租约 → 不置 inactive"""
        other_room = Room(
            room_number="TR-502", monthly_rent=Decimal("800"),
            status="occupied", owner_id=landlord.id
        )
        db.add(other_room)
        db.flush()
        db.add(LeaseRecord(
            tenant_id=occupied_room["tenant"].id, room_id=other_room.id,
            lease_start=date.today() - timedelta(days=30),
            lease_end=date.today() + timedelta(days=300),
            monthly_rent=Decimal("800"), is_active=True, owner_id=landlord.id
        ))
        db.commit()

        resp = client.post(
            f"/api/v1/lease-records/{occupied_room['lease'].id}/transfer",
            json=_transfer_payload(),
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        db.refresh(occupied_room["tenant"])
        assert occupied_room["tenant"].status == "active"  # 别的房间还住着

        # 本房间居住人记录仍被清理
        occupants = db.query(RoomOccupant).filter(
            RoomOccupant.room_id == occupied_room["room"].id
        ).all()
        assert all(o.is_active is False for o in occupants)
