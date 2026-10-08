"""水电收益账期归月规则测试（2026-10-03）

背景：抄表/收款日不固定（有时31号收、有时1号收），同一期账可能落在
两个日历月，导致月度收益跟供电局账单对不上；且同房间同月多次收款
会被累计，收益虚增。

规则（用户裁决）：
1. 每月1-5号收的水电费 → 算上个月账期（供电局按自然月出账）
2. 每个系列每个房间每类型每账期 → 只统计最近一次收款

覆盖端点：
- GET /api/v1/utility-bills/profit
- GET /api/v1/utility-bills/series/{series}/detail
- GET /api/v1/utility-bills/{bill_id}
"""
import pytest
from datetime import date
from decimal import Decimal

from app.models import (
    User, Room, Payment, UtilityReading, UtilityBill, pwd_context,
)


@pytest.fixture
def owner(client, db):
    """建一个有房间的用户并登录，返回 (headers, series)"""
    user = User(
        username="profit_owner_1003",
        email="profit_owner_1003@test.com",
        password_hash=pwd_context.hash("Test12345"),
        role="landlord",
    )
    db.add(user)
    db.flush()
    for num in ("P-101", "P-102"):
        db.add(Room(room_number=num, series="PS1", monthly_rent=1000, owner_id=user.id))
    db.commit()
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "profit_owner_1003", "password": "Test12345"},
    )
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}, "PS1"


def _mk_payment(db, room_id, amount, payment_date, description, owner_id):
    p = Payment(
        room_id=room_id,
        amount=Decimal(str(amount)),
        payment_type="utility",
        payment_date=payment_date,
        description=description,
        owner_id=owner_id,
    )
    db.add(p)
    db.flush()
    return p


def _mk_reading(db, room_id, utype, reading_date, amount, payment_id, owner_id):
    r = UtilityReading(
        room_id=room_id,
        utility_type=utype,
        reading=1000,
        previous_reading=900,
        usage=100,
        amount=Decimal(str(amount)),
        reading_date=reading_date,
        payment_id=payment_id,
        owner_id=owner_id,
    )
    db.add(r)
    db.flush()
    return r


def _get_month(rows, series, year, month):
    for r in rows:
        if r["series"] == series and r["year"] == year and r["month"] == month:
            return r
    return None


class TestBillPeriodRule:
    """规则1：1-5号收的算上个月"""

    def test_payment_on_1st_counts_as_previous_month(self, client, db, owner):
        headers, series = owner
        user = db.query(User).filter_by(username="profit_owner_1003").one()
        room = db.query(Room).filter_by(room_number="P-101").one()

        # 8月31号抄表收款100，9月1号又收了一笔属于同一期的钱
        _mk_payment(db, room.id, 100, date(2026, 8, 31), "电费 P-101", user.id)
        # 9月1号收的 → 归8月账期，但同账期只取最新一次 → 只算150
        _mk_payment(db, room.id, 150, date(2026, 9, 1), "电费 P-101", user.id)
        db.commit()

        resp = client.get("/api/v1/utility-bills/profit", headers=headers)
        assert resp.status_code == 200, resp.text
        rows = resp.json()["monthly_breakdown"]

        # 8月电费收 = 150（两笔都归8月，取最新9/1那笔）
        aug = _get_month(rows, series, 2026, 8)
        assert aug is not None
        assert aug["electric_collected"] == 150.0

    def test_payment_on_5th_boundary(self, client, db, owner):
        """5号是边界：仍算上个月"""
        headers, series = owner
        user = db.query(User).filter_by(username="profit_owner_1003").one()
        room = db.query(Room).filter_by(room_number="P-101").one()

        _mk_payment(db, room.id, 60, date(2026, 9, 5), "水费 P-101", user.id)
        db.commit()

        resp = client.get("/api/v1/utility-bills/profit", headers=headers)
        rows = resp.json()["monthly_breakdown"]
        aug = _get_month(rows, series, 2026, 8)
        assert aug is not None
        assert aug["water_collected"] == 60.0

    def test_payment_on_6th_counts_as_current_month(self, client, db, owner):
        """6号开始算当月"""
        headers, series = owner
        user = db.query(User).filter_by(username="profit_owner_1003").one()
        room = db.query(Room).filter_by(room_number="P-101").one()

        _mk_payment(db, room.id, 70, date(2026, 9, 6), "水费 P-101", user.id)
        db.commit()

        resp = client.get("/api/v1/utility-bills/profit", headers=headers)
        rows = resp.json()["monthly_breakdown"]
        assert _get_month(rows, series, 2026, 8) is None
        sep = _get_month(rows, series, 2026, 9)
        assert sep is not None
        assert sep["water_collected"] == 70.0

    def test_january_early_payment_rolls_to_december(self, client, db, owner):
        """1月1-5号收款 → 归上一年12月（跨年）"""
        headers, series = owner
        user = db.query(User).filter_by(username="profit_owner_1003").one()
        room = db.query(Room).filter_by(room_number="P-101").one()

        _mk_payment(db, room.id, 80, date(2026, 1, 3), "水费 P-101", user.id)
        db.commit()

        resp = client.get("/api/v1/utility-bills/profit", headers=headers)
        rows = resp.json()["monthly_breakdown"]
        dec = _get_month(rows, series, 2025, 12)
        assert dec is not None
        assert dec["water_collected"] == 80.0


