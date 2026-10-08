"""覆盖周期前后端同构性验证（2026-10-06 预收口径修复）

前端 getCoveragePeriod（paymentCycle.ts）与后端 v5 起租日网格
（lease_grid.next_due_date）必须输出完全一致的"下一个未付期"。
本测试锁定同一组用例在两端的结果（前端对应 frontend/tests/coverage-period.test.ts）。

背景：弹窗"覆盖周期"原取"今天所在期"且不看付款记录——租客已预付到
10-09 时 102-4 仍显示 09-10~10-09（已收过的期）。修复后取
next_due（最后已付期+1 期初）为 period_start，期末=+cycle月-1天。
"""
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dateutil.relativedelta import relativedelta
from app.utils.lease_grid import next_due_date

AS_OF = date(2026, 10, 6)

CASES = [
    # (name, lease_start, cycle, pay_dates, expected_start, expected_end)
    ('102-4真实', '2026-03-10', 1,
     ['2026-04-07', '2026-05-07', '2026-06-07', '2026-07-08', '2026-08-07', '2026-09-08'],
     '2026-10-10', '2026-11-09'),
    ('从未收租', '2026-06-15', 1, [], '2026-06-15', '2026-07-14'),
    ('季付下期', '2026-09-05', 3, ['2026-10-02'], '2026-12-05', '2027-03-04'),
    # 月末回退后日漂移：1-31→2-28→3-28（前后端 addMonths/relativedelta 迭代一致）
    ('月末回退', '2026-01-31', 1, ['2026-02-28'], '2026-03-28', '2026-04-27'),
    # 旧租客付款（早于 lease_start-14）不顶新租客的期
    ('换租隔离', '2026-09-10', 1, ['2026-08-08', '2026-09-08'], '2026-10-10', '2026-11-09'),
]


def test_coverage_period_next_unpaid():
    for name, ls, cyc, pays, want_start, want_end in CASES:
        nd = next_due_date(date.fromisoformat(ls), cyc,
                           [date.fromisoformat(p) for p in pays], AS_OF)
        end = nd + relativedelta(months=cyc) - timedelta(days=1)
        assert str(nd) == want_start, f"{name}: start {nd} != {want_start}"
        assert str(end) == want_end, f"{name}: end {end} != {want_end}"
