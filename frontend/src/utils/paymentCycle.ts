/**
 * 季度付/半年付房间：判断当前是否应收房租
 *
 * 核心逻辑：计算下次到期日（lease_start + cycle个月），
 * 检查是否有rent payment在该到期日±14天内。
 * 没有 → 应收房租（includeRent=true）
 * 有 → 已付，不收（includeRent=false）
 *
 * 与后端 _has_paid_for_target_cycle 逻辑一致。
 */

interface RoomLike {
  id?: number
  room_id?: number
  payment_cycle?: number | null
  lease_start?: string | null
}

interface PaymentLike {
  room_id: number
  payment_type: string
  payment_date: string
  status?: string
}

export function shouldIncludeRent(
  room: RoomLike,
  payments: PaymentLike[]
): boolean {
  const cycle = Math.max(1, Number(room.payment_cycle || 1))
  if (cycle <= 1) return true // 月付永远包含房租

  // 兼容 MergedReading（无 id 只有 room_id）：表格行数据也走同一判断
  const roomId = (room as any).id ?? (room as any).room_id

  const leaseStart = room.lease_start ? new Date(room.lease_start) : null
  if (!leaseStart) return true // 无租约开始日，默认包含

  // 计算当前周期到期日：从lease_start开始，每次加cycle个月，
  // 取最后一个 <= 今天的到期日（即当前正在履行的周期的起租日）
  // 注意：不能检查"下次到期日"——季度付提前交租后（如8/1交了8-11月的房租），
  // 下次到期日（11/2）±14天内自然没有支付，会误判"未付"导致房租重复计入
  // （2026-09-27 102-2 事故：8-01已交4650，9-27录水电时又把房租算进账单）
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  let currentDue = new Date(leaseStart)
  if (currentDue > today) return true // 租约尚未开始，视作不需收租
  while (true) {
    const next = new Date(currentDue)
    next.setMonth(next.getMonth() + cycle)
    if (next > today) break
    currentDue = next
  }

  // 检查是否有rent payment在当前周期到期日±14天内
  const windowMs = 14 * 24 * 60 * 60 * 1000
  const hasPaymentForCycle = payments.some(p =>
    p.room_id === roomId &&
    p.payment_type === 'rent' &&
    p.status !== 'cancelled' &&
    p.payment_date &&
    Math.abs(new Date(p.payment_date).getTime() - currentDue.getTime()) <= windowMs
  )

  return !hasPaymentForCycle
}
