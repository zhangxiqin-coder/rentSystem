/**
 * 收租网格引擎（v5 起租日网格，2026-10-02）——与后端 app/utils/lease_grid.py 同构
 *
 * 口径（用户裁决 2026-10-02）："逾期标准是房租起租日那天算"——
 * 应收日从 lease_start 按付款周期推网格，付款不改变期界。
 *
 * 规则：
 * - 期界：G0=lease_start，G(k+1)=Gk+cycle月（月末溢出回退到月末）。
 * - 付款分配（最晚兼容期）：付款落在 [期初-14天, 下期初) 内抵付该期；
 *   若付款落在"下期初前14天内"→ 优先抵付下期（租客惯常提前2-5天预付，
 *   e.g. 10-02付的钱是给10-04那期的）。
 * - 应收日 = 最后已付期+1 的期初；无实付 → lease_start。
 *
 * 历史：
 * - v3 ±14天固定窗口：收款日漂移>14天必误判（2-2501-A 事故）。
 * - v4 支付锚定（付款日X覆盖[X,X+cycle月)）：应收日随付款日漂移，
 *   2026-10-02 用户否决；且月付被排除（302-4 刚交完仍显示"即将到期"）。
 */

interface RoomLike {
  id?: number
  room_id?: number
  payment_cycle?: number | null
  lease_start?: string | null
  status?: string | null
}

interface PaymentLike {
  room_id: number
  payment_type: string
  payment_date: string
  status?: string
}

/** 解析 YYYY-MM-DD 为本地零点日期（避免UTC时区偏移） */
export function parseDay(s: string): Date {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s)
  return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : new Date(s)
}

/** 加N个月（对齐后端 dateutil relativedelta：月末溢出回退到月末） */
export function addMonths(d: Date, months: number): Date {
  const r = new Date(d.getTime())
  const day = r.getDate()
  r.setMonth(r.getMonth() + months)
  if (r.getDate() < day) {
    r.setDate(0)
  }
  return r
}

const EARLY_PAY_DAYS = 14

/** 付款日 p 是否落在第 idx 期窗口 [期初-14天, 下期初) 内（或提前抵付下期） */
function payFillsCycle(p: Date, grid: Date[], idx: number): boolean {
  const g = grid[idx]
  const next = grid[idx + 1]
  const lo = new Date(g.getTime())
  lo.setDate(lo.getDate() - EARLY_PAY_DAYS)
  if (p < lo) return false
  if (next) {
    // 付款落在下期初前14天内 → 优先抵付下期（预付惯例）
    const nextEarly = new Date(next.getTime())
    nextEarly.setDate(nextEarly.getDate() - EARLY_PAY_DAYS)
    if (p >= nextEarly) return false
    return true
  }
  return true // 最后一期无上界
}

/**
 * 网格状态：返回最后一次付款所抵付的期 index（-1=无有效付款）。
 * 分配策略与后端 lease_grid.allocate_payments（最晚兼容期）一致。
 */
function lastFilledIndex(leaseStart: Date, cycle: number, payDates: Date[]): number {
  // 生成覆盖所有付款+今天的网格
  let lastPay = leaseStart
  for (const p of payDates) if (p > lastPay) lastPay = p
  const grid: Date[] = [leaseStart]
  while (grid[grid.length - 1] <= lastPay) {
    grid.push(addMonths(grid[grid.length - 1], cycle))
  }
  grid.push(addMonths(grid[grid.length - 1], cycle)) // 保证最后一期窗口完整

  let lastIdx = -1
  for (const p of payDates) {
    // 找该付款能抵付的最晚期（从后往前找第一个满足窗口的）
    for (let idx = grid.length - 1; idx >= 0; idx--) {
      if (idx <= lastIdx) break // 只能填 lastIdx 之后的期（顺序分配）
      if (payFillsCycle(p, grid, idx)) {
        lastIdx = idx
        break
      }
    }
  }
  return lastIdx
}

