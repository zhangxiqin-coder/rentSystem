"""同日防重复读数测试 —— 2026-09-07 502-2 退租结算重复录入事故的回归测试

背景：end-lease 结算/抄表接口无幂等，双击或重试会生成两套读数+支付，
导致收益统计虚增（502-2 退租结算重复，8月电费虚增 381）。
修复：create_utility_reading 服务层加同日查重（同房间+同类型+同日期拒绝）。
"""
import pytest
from datetime import date
from decimal import Decimal

from app.models import Room, UtilityRate
from app.service.business import create_utility_reading


def _mk_room(db, number="T-dup-101"):
    room = Room(room_number=number, monthly_rent=Decimal("1000"), payment_cycle=1)
    db.add(room)
    db.add(UtilityRate(utility_type="water", rate_per_unit=Decimal("5.0"),
                       effective_date=date(2024, 1, 1)))
    db.add(UtilityRate(utility_type="electricity", rate_per_unit=Decimal("1.0"),
                       effective_date=date(2024, 1, 1)))
    db.commit()
    return room


class TestSameDayDuplicatePrevention:

    def test_same_day_same_type_rejected(self, db):
        """同房间+同类型+同日期的第二条读数必须被拒绝"""
        room = _mk_room(db)
        r1 = create_utility_reading(
            db, room_id=room.id, utility_type="water",
            reading=Decimal("100"), reading_date=date(2026, 8, 27),
        )
        assert r1.usage == Decimal("100")

        with pytest.raises(ValueError, match="已存在"):
            create_utility_reading(
                db, room_id=room.id, utility_type="water",
                reading=Decimal("100"), reading_date=date(2026, 8, 27),
            )

    def test_same_day_different_type_allowed(self, db):
        """同日水+电各一条是正常流程（含0费率房间的自动0读数），必须放行"""
        room = _mk_room(db, "T-dup-102")
        create_utility_reading(
            db, room_id=room.id, utility_type="water",
            reading=Decimal("100"), reading_date=date(2026, 8, 27),
        )
        r2 = create_utility_reading(  # 不应抛错
            db, room_id=room.id, utility_type="electricity",
            reading=Decimal("200"), reading_date=date(2026, 8, 27),
        )
        assert r2.usage == Decimal("200")

    def test_different_day_allowed(self, db):
        """不同日期的读数是正常月度抄表，必须放行"""
        room = _mk_room(db, "T-dup-103")
        create_utility_reading(
            db, room_id=room.id, utility_type="water",
            reading=Decimal("100"), reading_date=date(2026, 7, 27),
        )
        r2 = create_utility_reading(  # 不应抛错
            db, room_id=room.id, utility_type="water",
            reading=Decimal("110"), reading_date=date(2026, 8, 27),
        )
        assert r2.usage == Decimal("10")

    def test_different_room_allowed(self, db):
        """不同房间同日同类型读数必须放行"""
        room_a = _mk_room(db, "T-dup-104A")
        room_b = Room(room_number="T-dup-104B", monthly_rent=Decimal("1000"), payment_cycle=1)
        db.add(room_b)
        db.commit()
        create_utility_reading(
            db, room_id=room_a.id, utility_type="water",
            reading=Decimal("100"), reading_date=date(2026, 8, 27),
        )
        r2 = create_utility_reading(  # 不应抛错
            db, room_id=room_b.id, utility_type="water",
            reading=Decimal("300"), reading_date=date(2026, 8, 27),
        )
        assert r2.usage == Decimal("300")

    def test_zero_reading_room_water_then_electric(self, db):
        """0费率房间自动创建水/电两条0读数（同日不同类型），必须放行"""
        room = _mk_room(db, "T-dup-105")
        create_utility_reading(
            db, room_id=room.id, utility_type="water",
            reading=Decimal("0"), reading_date=date(2026, 8, 27),
            previous_reading=Decimal("0"),
        )
        r2 = create_utility_reading(  # 不应抛错
            db, room_id=room.id, utility_type="electricity",
            reading=Decimal("0"), reading_date=date(2026, 8, 27),
            previous_reading=Decimal("0"),
        )
        assert float(r2.amount) == 0.0

    def test_manual_previous_reading_still_checked_for_dup(self, db):
        """手工传入 previous_reading 的路径同样受同日查重保护"""
        room = _mk_room(db, "T-dup-106")
        create_utility_reading(
            db, room_id=room.id, utility_type="water",
            reading=Decimal("100"), reading_date=date(2026, 8, 27),
            previous_reading=Decimal("90"),
        )
        with pytest.raises(ValueError, match="已存在"):
            create_utility_reading(
                db, room_id=room.id, utility_type="water",
                reading=Decimal("105"), reading_date=date(2026, 8, 27),
                previous_reading=Decimal("90"),
            )
