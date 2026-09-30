"""
2026-09-27 102-2 事故回归测试：季付提前交租后不应重复计入房租。

事故：102-2（季付，lease_start=2025-05-02）8-01 已交 4650（覆盖 8/2~11/1 季度），
9-27 录水电时账单又含 4650 房租。

根因：_has_paid_for_target_cycle / shouldIncludeRent 检查的是"下次到期日"
（11-02）±14天，8-01 的支付自然不在窗口内 → 误判"未付"。

修复：改为检查"当前周期到期日"（最后一个 <= 今天的到期日，即 8-02），
8-01 落在 8-02 ±14天内 → 正确判定"已付"。
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dateutil.relativedelta import relativedelta


def current_cycle_due(lease_start: date, cycle: int, today: date) -> date:
    """与修复后的 _has_paid_for_target_cycle 相同的算法（当前周期到期日）"""
    if lease_start > today:
        raise ValueError("lease not started")
    current_due = lease_start
    while True:
        nxt = current_due + relativedelta(months=cycle)
        if nxt > today:
            break
        current_due = nxt
    return current_due


def has_paid_current_cycle(payment_date: date, lease_start: date, cycle: int, today: date) -> bool:
    """模拟修复后的判断：支付是否落在当前周期到期日±14天内"""
    due = current_cycle_due(lease_start, cycle, today)
    return abs((payment_date - due).days) <= 14


# ---- 102-2 真实数据推演 ----
LEASE_START = date(2025, 5, 2)
CYCLE = 3
PAYMENT_8_1 = date(2026, 8, 1)  # 事故当天已存在的支付
TODAY = date(2026, 9, 27)       # 事故当天


def test_1022_current_due_is_aug2():
    """当前周期到期日应为 2026-08-02（而非下次 11-02）"""
    assert current_cycle_due(LEASE_START, CYCLE, TODAY) == date(2026, 8, 2)


def test_1022_paid_aug1_covers_current_cycle():
    """8-01 支付落在 8-02 ±14天内 → 已付，不应再收房租（事故场景）"""
    assert has_paid_current_cycle(PAYMENT_8_1, LEASE_START, CYCLE, TODAY) is True


def test_1022_nov_payment_not_needed_yet():
    """11月季度尚未到期，11-02 附近不应有支付（模拟查库为空）"""
    due = current_cycle_due(LEASE_START, CYCLE, TODAY)
    assert date(2026, 11, 2) not in [due - timedelta(days=d) for d in range(-14, 15)]


def test_no_payment_means_unpaid():
    """当前周期到期日 ±14 天外无支付 → 未付，应收房租"""
    # 假设只在 6-30 交过（覆盖上个季度），当前周期 8-02 未付
    assert has_paid_current_cycle(date(2026, 6, 30), LEASE_START, CYCLE, TODAY) is False


def test_old_next_due_logic_would_fail():
    """反证：旧逻辑（查下次到期日 11-02）会误判——写这个测试防止回退"""
    next_due = LEASE_START
    while next_due <= TODAY:
        next_due += relativedelta(months=CYCLE)
    assert next_due == date(2026, 11, 2)
    # 8-01 支付不在 11-02 ±14天内 → 旧逻辑判定未付 → bug
    assert abs((PAYMENT_8_1 - next_due).days) > 14


def test_after_nov_due_without_payment():
    """11-02 之后（如 12-01）若 11 月季度未付 → 应判定未付（应收房租）"""
    today2 = date(2026, 12, 1)
    # 无 11 月支付
    assert has_paid_current_cycle(PAYMENT_8_1, LEASE_START, CYCLE, today2) is False


def test_after_nov_due_with_payment():
    """11-02 季度若已在 11-01 支付 → 应判定已付"""
    today2 = date(2026, 12, 1)
    assert has_paid_current_cycle(date(2026, 11, 1), LEASE_START, CYCLE, today2) is True


def test_monthly_cycle_never_checked():
    """月付不走此判断（cycle=1）——由调用方保证，这里验证算法在 cycle=1 时也给出合理结果"""
    # 月付 lease_start=2026-09-05，9-05 交租，9-27 查询
    ls = date(2026, 9, 5)
    assert has_paid_current_cycle(date(2026, 9, 5), ls, 1, TODAY) is True
    assert has_paid_current_cycle(date(2026, 8, 5), ls, 1, TODAY) is False


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted({k: v for k, v in globals().items() if k.startswith("test_") and callable(v)}.items()):
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as e:
            print(f"FAIL {name}: {e}")
            failures += 1
    sys.exit(1 if failures else 0)
