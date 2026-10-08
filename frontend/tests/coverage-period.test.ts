// 验证 getCoveragePeriod（v5 网格预收口径）
// 运行：cd frontend && npx tsc --strict --noEmit --target es2020 --moduleResolution bundler --module esnext tests/coverage-period.test.ts
import { getCoveragePeriod, getNextGridDue } from '../src/utils/paymentCycle.ts'

let pass = 0, fail = 0
function eq(name: string, got: any, want: any) {
  const ok = JSON.stringify(got) === JSON.stringify(want)
  if (ok) { pass++; console.log(`  ✓ ${name}`) }
  else { fail++; console.log(`  ✗ ${name}\n      got  ${JSON.stringify(got)}\n      want ${JSON.stringify(want)}`) }
}

// ── 用例1：102-4 真实数据 ──
// lease 2026-03-10，月付，付款 04-07..09-08 共6笔（各抵付一期）
// 最后已付期 = 第6期 [09-10, 10-10)，下一期 = [10-10, 11-10) → 覆盖 10-10 ~ 11-09
{
  const room = { room_id: 31, payment_cycle: 1, lease_start: '2026-03-10' }
  const pays = ['2026-04-07','2026-05-07','2026-06-07','2026-07-08','2026-08-07','2026-09-08']
    .map(d => ({ room_id: 31, payment_type: 'rent', payment_date: d, status: 'completed' }))
  eq('102-4 覆盖周期', getCoveragePeriod(room, pays), { start: '2026-10-10', end: '2026-11-09' })
  eq('102-4 下次应收日', fmt(getNextGridDue(room, pays)), '2026-10-10')
}

// ── 用例2：从未收租 → 首期 ──
{
  const room = { room_id: 1, payment_cycle: 1, lease_start: '2026-06-15' }
  eq('从未收租', getCoveragePeriod(room, []), { start: '2026-06-15', end: '2026-07-14' })
}

// ── 用例3：季付（cycle=3），9-05 起租，10-02 已付首期 → 下期 12-05~03-04 ──
{
  const room = { room_id: 19, payment_cycle: 3, lease_start: '2026-09-05' }
  const pays = [{ room_id: 19, payment_type: 'rent', payment_date: '2026-10-02', status: 'completed' }]
  eq('季付下期', getCoveragePeriod(room, pays), { start: '2026-12-05', end: '2027-03-04' })
}

// ── 用例4：月末日（1-31 起租，2月回退后日漂移）──
// 网格：1-31, 2-28(回退), 3-28, 4-28...（dateutil/js 都不记忆31日锚，
// 前后端 addMonths/relativedelta 迭代行为一致）
// 2-28 付款抵付第2期(2-28起)，下一期 = 3-28 ~ 4-27
{
  const room = { room_id: 2, payment_cycle: 1, lease_start: '2026-01-31' }
  const pays = [{ room_id: 2, payment_type: 'rent', payment_date: '2026-02-28', status: 'completed' }]
  eq('月末回退', getCoveragePeriod(room, pays), { start: '2026-03-28', end: '2026-04-27' })
}

// ── 用例5：换租隔离（旧租客付款早于 lease_start-14 被跳过）──
{
  const room = { room_id: 5, payment_cycle: 1, lease_start: '2026-09-10' }
  const pays = [
    { room_id: 5, payment_type: 'rent', payment_date: '2026-08-08', status: 'completed' }, // 旧租客
    { room_id: 5, payment_type: 'rent', payment_date: '2026-09-08', status: 'completed' }, // 新租客预付
  ]
  eq('换租隔离', getCoveragePeriod(room, pays), { start: '2026-10-10', end: '2026-11-09' })
}

// ── 用例6：cancelled 付款不算 ──
{
  const room = { room_id: 6, payment_cycle: 1, lease_start: '2026-09-10' }
  const pays = [{ room_id: 6, payment_type: 'rent', payment_date: '2026-09-08', status: 'cancelled' }]
  eq('cancelled不算', getCoveragePeriod(room, pays), { start: '2026-09-10', end: '2026-10-09' })
}

function fmt(d: Date | null): string {
  if (!d) return 'null'
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
}

console.log(`\n${pass} passed, ${fail} failed`)
if (fail > 0) throw new Error(`${fail} test(s) failed`)
