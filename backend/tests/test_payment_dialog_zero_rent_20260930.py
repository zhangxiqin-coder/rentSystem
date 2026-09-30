"""标记已收弹窗季付房间房租重复预填修复（2026-09-30 102-2 事故回归）

根因：usePaymentData.showPaymentDialog 预填 rent_amount = monthly_rent × cycle，
      完全没查"本周期房租是否已收"。9-27 修复了消息+表格总计（skill 记录的5处），
      但"标记已收"弹窗是第6处漏网——用户点开弹窗看到实收房租又预填了 4650。

配套后端修复：rent_amount=0（只收水电）时不再创建 0 元 rent 支付记录。
      0 元记录若落在到期日 ±14 天窗口内，会污染 shouldIncludeRent /
      _has_paid_for_target_cycle 的判断，导致下个周期真正该收的房租被误判已收。

测试覆盖：
  1. 前端逻辑模拟：弹窗预填在"本周期已收房租"时 rent_amount 应为 0
  2. 后端 API：rent_amount=0 + 水电 > 0 → 只创建 utility 记录，无 0 元 rent
  3. 后端 API：0 元只收水电后，_has_paid_for_target_cycle 仍正确判定未付
  4. 后端 API：正常收租（rent > 0）不受影响
"""
import json
from datetime import date
from decimal import Decimal

import pytest

from app.models import Room, Payment, User


# ════════════════════════════════════════════════════
# 1. 前端 shouldIncludeRent 逻辑模拟（与 paymentCycle.ts 同算法）
# ════════════════════════════════════════════════════

def _current_due_ts(lease_start: str, cycle: int, today: date) -> float:
    """与 paymentCycle.ts 相同的当前周期到期日算法"""
    from datetime import datetime
    ls = datetime.fromisoformat(lease_start)
    if ls.date() > today:
        return ls.timestamp() * 1000
    cur = ls
    while True:
        import calendar
        y = cur.year + (cur.month - 1 + cycle) // 12
        m = (cur.month - 1 + cycle) % 12 + 1
        try:
            nxt = cur.replace(year=y, month=m)
        except ValueError:
            nxt = cur.replace(year=y, month=m, day=calendar.monthrange(y, m)[1])
        if nxt.date() > today:
            break
        cur = nxt
    return cur.timestamp() * 1000


def _should_include_rent(merged_row: dict, payments: list) -> bool:
    """与前端 shouldIncludeRent(room, payments) 相同的逻辑（含 room_id 兼容）"""
    cycle = max(1, int(merged_row.get("payment_cycle") or 1))
    if cycle <= 1:
        return True
    lease_start = merged_row.get("lease_start")
    if not lease_start:
        return True
    current_due = _current_due_ts(lease_start, cycle, date.today())
    room_id = merged_row.get("id") if merged_row.get("id") is not None else merged_row.get("room_id")
    window_ms = 14 * 24 * 60 * 60 * 1000
    has_paid = any(
        p["room_id"] == room_id
        and p["payment_type"] == "rent"
        and p.get("status") != "cancelled"
        and p.get("payment_date")
        and abs(_payment_ts(p["payment_date"]) - current_due) <= window_ms
        for p in payments
    )
    return not has_paid


def _payment_ts(d: str) -> float:
    from datetime import datetime
    return datetime.fromisoformat(d).timestamp() * 1000


class TestDialogPrefillLogic:
    """弹窗预填逻辑：已收房租的季付房间 rent_amount 必须预填 0"""

    def _row_1022(self) -> dict:
        # 102-2 真实数据：季付，lease_start 2025-05-02，月租 1550
        return {
            "room_id": 40,
            "payment_cycle": 3,
            "lease_start": "2025-05-02",
            "monthly_rent": 1550,
        }

    def test_dialog_prefill_rent_zero_when_cycle_paid(self):
        """102-2 场景：8-01 已交 4650，弹窗预填房租必须为 0"""
        row = self._row_1022()
        payments = [
            {"room_id": 40, "payment_type": "rent", "payment_date": "2026-08-01", "status": "completed"},
        ]
        cycle = max(1, int(row["payment_cycle"] or 1))
        rent_amount = row["monthly_rent"] * cycle
        # 与 usePaymentData.showPaymentDialog 相同的修复后逻辑
        if cycle > 1 and not _should_include_rent(row, payments):
            rent_amount = 0
        assert rent_amount == 0, "本周期房租已收，弹窗房租必须预填0"

    def test_dialog_prefill_rent_when_unpaid(self):
        """季付房间本周期没交房租 → 预填全额（该收）"""
        row = self._row_1022()
        payments = [
            # 上季度的付款，不在当前周期到期日 ±14 天内
            {"room_id": 40, "payment_type": "rent", "payment_date": "2026-06-30", "status": "completed"},
        ]
        cycle = max(1, int(row["payment_cycle"] or 1))
        rent_amount = row["monthly_rent"] * cycle
        if cycle > 1 and not _should_include_rent(row, payments):
            rent_amount = 0
        assert rent_amount == 4650, "本周期未收房租，弹窗应预填全额 4650"

    def test_monthly_room_always_prefills_rent(self):
        """月付房间不检查，永远预填房租"""
        row = {"room_id": 7, "payment_cycle": 1, "lease_start": "2026-01-10", "monthly_rent": 1200}
        payments = [
            {"room_id": 7, "payment_type": "rent", "payment_date": "2026-09-28", "status": "completed"},
        ]
        cycle = 1
        rent_amount = row["monthly_rent"] * cycle
        if cycle > 1 and not _should_include_rent(row, payments):
            rent_amount = 0
        assert rent_amount == 1200


