"""
测试房间水电记录 API 的日期范围过滤（start_date/end_date）

背景：前端 hasThisMonthReading 用 start_date/end_date 判断"本月是否已录入"，
但后端端点此前缺少这两个参数，导致日期过滤被静默忽略——只要房间历史上
有任何一条水电记录，就误判为"本月已录入"（2026-09 事故：2501C 房间 7 月有
旧记录、8/9 月未录入，却被误判为本月已录入，漏掉收租提醒）。
"""
import pytest
from datetime import date
from decimal import Decimal

from app.models import Room, UtilityReading


def _make_room(db, room_number="2501C"):
    room = Room(
        room_number=room_number,
        monthly_rent=Decimal("800.00"),
        payment_cycle=1,
        status="occupied",
        water_rate=Decimal("0"),
        electricity_rate=Decimal("0"),
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


def _add_reading(db, room_id, utility_type, reading_date, reading=0):
    r = UtilityReading(
        room_id=room_id,
        utility_type=utility_type,
        reading=Decimal(str(reading)),
        reading_date=reading_date,
        previous_reading=Decimal("0"),
        usage=Decimal("0"),
        amount=Decimal("0"),
    )
    db.add(r)
    db.commit()
    return r


class TestUtilityReadingsDateFilter:
    """验证 start_date/end_date 过滤正确生效"""

    def test_excludes_old_records_outside_month(self, client, db, auth_headers):
        """历史月份记录不应被本月查询命中（2501C 事故根因）"""
        room = _make_room(db)
        # 7 月的旧记录（模拟 2501C 最后一次录入是 7-20）
        _add_reading(db, room.id, "water", date(2026, 7, 20))
        _add_reading(db, room.id, "electricity", date(2026, 7, 20))

        resp = client.get(
            f"/api/v1/rooms/{room.id}/utility-readings",
            params={"start_date": "2026-09-01", "end_date": "2026-09-30", "size": 50},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # 7 月的记录不应出现在 9 月范围内
        assert data["total"] == 0
        assert data["items"] == []

    def test_includes_records_within_month(self, client, db, auth_headers):
        """本月记录应被本月查询命中"""
        room = _make_room(db)
        _add_reading(db, room.id, "water", date(2026, 9, 15))
        _add_reading(db, room.id, "electricity", date(2026, 9, 15))

        resp = client.get(
            f"/api/v1/rooms/{room.id}/utility-readings",
            params={"start_date": "2026-09-01", "end_date": "2026-09-30", "size": 50},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    def test_utility_type_filter_combined_with_date(self, client, db, auth_headers):
        """日期 + 类型组合过滤：本月水记录命中、电记录不命中"""
        room = _make_room(db)
        _add_reading(db, room.id, "water", date(2026, 9, 10))
        _add_reading(db, room.id, "electricity", date(2026, 8, 10))  # 上月电记录

        resp = client.get(
            f"/api/v1/rooms/{room.id}/utility-readings",
            params={
                "utility_type": "electricity",
                "start_date": "2026-09-01",
                "end_date": "2026-09-30",
                "size": 50,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # 9 月没有电记录，应返回空
        assert data["total"] == 0

    def test_no_date_filter_returns_all(self, client, db, auth_headers):
        """不传日期时保持原行为：返回所有记录"""
        room = _make_room(db)
        _add_reading(db, room.id, "water", date(2026, 7, 20))
        _add_reading(db, room.id, "water", date(2026, 9, 15))

        resp = client.get(
            f"/api/v1/rooms/{room.id}/utility-readings",
            params={"size": 50},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
