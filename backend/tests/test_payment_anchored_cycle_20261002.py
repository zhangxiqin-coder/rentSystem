"""
2026-10-02 2-2501-A 事故回归测试 → v5 起租日网格引擎（同日用户裁决改版）。

事故链（两起）：
1. 房间编辑改了 rooms.lease_start 但活跃租约未同步 → 周期锚点脱节，
   旧租客07-10的4800落进错误锚点(07-06)的±14天窗口 → 误判"本周期已收"
   → 新租客韩力(租约95, 09-06起)的房租被清零。
2. v3 固定窗口：锚点日(6号)与实际收款日(10-02)漂移26天>14天 → 付款
   永远落不进固定窗口 → 付款后又被判未付 → 重复计租。
3. v4 支付锚定（付款日X覆盖[X, X+cycle月)）被用户否决：
   "逾期标准是房租起租日那天算，怎么以上次交租日期算"——应收日固定，
   且月付被排除在判定外（302-4 刚交完仍显示"即将到期"）。

v5 引擎（app/utils/lease_grid.py）：
- 期界：G0=lease_start，G(k+1)=Gk+cycle月。付款不改变期界。
- 付款分配（最晚兼容期）：落在 [期初-14天, 下期初) 的付款抵付该期，
  且下期初前14天内 → 优先抵付下期（预付惯例）。
- 应收日 = 最后已付期+1 的期初；无实付 → lease_start。

覆盖三处实现：
- backend/app/service/business.py::_has_paid_for_target_cycle（逾期/到期列表）
- backend/app/utils/notification_service.py::_has_paid_for_target_cycle（微信消息）
- backend/app/utils/lease_grid.py（共享引擎，前端 paymentCycle.ts 同构）
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.utils import lease_grid
from app.utils.lease_grid import is_paid_through, next_due_date


# 2-2501-A 真实数据（2026-10-02 云端核实）
LEASE_95 = date(2026, 9, 6)      # 韩力租约起租日（rooms.lease_start 已修正）
CYCLE = 3                        # 季付
OLD_TENANT_PAYMENT = date(2026, 7, 10)   # 旧租客4800（07-15~07-14租约期内）
NEW_TENANT_PAYMENT = date(2026, 10, 2)   # 用户10-02实付4800（payment 763）

# 302-4 真实数据（月付误报事故，v5 把月付纳入判定的验证用例）
LEASE_302_4 = date(2025, 8, 4)
PAYS_302_4 = [
    date(2026, 3, 30), date(2026, 5, 2), date(2026, 5, 30),
    date(2026, 7, 2), date(2026, 8, 1), date(2026, 8, 31),
    date(2026, 10, 2),
]


class TestIncident2501A:
    """事故场景回放：v5 网格引擎必须给出与用户预期一致的判定"""

    def test_before_payment_unpaid(self):
        """收款前(10-01)：韩力首期未付 → 应收房租"""
        assert is_paid_through(LEASE_95, CYCLE, [OLD_TENANT_PAYMENT], date(2026, 10, 1)) is False

    def test_day_of_payment_10_02(self):
        """10-02当天（已记4800，覆盖网格期[09-06,12-06)）：判定已付"""
        assert is_paid_through(
            LEASE_95, CYCLE, [OLD_TENANT_PAYMENT, NEW_TENANT_PAYMENT], date(2026, 10, 2)
        ) is True

    def test_grid_due_date_fixed(self):
        """v5 核心口径：应收日固定在网格上（12-06），不随付款日(10-02)漂移"""
        nd = next_due_date(
            LEASE_95, CYCLE, [OLD_TENANT_PAYMENT, NEW_TENANT_PAYMENT], date(2026, 10, 2)
        )
        assert nd == date(2026, 12, 6)

    def test_nov_no_double_rent(self):
        """11月录水电：网格期[09-06,12-06)已付 → 不重复计4800"""
        assert is_paid_through(
            LEASE_95, CYCLE, [OLD_TENANT_PAYMENT, NEW_TENANT_PAYMENT], date(2026, 11, 15)
        ) is True

    def test_dec_after_grid_expiry_unpaid(self):
        """12-06网格期到期后：下一期应收（用户口径：应收日固定，
        12-06起新一期，未付则显示应收——与v4(顺延到01-02)不同）"""
        assert is_paid_through(
            LEASE_95, CYCLE, [OLD_TENANT_PAYMENT, NEW_TENANT_PAYMENT], date(2026, 12, 20)
        ) is False

    def test_old_tenant_payment_excluded(self):
        """换租隔离：旧租客07-10付款（早于09-06前14天线08-23）不参与"""
        assert is_paid_through(LEASE_95, CYCLE, [OLD_TENANT_PAYMENT], date(2026, 10, 2)) is False

    def test_advance_payment_14d_before_lease(self):
        """提前交租：起租日前14天内(08-25)付款算覆盖首期"""
        assert is_paid_through(LEASE_95, CYCLE, [date(2026, 8, 25)], date(2026, 9, 6)) is True

    def test_payment_before_14d_window_excluded(self):
        """起租前>14天的付款(08-10)不算（旧租客/定金性质）"""
        assert is_paid_through(LEASE_95, CYCLE, [date(2026, 8, 10)], date(2026, 9, 6)) is False


class TestMonthlyRoomsV5:
    """月付纳入网格判定（v4 把月付排除 → 302-4 10-02刚交仍显示"即将到期2天"）"""

    def test_302_4_just_paid_not_expiring(self):
        """302-4 真实付款史：10-02付款预付[10-04期)，下次应收11-04 → 已付"""
        assert is_paid_through(LEASE_302_4, 1, PAYS_302_4, date(2026, 10, 2)) is True

    def test_302_4_next_due_on_grid(self):
        """下次应收=11-04（起租日4号网格），不是付款日+30天"""
        nd = next_due_date(LEASE_302_4, 1, PAYS_302_4, date(2026, 10, 2))
        assert nd == date(2026, 11, 4)

    def test_302_4_without_oct_payment_unpaid(self):
        """若无10-02付款：网格判定本期[09-04,10-04)已由8-31付款覆盖，
        应收日=10-04（未来2天）→ is_paid_through=True（本期已付），
        但 days_to_due=2 → 出现在"即将到期"提醒列表（302-1真实场景）"""
        assert is_paid_through(LEASE_302_4, 1, PAYS_302_4[:-1], date(2026, 10, 2)) is True
        nd = next_due_date(LEASE_302_4, 1, PAYS_302_4[:-1], date(2026, 10, 2))
        assert nd == date(2026, 10, 4)
        assert (nd - date(2026, 10, 2)).days == 2

    def test_monthly_never_paid_chase(self):
        """月付从无付款记录 → 应收（回退到 lease_start）"""
        assert is_paid_through(LEASE_302_4, 1, [], date(2026, 10, 2)) is False


class TestGridEngineUnits:
    """引擎单元：月末溢出、豁免线、多年网格"""

    def test_month_end_overflow(self):
        """502-2：起租08-30月付，9月期(09-30)已付9-27 → 下期10-30"""
        nd = next_due_date(date(2026, 8, 30), 1, [date(2026, 9, 27)], date(2026, 10, 2))
        assert nd == date(2026, 10, 30)

    def test_amnesty_before_cutoff(self):
        """豁免线：期初 < cutoff 的未付期不追讨（102-6 年付无付款记录场景）"""
        nd = next_due_date(date(2026, 4, 9), 12, [], date(2026, 10, 2), cutoff=date(2026, 9, 1))
        assert nd == date(2027, 4, 9)

    def test_annual_room_never_paid_no_cutoff_ancient_due(self):
        """无豁免线时年付无付款 → 应收=lease_start（远古但真实欠付）"""
        nd = next_due_date(date(2026, 4, 9), 12, [], date(2026, 10, 2))
        assert nd == date(2026, 4, 9)

    def test_quarterly_extra_payment_not_carried(self):
        """102-2：4-29/6-30/8-01三笔（历史多付一笔）→ 以最近实付向前看，
        下次应收=网格上的11-02（不追历史缺口）"""
        nd = next_due_date(
            date(2025, 5, 2), 3,
            [date(2026, 4, 29), date(2026, 6, 30), date(2026, 8, 1)],
            date(2026, 10, 2),
        )
        assert nd == date(2026, 11, 2)


# ────────────────────────────────────────────────────────────
# 后端实现层：business.py / notification_service.py 真实函数
# ────────────────────────────────────────────────────────────

PROD_CUTOFF = date(2026, 4, 22)  # 生产默认豁免线


class TestBackendImplementations:
    """直接调用后端真实函数（内存对象模拟Room/Payment）"""

    def _make_room(self, lease_start, cycle=3, room_id=41, last_payment_date=None):
        class _R:
            pass
        r = _R()
        r.id = room_id
        r.payment_cycle = cycle
        r.lease_start = lease_start
        r.last_payment_date = last_payment_date
        return r

    def _make_payment(self, room_id, pd, ptype="rent", status="completed"):
        class _P:
            pass
        p = _P()
        p.room_id = room_id
        p.payment_date = pd
        p.payment_type = ptype
        p.status = status
        return p

    def test_business_impl_2501a_timeline(self):
        """business.py 版本沿 2-2501-A 时间线判定正确（生产豁免线）"""
        from app.service.business import _has_paid_for_target_cycle

        room = self._make_room(LEASE_95, 3)
        pays = [self._make_payment(41, OLD_TENANT_PAYMENT),
                self._make_payment(41, NEW_TENANT_PAYMENT)]

        # 已含10-02付款 → 已付
        assert _has_paid_for_target_cycle(room, pays, PROD_CUTOFF, 7) is True
        # 只有旧租客付款 → 未付（应收4800）
        assert _has_paid_for_target_cycle(room, pays[:1], PROD_CUTOFF, 7) is False
        # 无任何付款 → 首期未付
        assert _has_paid_for_target_cycle(room, [], PROD_CUTOFF, 7) is False

    def test_business_impl_monthly_302_4(self):
        """business.py 月付判定（v5 新增：月付参与）"""
        from app.service.business import _has_paid_for_target_cycle

        room = self._make_room(LEASE_302_4, cycle=1, room_id=27)
        pays = [self._make_payment(27, d) for d in PAYS_302_4]
        assert _has_paid_for_target_cycle(room, pays, PROD_CUTOFF, 7) is True

    def test_notification_impl_2501a_today(self):
        """notification_service.py 版本（微信消息路径）今天判定已付"""
        from app.utils.notification_service import _has_paid_for_target_cycle as ns_has_paid

        class _R:
            pass
        room = _R()
        room.id = 41
        room.payment_cycle = 3
        room.lease_start = LEASE_95

        class _DB:
            def query(self, *a, **k):
                class _Q:
                    def filter(self, *a, **k):
                        return self
                    def all(self):
                        return [(NEW_TENANT_PAYMENT,), (OLD_TENANT_PAYMENT,)]
                return _Q()

        assert ns_has_paid(_DB(), room, 3) is True

    def test_notification_impl_monthly_paid(self):
        """notification_service.py 月付判定（302-4 场景）"""
        from app.utils.notification_service import _has_paid_for_target_cycle as ns_has_paid

        class _R:
            pass
        room = _R()
        room.id = 27
        room.payment_cycle = 1
        room.lease_start = LEASE_302_4

        class _DB:
            def query(self, *a, **k):
                class _Q:
                    def filter(self, *a, **k):
                        return self
                    def all(self):
                        return [(d,) for d in PAYS_302_4]
                return _Q()

        assert ns_has_paid(_DB(), room, 1) is True


if __name__ == "__main__":
    failures = 0
    import inspect
    for cname, cls in sorted({k: v for k, v in globals().items() if inspect.isclass(v) and k.startswith("Test")}.items()):
        inst = cls()
        for mname, m in sorted(inspect.getmembers(inst, predicate=inspect.ismethod)):
            if mname.startswith("test_"):
                try:
                    m()
                    print(f"PASS {cname}.{mname}")
                except AssertionError as e:
                    print(f"FAIL {cname}.{mname}: {e}")
                    failures += 1
    sys.exit(1 if failures else 0)