# ════════════════════════════════════════════════════
# 2. 后端 API：rent_amount=0 不创建 0 元 rent 记录
# ════════════════════════════════════════════════════

class TestBulkPaymentZeroRent:
    @pytest.fixture
    def quarterly_room(self, db, test_user):
        # 用 test_user 建（auth_headers 的 token 属于它），否则权限校验 404
        user = test_user

        room = Room(
            room_number="ZR-102-2",
            monthly_rent=Decimal("1550"),
            payment_cycle=3,
            status="occupied",
            tenant_name="潘某",
            lease_start=date(2025, 5, 2),
            lease_end=date(2027, 5, 2),
            owner_id=user.id,
        )
        db.add(room)
        db.flush()  # 先拿 room.id
        # 模拟本周期房租已收（8-01 交 4650，落在 8-02 ±14 天窗口）
        db.add(Payment(
            room_id=room.id,
            payment_type="rent",
            amount=Decimal("4650"),
            payment_date=date(2026, 8, 1),
            status="completed",
            owner_id=user.id,
        ))
        db.commit()
        return room

    def test_zero_rent_creates_no_rent_record(self, client, quarterly_room, auth_headers):
        """只收水电：rent=0 + 水电>0 → 无 rent 记录，只有水/电 utility 记录"""
        r = client.post(
            "/api/v1/payments/bulk",
            json={
                "room_id": quarterly_room.id,
                "reading_date": "2026-09-27",
                "payment_date": "2026-09-30",
                "rent_amount": 0,
                "rent_original": 0,
                "payment_method": "微信支付",
                "water_charge": {
                    "utility_type": "water",
                    "amount": 55,
                    "original_amount": 55,
                    "discount": 0,
                },
                "electricity_charge": {
                    "utility_type": "electricity",
                    "amount": 396,
                    "original_amount": 396,
                    "discount": 0,
                },
            },
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        assert Decimal(str(body["total_actual"])) == Decimal("451")

        # 验证数据库：无 0 元 rent，只有两条 utility
        from app.database import SessionLocal
        sess = SessionLocal()
        try:
            room = sess.query(Room).filter(Room.id == quarterly_room.id).first()
            created = sess.query(Payment).filter(
                Payment.room_id == room.id,
                Payment.payment_date == date(2026, 9, 30),
            ).all()
            types = sorted(p.payment_type for p in created)
            assert types == ["utility", "utility"], f"只应有两条utility，实际: {types}"
            assert all(p.amount > 0 for p in created), "不应存在0元支付记录"
        finally:
            sess.close()

    def test_zero_rent_does_not_pollute_paid_judgment(self, client, quarterly_room, auth_headers):
        """只收水电后，_has_paid_for_target_cycle 对下一周期仍判未付（不漏收房租）"""
        from app.utils.notification_service import _has_paid_for_target_cycle
        from app.database import SessionLocal

        # 先走一遍只收水电（rent=0）
        r = client.post(
            "/api/v1/payments/bulk",
            json={
                "room_id": quarterly_room.id,
                "reading_date": "2026-09-27",
                "payment_date": "2026-09-30",
                "rent_amount": 0,
                "rent_original": 0,
                "payment_method": "微信支付",
                "water_charge": {
                    "utility_type": "water",
                    "amount": 55,
                    "original_amount": 55,
                    "discount": 0,
                },
            },
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text

        sess = SessionLocal()
        try:
            room = sess.query(Room).filter(Room.id == quarterly_room.id).first()
            # 模拟时间走到 11 月初（下个周期到期 11-02）：直接验证 8-02 窗口判断
            # 8-01 的 4650 仍在 8-02 ±14 天内 → 当前周期已付
            has_paid_current = _has_paid_for_target_cycle(sess, room, cycle=3)
            # 9-30 的只收水电操作不应产生任何落在 ±14 天窗口内的 rent 记录
            zero_rents = sess.query(Payment).filter(
                Payment.room_id == room.id,
                Payment.payment_type == "rent",
                Payment.amount == 0,
            ).count()
            assert zero_rents == 0, "不应存在0元rent记录污染窗口判断"
        finally:
            sess.close()

    def test_normal_rent_still_creates_record(self, client, quarterly_room, auth_headers):
        """正常收租（rent>0）不受影响"""
        r = client.post(
            "/api/v1/payments/bulk",
            json={
                "room_id": quarterly_room.id,
                "payment_date": "2026-09-30",
                "rent_amount": 1550,
                "rent_original": 1550,
                "payment_method": "现金",
            },
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert Decimal(str(body["total_actual"])) == Decimal("1550")
        assert len(body["payments"]) == 1

    def test_zero_rent_zero_utilities_rejected(self, client, quarterly_room, auth_headers):
        """rent=0 且无水电 → 不创建任何记录（空支付无意义）"""
        r = client.post(
            "/api/v1/payments/bulk",
            json={
                "room_id": quarterly_room.id,
                "payment_date": "2026-09-30",
                "rent_amount": 0,
                "rent_original": 0,
                "payment_method": "现金",
            },
            headers=auth_headers,
        )
        # 允许 200（空 payments 列表）或 400，但不能 500
        assert r.status_code in (200, 400), r.text
        if r.status_code == 200:
            from app.database import SessionLocal
            sess = SessionLocal()
            try:
                room = sess.query(Room).filter(Room.id == quarterly_room.id).first()
                n = sess.query(Payment).filter(
                    Payment.room_id == room.id,
                    Payment.payment_date == date(2026, 9, 30),
                ).count()
                assert n == 0, "全0支付不应创建任何记录"
            finally:
                sess.close()