class TestLatestOnlyRule:
    """规则2：每房间每类型每账期只算最近一次收款"""

    def test_multiple_payments_same_period_keeps_latest(self, client, db, owner):
        headers, series = owner
        user = db.query(User).filter_by(username="profit_owner_1003").one()
        room = db.query(Room).filter_by(room_number="P-101").one()

        # 同一账期收了3次（8/20、9/2、9/4）→ 只算最新的9/4那笔150
        _mk_payment(db, room.id, 100, date(2026, 8, 20), "电费 P-101", user.id)
        _mk_payment(db, room.id, 120, date(2026, 9, 2), "电费 P-101", user.id)
        _mk_payment(db, room.id, 150, date(2026, 9, 4), "电费 P-101", user.id)
        db.commit()

        resp = client.get("/api/v1/utility-bills/profit", headers=headers)
        rows = resp.json()["monthly_breakdown"]
        aug = _get_month(rows, series, 2026, 8)
        assert aug is not None
        # 8/20（100）和 9/2、9/4（120、150）都归8月账期，取最新150
        assert aug["electric_collected"] == 150.0

    def test_different_rooms_are_independent(self, client, db, owner):
        """不同房间各自取最新，互不影响"""
        headers, series = owner
        user = db.query(User).filter_by(username="profit_owner_1003").one()
        r1 = db.query(Room).filter_by(room_number="P-101").one()
        r2 = db.query(Room).filter_by(room_number="P-102").one()

        _mk_payment(db, r1.id, 100, date(2026, 8, 20), "电费 P-101", user.id)
        _mk_payment(db, r2.id, 200, date(2026, 8, 25), "电费 P-102", user.id)
        db.commit()

        resp = client.get("/api/v1/utility-bills/profit", headers=headers)
        rows = resp.json()["monthly_breakdown"]
        aug = _get_month(rows, series, 2026, 8)
        assert aug["electric_collected"] == 300.0

    def test_water_and_electric_independent(self, client, db, owner):
        """水和电各自取最新"""
        headers, series = owner
        user = db.query(User).filter_by(username="profit_owner_1003").one()
        room = db.query(Room).filter_by(room_number="P-101").one()

        _mk_payment(db, room.id, 50, date(2026, 8, 20), "水费 P-101", user.id)
        _mk_payment(db, room.id, 60, date(2026, 8, 25), "水费 P-101", user.id)
        _mk_payment(db, room.id, 130, date(2026, 8, 20), "电费 P-101", user.id)
        db.commit()

        resp = client.get("/api/v1/utility-bills/profit", headers=headers)
        rows = resp.json()["monthly_breakdown"]
        aug = _get_month(rows, series, 2026, 8)
        assert aug["water_collected"] == 60.0
        assert aug["electric_collected"] == 130.0

    def test_profit_calculation_with_cost(self, client, db, owner):
        """收益 = 收 - 支；支出为0时不算收益"""
        headers, series = owner
        user = db.query(User).filter_by(username="profit_owner_1003").one()
        room = db.query(Room).filter_by(room_number="P-101").one()

        _mk_payment(db, room.id, 150, date(2026, 8, 20), "电费 P-101", user.id)
        db.commit()

        # 8月电费支出100
        db.add(UtilityBill(series=series, year=2026, month=8, utility_type="electric", cost=100.0))
        db.commit()

        resp = client.get("/api/v1/utility-bills/profit", headers=headers)
        rows = resp.json()["monthly_breakdown"]
        aug = _get_month(rows, series, 2026, 8)
        assert aug["electric_collected"] == 150.0
        assert aug["electric_cost"] == 100.0
        assert aug["electric_profit"] == 50.0
        # 水费支出未录 → 收益为0
        assert aug["water_profit"] == 0.0


