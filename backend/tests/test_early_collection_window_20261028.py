"""
提前收租窗口回归测试（2026-10-28 102-2 案例）

场景：季付房间已付上期、下期到期日进入 14 天提前收租窗口。
录入水电时催租消息/弹窗必须含下期房租——租客惯常提前 2-5 天预付。
旧 bug：shouldIncludeRent / _has_paid_for_target_cycle 只看"到期日≤今天"，
102-2（11-02 到期、10-28 录水电）被判"已付"，房租行被吃掉。
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest


@pytest.fixture
def q_room_1022(db, test_user):
    """复刻 102-2：季付 lease_start=2025-05-02，付款覆盖到 11-01。"""
    from app.models import Room, Payment

    room = Room(
        room_number="T-EARLY-102",
        building="测试楼",
        monthly_rent=Decimal("1550"),
        payment_cycle=3,
        lease_start=date(2025, 5, 2),
        status="occupied",
        owner_id=test_user.id,
    )
    db.add(room)
    db.flush()
    # 按季付款：4-29 / 6-30 / 8-01（最后这笔覆盖 8-02~11-01）
    for pd in (date(2026, 4, 29), date(2026, 6, 30), date(2026, 8, 1)):
        db.add(Payment(
            room_id=room.id, payment_type="rent", amount=Decimal("4650"),
            payment_date=pd, status="completed", owner_id=test_user.id,
        ))
    db.commit()
    return room


class TestEarlyCollectionWindow:
    def test_due_within_14_days_should_include_rent(self, db, q_room_1022):
        """下期到期日进入 14 天窗口（102-2：11-02，今天 10-28 差 5 天）→ 含房租。"""
        from app.utils.notification_service import _has_paid_for_target_cycle

        room = db.query(type(q_room_1022)).get(q_room_1022.id)
        db.refresh(room)

        # 直接用引擎断言口径：next_due=11-02，is_paid_through 旧口径=True，
        # 但通知层必须返回 False（=未付=含房租）
        from app.utils import lease_grid
        from app.models import Payment
        pays = [p.payment_date for p in db.query(Payment).filter(
            Payment.room_id == room.id, Payment.status != "cancelled").all()]
        nd = lease_grid.next_due_date(room.lease_start, 3, pays, date.today())
        days = (nd - date.today()).days
        assert 0 < days <= 14, f"fixture 漂移：next_due={nd} 差{days}天，不在窗口内"

        result = _has_paid_for_target_cycle(db, room, cycle=3)
        assert result is False, f"差{days}天已进入提前收租窗口，催租消息应含房租"

    def test_due_far_future_should_exclude_rent(self, db, q_room_1022):
        """下期到期日还远（>14天）→ 已付，不含房租。"""
        from app.models import Payment, Room
        from app.utils.notification_service import _has_paid_for_target_cycle

        room = db.query(type(q_room_1022)).get(q_room_1022.id)
        # 补一笔今天刚交的（覆盖到 2027-02），下期到期日推出 >14 天
        db.add(Payment(
            room_id=room.id, payment_type="rent", amount=Decimal("4650"),
            payment_date=date.today(), status="completed",
            owner_id=room.owner_id,
        ))
        db.commit()
        db.refresh(room)
        assert _has_paid_for_target_cycle(db, room, cycle=3) is True

    def test_business_impl_same_semantics(self, db, q_room_1022):
        """business._has_paid_for_target_cycle 与通知层同口径（窗口内→False）。"""
        from app.models import Payment
        from app.service.business import _has_paid_for_target_cycle as biz_impl
        from app.utils import lease_grid

        room = db.query(type(q_room_1022)).get(q_room_1022.id)
        db.refresh(room)
        pays = [p.payment_date for p in db.query(Payment).filter(
            Payment.room_id == room.id, Payment.status != "cancelled").all()]
        nd = lease_grid.next_due_date(room.lease_start, 3, pays, date.today())
        assert (nd - date.today()).days <= 14

        payments = db.query(Payment).filter(
            Payment.room_id == room.id).all()
        assert biz_impl(room, payments, cutoff=date(2026, 4, 22), expiring_days=7) is False
