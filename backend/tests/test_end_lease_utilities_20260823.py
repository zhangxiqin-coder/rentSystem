"""
退租水电结算功能测试（2026-08-23）
覆盖：
1. end-lease 携带水电读数 → 生成 UtilityReading + 已收款 Payment + 回填 payment_id
2. 退租读数写入房间初始读数（下个租客的起点）
3. utility_paid=False → 只生成 UtilityReading，不生成 Payment
4. 不带读数退租（兼容旧行为）→ 无水电记录
5. 读数小于上次读数 → 400 报错
6. final-reading-context 返回上次读数+费率
7. 退租后新租客首次抄表：previous_reading 自动取退租读数（get_previous_reading 按房间查历史）
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from app.models import (
    User, Room, Tenant, LeaseRecord, UtilityReading, UtilityRate, Payment, pwd_context
)


@pytest.fixture
def landlord(db, test_user):
    """复用 conftest 的 test_user 作为房东（auth_headers 就是这个用户）"""
    return test_user


@pytest.fixture
def rates(db):
    """创建水5元/电1元费率"""
    today = date.today()
    water_rate = UtilityRate(
        utility_type="water", rate_per_unit=Decimal("5"),
        effective_date=today - timedelta(days=365), is_active=True
    )
    elec_rate = UtilityRate(
        utility_type="electricity", rate_per_unit=Decimal("1"),
        effective_date=today - timedelta(days=365), is_active=True
    )
    db.add_all([water_rate, elec_rate])
    db.commit()
    return {"water": water_rate, "electricity": elec_rate}


@pytest.fixture
def occupied_room(db, landlord, rates):
    """已出租房间：房间+租客+生效租约+上月水电记录（水100/电1000）"""
    room = Room(
        room_number="T-302-2", monthly_rent=Decimal("1000"),
        status="occupied", owner_id=landlord.id,
        initial_electricity_reading=Decimal("900"),
        initial_water_reading=Decimal("90")
    )
    db.add(room)
    db.flush()

    tenant = Tenant(name="测试租客", phone="13800000001", status="active", owner_id=landlord.id)
    db.add(tenant)
    db.flush()

    lease = LeaseRecord(
        tenant_id=tenant.id, room_id=room.id,
        lease_start=date.today() - timedelta(days=200),
        lease_end=date.today() + timedelta(days=100),
        monthly_rent=Decimal("1000"), is_active=True, owner_id=landlord.id
    )
    db.add(lease)

    # 上月水电记录：水 90→100（10吨），电 900→1000（100度）
    last_month = date.today() - timedelta(days=30)
    db.add(UtilityReading(
        room_id=room.id, utility_type="water", reading=Decimal("100"),
        reading_date=last_month, previous_reading=Decimal("90"),
        usage=Decimal("10"), amount=Decimal("50"), owner_id=landlord.id
    ))
    db.add(UtilityReading(
        room_id=room.id, utility_type="electricity", reading=Decimal("1000"),
        reading_date=last_month, previous_reading=Decimal("900"),
        usage=Decimal("100"), amount=Decimal("100"), owner_id=landlord.id
    ))
    db.commit()
    db.refresh(lease)
    return {"room": room, "tenant": tenant, "lease": lease}


class TestEndLeaseUtilitySettlement:

    def test_end_lease_with_paid_utilities(self, client, auth_headers, db, occupied_room, landlord):
        """退租带水电读数+已收款 → 水电记录+缴费单+初始读数更新"""
        lease = occupied_room["lease"]
        room = occupied_room["room"]

        resp = client.post(
            f"/api/v1/lease-records/{lease.id}/end-lease",
            json={
                "final_water_reading": 120,
                "final_electricity_reading": 1100,
                "utility_paid": True,
                "payment_method": "现金"
            },
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "退租成功" in data["message"]

        # 水费：100→120 = 20吨 × 5 = 100
        assert data["water_utility_id"] is not None
        assert Decimal(str(data["water_amount"])) == Decimal("100")
        assert data["water_payment_id"] is not None

        # 电费：1000→1100 = 100度 × 1 = 100
        assert Decimal(str(data["electricity_amount"])) == Decimal("100")
        assert data["electricity_payment_id"] is not None

        # 校验数据库
        water = db.query(UtilityReading).filter(UtilityReading.id == data["water_utility_id"]).first()
        assert water.previous_reading == Decimal("100")
        assert water.usage == Decimal("20")
        assert water.payment_id == data["water_payment_id"]
        assert "退租结算" in water.notes

        elec = db.query(UtilityReading).filter(UtilityReading.id == data["electricity_utility_id"]).first()
        assert elec.previous_reading == Decimal("1000")
        assert elec.usage == Decimal("100")

        water_pay = db.query(Payment).filter(Payment.id == data["water_payment_id"]).first()
        assert water_pay.payment_type == "utility"
        assert water_pay.amount == Decimal("100")
        assert water_pay.payment_method == "现金"
        assert water_pay.status == "completed"

        # 房间初始读数 = 退租读数（下个租客的起点）
        db.refresh(room)
        assert room.initial_water_reading == Decimal("120")
        assert room.initial_electricity_reading == Decimal("1100")

        # 租约已结束
        db.refresh(lease)
        assert lease.is_active is False

    def test_end_lease_unpaid(self, client, auth_headers, db, occupied_room):
        """utility_paid=False → 只生成水电记录，不生成缴费单"""
        lease = occupied_room["lease"]

        resp = client.post(
            f"/api/v1/lease-records/{lease.id}/end-lease",
            json={
                "final_water_reading": 110,
                "final_electricity_reading": 1050,
                "utility_paid": False
            },
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["water_utility_id"] is not None
        assert data["water_payment_id"] is None  # 未收款
        assert data["electricity_payment_id"] is None

        water = db.query(UtilityReading).filter(UtilityReading.id == data["water_utility_id"]).first()
        assert water.payment_id is None

    def test_end_lease_without_readings_compat(self, client, auth_headers, db, occupied_room):
        """不带读数退租（旧行为兼容）→ 无水电记录"""
        lease = occupied_room["lease"]
        before = db.query(UtilityReading).count()

        resp = client.post(
            f"/api/v1/lease-records/{lease.id}/end-lease",
            json={},
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        assert db.query(UtilityReading).count() == before  # 没有新增

    def test_end_lease_reading_below_previous_rejected(self, client, auth_headers, occupied_room):
        """读数小于上次读数 → 400"""
        lease = occupied_room["lease"]
        resp = client.post(
            f"/api/v1/lease-records/{lease.id}/end-lease",
            json={"final_water_reading": 50},  # 上次100
            headers=auth_headers
        )
        assert resp.status_code == 400
        assert "不能小于" in resp.json()["detail"]

    def test_final_reading_context(self, client, auth_headers, occupied_room):
        """上下文接口返回上次读数+费率"""
        lease = occupied_room["lease"]
        resp = client.get(
            f"/api/v1/lease-records/{lease.id}/final-reading-context",
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert Decimal(str(data["water"]["previous_reading"])) == Decimal("100")
        assert Decimal(str(data["water"]["rate"])) == Decimal("5")
        assert Decimal(str(data["electricity"]["previous_reading"])) == Decimal("1000")
        assert Decimal(str(data["electricity"]["rate"])) == Decimal("1")

    def test_end_lease_marks_tenant_inactive(self, client, auth_headers, db, occupied_room):
        """退租后租客应出现在"搬离"tab（status=inactive）"""
        lease = occupied_room["lease"]
        tenant = occupied_room["tenant"]

        resp = client.post(
            f"/api/v1/lease-records/{lease.id}/end-lease",
            json={},
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text

        db.refresh(tenant)
        assert tenant.status == 'inactive', "退租后租客应为已搬离状态"

        # 搬离tab接口能查到
        resp = client.get("/api/v1/tenants?status=inactive", headers=auth_headers)
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()]
        assert "测试租客" in names

    def test_restore_lease_reactivates_tenant(self, client, auth_headers, db, occupied_room):
        """恢复入住后租客应回到 active（从搬离tab消失）"""
        lease = occupied_room["lease"]
        tenant = occupied_room["tenant"]

        # 先退租
        resp = client.post(
            f"/api/v1/lease-records/{lease.id}/end-lease",
            json={"final_water_reading": 120, "utility_paid": False},
            headers=auth_headers
        )
        assert resp.status_code == 200
        db.refresh(tenant)
        assert tenant.status == 'inactive'

        # 退租后租期日期仍覆盖今天，restore 会拒绝"已是生效状态"→ 改日期后恢复
        lease.lease_start = date.today() - timedelta(days=10)
        lease.lease_end = date.today() - timedelta(days=1)
        db.commit()

        resp = client.post(f"/api/v1/lease-records/{lease.id}/restore", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        db.refresh(tenant)
        assert tenant.status == 'active', "恢复入住后租客应回到active"

    def test_end_lease_keeps_tenant_active_if_other_lease(self, client, auth_headers, db, occupied_room, landlord):
        """租客在别的房间还有活跃租约时，退租本房间不应把他置为搬离"""
        lease = occupied_room["lease"]
        tenant = occupied_room["tenant"]

        # 另一个房间的新租约
        other_room = Room(
            room_number="T-OTHER", monthly_rent=Decimal("800"),
            status="occupied", owner_id=landlord.id
        )
        db.add(other_room)
        db.flush()
        db.add(LeaseRecord(
            tenant_id=tenant.id, room_id=other_room.id,
            lease_start=date.today() - timedelta(days=5),
            lease_end=date.today() + timedelta(days=30),
            monthly_rent=Decimal("800"), is_active=True, owner_id=landlord.id
        ))
        db.commit()

        resp = client.post(
            f"/api/v1/lease-records/{lease.id}/end-lease",
            json={},
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        db.refresh(tenant)
        assert tenant.status == 'active', "还有其他活跃租约的租客不应被置为搬离"

    def test_end_lease_deactivates_room_occupants(self, client, auth_headers, db, occupied_room):
        """退租应清掉本房间所有活跃居住人（主租客+同住人）"""
        from app.models import RoomOccupant
        lease = occupied_room["lease"]
        room = occupied_room["room"]
        tenant = occupied_room["tenant"]

        # 预置主租客+同住人两条活跃居住人记录
        db.add(RoomOccupant(room_id=room.id, tenant_id=tenant.id, role="primary", is_active=True, owner_id=lease.owner_id))
        co = Tenant(name="同住人甲", phone="13800000009", status="active", owner_id=lease.owner_id)
        db.add(co)
        db.flush()
        db.add(RoomOccupant(room_id=room.id, tenant_id=co.id, role="family", is_active=True, owner_id=lease.owner_id))
        db.commit()

        resp = client.post(
            f"/api/v1/lease-records/{lease.id}/end-lease",
            json={},
            headers=auth_headers
        )
        assert resp.status_code == 200, resp.text

        active_occ = db.query(RoomOccupant).filter(
            RoomOccupant.room_id == room.id, RoomOccupant.is_active == True
        ).count()
        assert active_occ == 0, "退租后本房间不应有活跃居住人"

        db.refresh(co)
        assert co.status == 'active', "非签约同住人不应被置inactive（只清居住记录）"

    def test_restore_recovers_occupant_record(self, client, auth_headers, db, occupied_room):
        """restore 恢复租客active + 恢复主租客居住人记录"""
        from app.models import RoomOccupant
        lease = occupied_room["lease"]
        room = occupied_room["room"]
        tenant = occupied_room["tenant"]

        resp = client.post(
            f"/api/v1/lease-records/{lease.id}/end-lease",
            json={},
            headers=auth_headers
        )
        assert resp.status_code == 200

        lease.lease_start = date.today() - timedelta(days=10)
        lease.lease_end = date.today() - timedelta(days=1)
        db.commit()

        resp = client.post(f"/api/v1/lease-records/{lease.id}/restore", headers=auth_headers)
        assert resp.status_code == 200, resp.text

        db.refresh(tenant)
        assert tenant.status == 'active'
        occ = db.query(RoomOccupant).filter(
            RoomOccupant.room_id == room.id, RoomOccupant.tenant_id == tenant.id
        ).first()
        assert occ is not None and occ.is_active, "restore后主租客居住人记录应恢复"

    def test_next_tenant_first_reading_uses_checkout_reading(
        self, client, auth_headers, db, occupied_room, landlord
    ):
        """完整链路：退租读数 → 新租客首次抄表 previous_reading 自动取退租读数"""
        lease = occupied_room["lease"]
        room = occupied_room["room"]

        # 退租：水 100→120
        resp = client.post(
            f"/api/v1/lease-records/{lease.id}/end-lease",
            json={"final_water_reading": 120, "final_electricity_reading": 1100, "utility_paid": True},
            headers=auth_headers
        )
        assert resp.status_code == 200

        # 新租客入住（不录入读数 → 走房间初始读数逻辑不在本API范围，这里直接验证抄表回退）
        # 新租客第一次抄表：水 130
        resp = client.post(
            "/api/v1/utility/readings",
            json={
                "room_id": room.id,
                "utility_type": "water",
                "reading": 130,
                "reading_date": str(date.today() + timedelta(days=1))
            },
            headers=auth_headers
        )
        assert resp.status_code in (200, 201), resp.text
        new_reading = resp.json()
        # previous_reading 应该是退租时的 120（按房间历史取最新）
        assert Decimal(str(new_reading["previous_reading"])) == Decimal("120")
        assert Decimal(str(new_reading["usage"])) == Decimal("10")
        assert Decimal(str(new_reading["amount"])) == Decimal("50")  # 10吨×5元