class TestSeriesDetailEndpoint:
    """/series/{series}/detail 同步账期+取最新"""

    def test_detail_latest_reading_per_period(self, client, db, owner):
        headers, series = owner
        user = db.query(User).filter_by(username="profit_owner_1003").one()
        room = db.query(Room).filter_by(room_number="P-101").one()

        p1 = _mk_payment(db, room.id, 100, date(2026, 8, 20), "电费 P-101", user.id)
        r1 = _mk_reading(db, room.id, "electricity", date(2026, 8, 20), 100, p1.id, user.id)
        # 9/2补录修正 → 归8月，应显示这条
        p2 = _mk_payment(db, room.id, 150, date(2026, 9, 2), "电费 P-101", user.id)
        r2 = _mk_reading(db, room.id, "electricity", date(2026, 9, 2), 150, p2.id, user.id)
        db.commit()

        resp = client.get(
            f"/api/v1/utility-bills/series/{series}/detail",
            params={"year": 2026, "month": 8},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        row = next(r for r in data if r["room_number"] == "P-101")
        assert row["electric_amount"] == 150.0  # 最新一次
        assert row["electric_date"] == "2026-09-02"

        # 9月账期应该是空的
        resp9 = client.get(
            f"/api/v1/utility-bills/series/{series}/detail",
            params={"year": 2026, "month": 9},
            headers=headers,
        )
        row9 = next(r for r in resp9.json() if r["room_number"] == "P-101")
        assert row9["electric_amount"] is None

    def test_detail_water_on_1st_belongs_prev_month(self, client, db, owner):
        headers, series = owner
        user = db.query(User).filter_by(username="profit_owner_1003").one()
        room = db.query(Room).filter_by(room_number="P-101").one()

        p = _mk_payment(db, room.id, 55, date(2026, 9, 1), "水费 P-101", user.id)
        _mk_reading(db, room.id, "water", date(2026, 9, 1), 55, p.id, user.id)
        db.commit()

        resp = client.get(
            f"/api/v1/utility-bills/series/{series}/detail",
            params={"year": 2026, "month": 8},
            headers=headers,
        )
        row = next(r for r in resp.json() if r["room_number"] == "P-101")
        assert row["water_amount"] == 55.0


class TestSingleBillEndpoint:
    """/{bill_id} 单账单收益口径一致"""

    def test_single_bill_profit_uses_period_rule(self, client, db, owner):
        headers, series = owner
        user = db.query(User).filter_by(username="profit_owner_1003").one()
        room = db.query(Room).filter_by(room_number="P-101").one()

        # 8/31收100 + 9/1收150 → 都归8月，取最新150
        _mk_payment(db, room.id, 100, date(2026, 8, 31), "电费 P-101", user.id)
        _mk_payment(db, room.id, 150, date(2026, 9, 1), "电费 P-101", user.id)
        db.commit()

        db.add(UtilityBill(series=series, year=2026, month=8, utility_type="electric", cost=120.0))
        db.commit()
        bill = db.query(UtilityBill).filter_by(series=series, year=2026, month=8).one()

        resp = client.get(f"/api/v1/utility-bills/{bill.id}", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["electric_collected"] == 150.0
        assert float(data["electric_profit"]) == 30.0

    def test_single_bill_other_series_forbidden(self, client, db, owner):
        headers, series = owner
        db.add(UtilityBill(series="OTHER", year=2026, month=8, utility_type="water", cost=10.0))
        db.commit()
        bill = db.query(UtilityBill).filter_by(series="OTHER").one()
        resp = client.get(f"/api/v1/utility-bills/{bill.id}", headers=headers)
        assert resp.status_code == 403


class TestDataIsolation:
    """数据隔离：别人的系列不能算进我的收益"""

    def test_other_users_series_excluded(self, client, db, owner):
        headers, series = owner
        user = db.query(User).filter_by(username="profit_owner_1003").one()
        # 另一个用户的系列
        other = User(
            username="other_1003",
            email="other_1003@test.com",
            password_hash=pwd_context.hash("Test12345"),
            role="landlord",
        )
        db.add(other)
        db.flush()
        other_room = Room(room_number="X-1", series="XSER", monthly_rent=500, owner_id=other.id)
        db.add(other_room)
        db.flush()
        _mk_payment(db, other_room.id, 999, date(2026, 8, 20), "电费 X-1", other.id)
        db.commit()

        resp = client.get("/api/v1/utility-bills/profit", headers=headers)
        rows = resp.json()["monthly_breakdown"]
        assert all(r["series"] != "XSER" for r in rows)