/**
 * 判断当前应收期是否已付（含月付）。
 * 已付 = 最后已付期覆盖今天（今天 < 该期下期初）。
 */
export function shouldIncludeRent(
  room: RoomLike,
  payments: PaymentLike[]
): boolean {
  const cycle = Math.max(1, Number(room.payment_cycle || 1))

  // 兼容 MergedReading（无 id 只有 room_id）
  const roomId = (room as any).id ?? (room as any).room_id

  // 转租空窗期/空置房间（2026-10-28 302-1 案例）：老租客已退、新租约
  // 未来才生效，此刻无在租租客，水电结算只含水电，不含房租。
  // status 未携带（旧调用方/MergedReading 缺字段）时保持原行为。
  if (room.status && room.status !== 'occupied') return false

  if (!room.lease_start) return true // 无租约开始日，默认包含

  const leaseStart = parseDay(room.lease_start)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  if (leaseStart > today) return true // 租约尚未开始，视作不需收租

  // 本租约期内有效 rent 实付日（换租隔离）
  const earliest = new Date(leaseStart.getTime())
  earliest.setDate(earliest.getDate() - EARLY_PAY_DAYS)

  const payDates: Date[] = []
  for (const p of payments) {
    if (p.room_id !== roomId) continue
    if (p.payment_type !== 'rent') continue
    if (p.status === 'cancelled') continue
    if (!p.payment_date) continue
    const d = parseDay(p.payment_date)
    if (d < earliest) continue
    payDates.push(d)
  }
  payDates.sort((a, b) => a.getTime() - b.getTime())

  if (payDates.length === 0) return true // 从未收租 → 应收首期

  const lastIdx = lastFilledIndex(leaseStart, cycle, payDates)

  // 应收日 = 最后已付期+1 的期初；已付 = 应收日超出提前收租窗口。
  // ⚠️ 应收日在未来但 ≤14 天内（EARLY_PAY_DAYS）也算该收——租客惯常
  // 提前 2-5 天预付（102-2 案例：11-02 到期，10-28 录水电时催租消息
  // 必须含下季度房租；旧逻辑判"已付"把房租行吃掉了）。
  const grid = [leaseStart]
  for (let i = 0; i < lastIdx + 1; i++) grid.push(addMonths(grid[i], cycle))
  const nextDue = grid[lastIdx + 1]
  const daysUntil = Math.floor((nextDue.getTime() - today.getTime()) / 86400000)
  // 含房租 = 应收日已到（daysUntil<=0）或进入提前收租窗口（<=14天）。
  // ⚠️ 方向别写反：窗口内（含已逾期）→ true；窗口外（还远）→ false。
  return daysUntil <= EARLY_PAY_DAYS
}

/**
 * 下次应收日（起租日网格上"最后已付期+1"），无 lease_start 返回 null。
 * 与后端 lease_grid.next_due_date 同构。
 */
export function getNextGridDue(
  room: RoomLike,
  payments: PaymentLike[]
): Date | null {
  const cycle = Math.max(1, Number(room.payment_cycle || 1))
  if (!room.lease_start) return null

  const roomId = (room as any).id ?? (room as any).room_id
  const leaseStart = parseDay(room.lease_start)
  const earliest = new Date(leaseStart.getTime())
  earliest.setDate(earliest.getDate() - EARLY_PAY_DAYS)

  const payDates: Date[] = []
  for (const p of payments) {
    if (p.room_id !== roomId) continue
    if (p.payment_type !== 'rent') continue
    if (p.status === 'cancelled') continue
    if (!p.payment_date) continue
    const d = parseDay(p.payment_date)
    if (d < earliest) continue
    payDates.push(d)
  }
  payDates.sort((a, b) => a.getTime() - b.getTime())

  if (payDates.length === 0) return leaseStart

  const lastIdx = lastFilledIndex(leaseStart, cycle, payDates)
  const grid = [leaseStart]
  for (let i = 0; i < lastIdx + 1; i++) grid.push(addMonths(grid[i], cycle))
  return grid[lastIdx + 1]
}

