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

  const leaseStart = room.lease_start ? new Date(room.lease_start) : null
  if (!leaseStart) return true // 无租约开始日，默认包含

  // 计算下次到期日：从lease_start开始，每次加cycle个月，直到超过今天
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  let nextDue = new Date(leaseStart)
  while (nextDue <= today) {
    nextDue.setMonth(nextDue.getMonth() + cycle)
  }

  // 检查是否有rent payment在到期日±14天内
  const roomId = room.id
  const windowMs = 14 * 24 * 60 * 60 * 1000
  const hasPaymentForCycle = payments.some(p =>
    p.room_id === roomId &&
    p.payment_type === 'rent' &&
    p.status !== 'cancelled' &&
    p.payment_date &&
    Math.abs(new Date(p.payment_date).getTime() - nextDue.getTime()) <= windowMs
  )

  return !hasPaymentForCycle
}
