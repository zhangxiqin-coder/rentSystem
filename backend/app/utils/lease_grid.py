"""
租赁收租网格引擎（v5，2026-10-02）——"起租日网格 + 最晚兼容期付款分配"

口径（用户裁决 2026-10-02）：应收/逾期一律从起租日按付款周期推网格，
实际收款日漂移不改变应收日；付款的作用 = 标记某个期已付。

规则：
- 期界：G0 = lease_start，G(k+1) = Gk + cycle个月（relativedelta，月末溢出回退月末）。
- 付款分配：按时间序的 rent 实付，填入"最晚兼容的未付期"，
  兼容窗口 = [期初-14天, 下一期初)。
  * 付款落在下期初前14天内 → 优先抵付下期（预付，本房全部租客的惯例：
    期初前2-5天交租。旧"最早期"分配会把整条付款链错位一期，
    302-4 刚交完仍显示"即将到期"就是这个错位）。
  * 付款落在期内 → 抵付当期（迟交）。
  * 早于 lease_start-14天 的付款 = 旧租客/前租约款项，永久跳过（换租天然隔离）。
  * 多余付款（目标期已付）不结转、不退回，仅忽略（保守，防一次早付顶两期）。
- 豁免（cutoff）：期初 < overdue_cutoff_date 的期一律视为已结清
  （系统上线线之前的历史欠租不追讨；也是 102-6 这类"租约早、近期无付款记录"
  房间不会被判远古欠租的原因）。
- 应收日 next_due = max(G0, 最后已付期+1期, 最后豁免期+1期)。
  永远落在网格上；历史中段的缺口不追（以最近实付向前看）。
- 判欠：next_due ≤ 今天 → 欠租（days = today - next_due 取负）；
  next_due > 今天 → 本期已收，days = next_due - today。

历史（淘汰原因）：
- v3 ±14天固定窗口：收款日与固定窗口漂移>14天必误判（2-2501-A 事故）。
- v4 支付锚定（付款日X覆盖[X, X+cycle月)）：应收日随付款日漂移，用户否决
  （2026-10-02：标准=起租日）；且月付被排除在判定外。
"""
from datetime import date, timedelta
from typing import List, Optional, Sequence
from dateutil.relativedelta import relativedelta

# 允许提前交租的天数（付款日早于期初不超过该值即可抵付该期）
EARLY_PAY_DAYS = 14


def _add_months(d: date, months: int) -> date:
    return d + relativedelta(months=months)


def build_grid(
    lease_start: date,
    cycle_months: int,
    upto: date,
    extra: int = 2,
) -> List[date]:
    """生成期界序列 G0=lease_start，逐期 +cycle月，直到跨过 upto 再多推 extra 期。"""
    cycle_months = max(1, cycle_months or 1)
    grid = [lease_start]
    while grid[-1] <= upto:
        grid.append(_add_months(grid[-1], cycle_months))
    for _ in range(extra):
        grid.append(_add_months(grid[-1], cycle_months))
    return grid


def _grid_cycle(grid: Sequence[date]) -> int:
    if len(grid) < 2:
        return 1
    a, b = grid[0], grid[1]
    return max(1, (b.year - a.year) * 12 + (b.month - a.month))


def allocate_payments(grid: Sequence[date], pay_dates: Sequence[date]) -> List[bool]:
    """最晚兼容期分配：付款优先抵付其前方14天内开始的期（预付惯例），
    否则抵付所在期（迟交）。返回与 grid 等长的 filled 列表。"""
    cycle_months = _grid_cycle(grid)
    filled = [False] * len(grid)
    for x in sorted(p for p in pay_dates if p is not None):
        # 包含期 idx：最大的 grid[i] <= x
        idx = None
        for i in range(len(grid) - 1, -1, -1):
            if grid[i] <= x:
                idx = i
                break
        if idx is None:
            # 早于起租日：仅当在 G0 前14天内才算预付首期
            if x >= grid[0] - timedelta(days=EARLY_PAY_DAYS) and not filled[0]:
                filled[0] = True
            continue
        # 候选：包含期 idx；若付款落在下期初前14天内，idx+1 也可兼容（预付下期）
        candidates = [idx]
        nxt = grid[idx + 1] if idx + 1 < len(grid) else _add_months(grid[idx], cycle_months)
        if x >= nxt - timedelta(days=EARLY_PAY_DAYS):
            candidates.append(idx + 1)
        # 从最晚候选往回找第一个未付期
        for c in reversed(candidates):
            if c < len(grid) and not filled[c]:
                filled[c] = True
                break
        # 全已付 → 多余付款，忽略
    return filled


def grid_status(
    lease_start: Optional[date],
    cycle_months: int,
    pay_dates: Sequence[date],
    as_of: date,
    cutoff: Optional[date] = None,
) -> dict:
    """完整网格状态。

    Returns:
        {
          'periods': [(期初, filled), ...],
          'next_due': 应收日（见模块docstring；lease_start=None → None）,
          'filled_count': 实付填掉的期数,
        }
    """
    if lease_start is None:
        return {'periods': [], 'next_due': None, 'filled_count': 0}

    pays = [p for p in pay_dates if p is not None]
    upto = max([as_of] + pays) if pays else as_of
    grid = build_grid(lease_start, cycle_months, upto, extra=2)
    filled = allocate_payments(grid, pays)

    last_filled_idx = -1
    for i, f in enumerate(filled):
        if f:
            last_filled_idx = i

    # 豁免前缀：期初 < cutoff 的期全部视为已结清
    first_post_cutoff_idx = 0
    if cutoff is not None:
        for i, g in enumerate(grid):
            if g < cutoff:
                first_post_cutoff_idx = i + 1

    anchor_idx = max(last_filled_idx + 1, first_post_cutoff_idx, 0)
    next_due = grid[anchor_idx] if anchor_idx < len(grid) else _add_months(grid[-1], max(1, cycle_months or 1))

    return {
        'periods': list(zip(grid, filled)),
        'next_due': next_due,
        'filled_count': last_filled_idx + 1,
    }


def next_due_date(
    lease_start: Optional[date],
    cycle_months: int,
    pay_dates: Sequence[date],
    as_of: date,
    cutoff: Optional[date] = None,
) -> Optional[date]:
    """应收日（起租日网格口径）。"""
    return grid_status(lease_start, cycle_months, pay_dates, as_of, cutoff)['next_due']


def days_until_due(
    lease_start: Optional[date],
    cycle_months: int,
    pay_dates: Sequence[date],
    as_of: date,
    cutoff: Optional[date] = None,
) -> Optional[int]:
    """距离应收日天数；负数 = 已欠租天数。"""
    nd = next_due_date(lease_start, cycle_months, pay_dates, as_of, cutoff)
    return (nd - as_of).days if nd else None


def is_paid_through(
    lease_start: Optional[date],
    cycle_months: int,
    pay_dates: Sequence[date],
    as_of: date,
    cutoff: Optional[date] = None,
) -> bool:
    """截至 as_of 本期是否已收（应收日在未来或无租约信息视为已结清）。"""
    nd = next_due_date(lease_start, cycle_months, pay_dates, as_of, cutoff)
    return nd is None or nd > as_of