/**
 * 房租覆盖周期（预收下一期口径，2026-10-06）。
 *
 * 本次收的房租覆盖"下一个未付期"：在起租日网格上取
 * getNextGridDue（最后已付期+1 的期初）为 period_start，
 * 期末 = 期初 + cycle 月 - 1 天。
 *
 * 修复前 bug：弹窗取"今天所在期"（完全不看付款记录）——
 * 租客已预付到 10-09 时仍显示 09-10~10-09（已收过的期）。
 * 正确示例（102-4，2026-10-06）：9-08 已付至 10-09，
 * 本次收的覆盖 2026-10-10 ~ 2026-11-09。
 *
 * 无 lease_start 返回 null；从未收租返回首期（lease_start 起）。
 */
export function getCoveragePeriod(
  room: RoomLike,
  payments: PaymentLike[]
): { start: string; end: string } | null {
  if (!room.lease_start) return null
  const cycle = Math.max(1, Number(room.payment_cycle || 1))

  const due = getNextGridDue(room, payments)
  if (!due) return null

  const start = due
  const nextStart = addMonths(start, cycle)
  const end = new Date(nextStart.getTime() - 86400000)

  const fmt = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return { start: fmt(start), end: fmt(end) }
}

/**
 * 月度收租判定（v5 网格，PaymentsView 收租概况用）。
 *
 * 对目标月 [year, month]（month 为 0-based）判定该房间：
 * - 'skipped'：该月不含网格期初（非周期月/租期未开始/豁免期前）或无租约信息
 * - 'paid'：该月期初所在期已由付款覆盖
 * - 'unpaid'：该月期初所在期未付
 *
 * 与后端 lease_grid 月度口径同构：期初落在该月即"该月应收"。
 */
export function getMonthGridStatus(
  room: RoomLike,
  payments: PaymentLike[],
  year: number,
  month: number, // 0-based
  cutoffDay?: Date // 豁免线：期初早于此线不追讨（可选）
): { kind: 'paid' | 'unpaid' | 'skipped'; reason?: string; dueDay?: number } {
  const cycle = Math.max(1, Number(room.payment_cycle || 1))
  const roomId = (room as any).id ?? (room as any).room_id

  if (!room.lease_start) return { kind: 'skipped', reason: '无租期信息' }

  const leaseStart = parseDay(room.lease_start)
  const monthStart = new Date(year, month, 1)
  const monthEnd = new Date(year, month + 1, 0) // 月末

  if (leaseStart > monthEnd) return { kind: 'skipped', reason: '租期未开始' }

  // 找落在该月内的网格期初
  let g = new Date(leaseStart.getTime())
  while (g < monthStart) g = addMonths(g, cycle)
  if (g > monthEnd) {
    // 该月无期初 → 下次收租月
    const next = g
    return { kind: 'skipped', reason: `下次${next.getMonth() + 1}月收` }
  }

  // g = 该月的期初（应收日）
  if (cutoffDay && g < cutoffDay) return { kind: 'skipped', reason: '豁免日期之前' }

  // 该期是否已付：找抵付该期的付款
  const earliest = new Date(g.getTime())
  earliest.setDate(earliest.getDate() - EARLY_PAY_DAYS)
  const next = addMonths(g, cycle)
  const nextEarly = new Date(next.getTime())
  nextEarly.setDate(nextEarly.getDate() - EARLY_PAY_DAYS)

  for (const p of payments) {
    if (p.room_id !== roomId) continue
    if (p.payment_type !== 'rent') continue
    if (p.status === 'cancelled') continue
    if (!p.payment_date) continue
    const d = parseDay(p.payment_date)
    if (d < earliest) continue
    if (d >= next) continue // 超出该期窗口（更晚的付款抵付更晚的期）
    // d ∈ [期初-14, 下期初)。若 d ≥ nextEarly → 抵付下期，不算本期
    if (d >= nextEarly) continue
    return { kind: 'paid', dueDay: g.getDate() }
  }
  return { kind: 'unpaid', dueDay: g.getDate() }
}
