import { computed, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { utilityApi } from '@/api/utility'
import { mergeReadings, type MergedReading } from '@/composables/useMergedReadings'
import { useOverdueConfig } from '@/composables/useOverdueConfig'
import type { UtilityReading, Room, Payment as RentPayment } from '@/types'

export function useOverdueManagement(deps: {
  allRooms: Ref<Room[]>
  payments: Ref<RentPayment[]>
  allReadings: Ref<UtilityReading[]>
  roomOptions: Ref<Room[]>
  formatAmount: (value: number, currency?: string) => string
  mergedReadings: Ref<MergedReading[]>
  showPaymentDialog: (row: MergedReading) => void
}) {
  const {
    allRooms,
    payments,
    allReadings,
    roomOptions,
    formatAmount,
    mergedReadings,
    showPaymentDialog,
  } = deps

  const { overdueCutoffDate, advanceRentDays, expiringDays, recentPaymentDays, recentReadingDays } = useOverdueConfig()

  // 性能优化：缓存合并结果，避免重复计算
  const mergedAllReadings = computed(() =>
    mergeReadings(allReadings.value, roomOptions.value)
  )

  const latestUnpaidUtilityAmountByRoom = computed(() => {
    const roomAmountMap = new Map<number, number>()
    const mergedList = mergedAllReadings.value

    // mergeReadings 已按日期倒序，首条即最近记录
    mergedList.forEach(item => {
      if (roomAmountMap.has(item.room_id)) return
      if (item.is_paid) return
      const utilityAmount =
        Number(item.water_reading?.amount || 0) +
        Number(item.electricity_reading?.amount || 0)
      roomAmountMap.set(item.room_id, utilityAmount)
    })

    return roomAmountMap
  })

  const overdueRooms = computed(() => {
    const overdue: Array<{
      room: Room
      overdueDays: number
      overdueAmount: number
      lastPaymentDate: string
      nextPaymentDate: string
    }> = []

    allRooms.value.forEach(room => {
      if (room.status !== 'occupied') return
      if (hasPaidThisMonth(room)) return
      if (hasRecentRentPayment(room.id)) return
      // 租期未开始的不纳入逾期
      if (room.lease_start && toStartOfDay(new Date(room.lease_start)) > toStartOfDay(new Date())) return

      const { targetDue } = getPaymentDueContext(room)

      const nextPaymentDate = getNextPaymentDate(room)
      const nextPaymentDays = getNextPaymentDays(room)

      // 如果距离应交日 <= 提前收租天数，计入欠租管理
      if (nextPaymentDays <= advanceRentDays.value) {
        const overdueDays = Math.max(0, -nextPaymentDays)
        const lastPaymentDate = room.last_payment_date || room.lease_start

        // 计算欠费总额（房租 + 最近未结清水电）
        const utilityAmount = latestUnpaidUtilityAmountByRoom.value.get(room.id) || 0
        const cycle = Math.max(1, Number(room.payment_cycle || 1))
        const overdueAmount = Number(room.monthly_rent || 0) * cycle + utilityAmount

        overdue.push({
          room,
          overdueDays,
          overdueAmount,
          lastPaymentDate: formatDate(lastPaymentDate!),
          nextPaymentDate: formatDate(nextPaymentDate)
        })
      }
    })

    // 按欠租天数排序（天数越多越靠前）
    return overdue.sort((a, b) => b.overdueDays - a.overdueDays)
  })

  // 即将到期房间
  const expiringRooms = computed(() => {
    const today = toStartOfDay(new Date())
    return allRooms.value
      .filter(room => room.status === 'occupied')
      .filter(room => !hasPaidThisMonth(room))
      .filter(room => !hasRecentRentPayment(room.id))
      .filter(room => !room.lease_start || toStartOfDay(new Date(room.lease_start)) <= today)
      .filter(room => {
        const days = getNextPaymentDays(room)
        return days > advanceRentDays.value && days <= expiringDays.value
      })
      .sort((a, b) => getNextPaymentDays(a) - getNextPaymentDays(b))
  })

  const getRecentUnpaidReadingForRoom = (roomId: number): MergedReading | undefined => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)

    return mergedAllReadings.value
      .filter(item => item.room_id === roomId && !item.is_paid && (item.water_reading || item.electricity_reading))
      .filter(item => {
        const readingDate = new Date(item.reading_date)
        readingDate.setHours(0, 0, 0, 0)
        const diffDays = Math.floor((today.getTime() - readingDate.getTime()) / (1000 * 60 * 60 * 24))
        return diffDays >= 0 && diffDays <= recentReadingDays.value
      })
      .sort((a, b) => new Date(b.reading_date).getTime() - new Date(a.reading_date).getTime())[0]
  }

  const canMarkExpiringRoomPaid = (room: Room) => {
    return !!getRecentUnpaidReadingForRoom(room.id)
  }

  const markExpiringRoomPaid = (room: Room) => {
    const row = getRecentUnpaidReadingForRoom(room.id)
    if (!row) {
      ElMessage.warning(`房间 ${room.room_number} 暂无近${recentReadingDays.value}天未收租的水电记录`)
      return
    }
    showPaymentDialog(row)
  }

  // 计算距离到期天数
  const getDaysDiff = (leaseEnd: string) => {
    const today = new Date()
    const endDate = new Date(leaseEnd)
    const diff = Math.ceil((endDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
    return Math.max(0, diff)
  }

  // 格式化日期
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    })
  }

  // 获取最近一次收租明细文本（用于催租消息）
  const getLatestCollectionDetailText = async (room: Room) => {
    try {
      const res = await utilityApi.getReadingsByRoom(room.id, { page: 1, size: 50 })
      const mergedList = mergeReadings(res.data.items || [], roomOptions.value)
      const latest = mergedList[0]
      const cycle = Math.max(1, Number(room.payment_cycle || 1))
      const rentDue = Number(room.monthly_rent || 0) * cycle
      const rentLabel = cycle > 1 ? `房租（${cycle}个月）` : '房租'
      if (!latest) return `【${room.room_number} 收租明细】\n抄表日期：-\n\n💰 合计：${formatAmount(rentDue)}\n🏠 ${rentLabel}：${formatAmount(rentDue)}\n💧 水费：暂无抄表记录\n⚡ 电费：暂无抄表记录`

      const date = new Date(latest.reading_date).toLocaleDateString('zh-CN')
      const rent = rentDue
      const water = latest.water_reading
      const electric = latest.electricity_reading

      const waterPrev = Number(water?.previous_reading || 0)
      const waterCurr = Number(water?.reading || 0)
      const waterUsage = Number(water?.usage ?? Math.max(0, waterCurr - waterPrev))
      const waterRate = Number(water?.rate_used ?? room.water_rate ?? 0)
      const waterAmount = Number(water?.amount || 0)

      const elecPrev = Number(electric?.previous_reading || 0)
      const elecCurr = Number(electric?.reading || 0)
      const elecUsage = Number(electric?.usage ?? Math.max(0, elecCurr - elecPrev))
      const elecRate = Number(electric?.rate_used ?? room.electricity_rate ?? 0)
      const elecAmount = Number(electric?.amount || 0)

      const total = rent + waterAmount + elecAmount

      const waterLine = water
        ? `💧 水费：${waterPrev}→${waterCurr}（用量${waterUsage}吨 × ¥${waterRate}/吨 = ${formatAmount(waterAmount)}）`
        : '💧 水费：暂无抄表记录'
      const electricLine = electric
        ? `⚡ 电费：${elecPrev}→${elecCurr}（用量${elecUsage}度 × ¥${elecRate}/度 = ${formatAmount(elecAmount)}）`
        : '⚡ 电费：暂无抄表记录'

      return `【${room.room_number} 收租明细】\n抄表日期：${date}\n\n💰 合计：${formatAmount(total)}\n🏠 ${rentLabel}：${formatAmount(rent)}\n${waterLine}\n${electricLine}`
    } catch {
      const cycle = Math.max(1, Number(room.payment_cycle || 1))
      const rentDue = Number(room.monthly_rent || 0) * cycle
      const rentLabel = cycle > 1 ? `房租（${cycle}个月）` : '房租'
      return `【${room.room_number} 收租明细】\n抄表日期：-\n\n💰 合计：${formatAmount(rentDue)}\n🏠 ${rentLabel}：${formatAmount(rentDue)}\n💧 水费：获取失败\n⚡ 电费：获取失败`
    }
  }

  // 一键催租
  const sendReminder = async (room: Room, type: 'overdue' | 'upcoming') => {
    try {
      const message = await getLatestCollectionDetailText(room)

      // 复制到剪贴板
      await navigator.clipboard.writeText(message)
      ElMessage.success('催租消息已复制到剪贴板，请发送给租客')
    } catch (error) {
      console.error('Failed to send reminder:', error)
      ElMessage.error('发送催租消息失败')
    }
  }

  const toStartOfDay = (date: Date) => {
    const d = new Date(date)
    d.setHours(0, 0, 0, 0)
    return d
  }

  const hasRecentRentPayment = (roomId: number) => {
    const today = toStartOfDay(new Date())
    return payments.value.some(payment => {
      if (payment.room_id !== roomId) return false
      if (!payment.payment_date) return false
      if (payment.status === 'cancelled') return false
      if (payment.payment_type === 'refund') return false

      const paymentDate = toStartOfDay(new Date(payment.payment_date))
      const diffDays = Math.floor((today.getTime() - paymentDate.getTime()) / (1000 * 60 * 60 * 24))
      return diffDays >= 0 && diffDays <= recentPaymentDays.value
    })
  }

  const hasRentPaymentAfter = (roomId: number, afterDate: Date) => {
    return payments.value.some(payment => {
      if (payment.room_id !== roomId) return false
      if (!payment.payment_date) return false
      if (payment.status === 'cancelled') return false
      if (payment.payment_type !== 'rent') return false
      return toStartOfDay(new Date(payment.payment_date)) > afterDate
    })
  }

  const hasAnyRentPayment = (roomId: number) => {
    return payments.value.some(payment => {
      if (payment.room_id !== roomId) return false
      if (payment.status === 'cancelled') return false
      if (payment.payment_type !== 'rent') return false
      return true
    })
  }

  const isSameMonth = (a: Date, b: Date) => {
    return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth()
  }

  const hasPaidThisMonth = (room: Room) => {
    const today = toStartOfDay(new Date())

    // 历史导入场景：没有 payment 记录，但 last_payment_date 已更新，视为本月已收
    if (room.last_payment_date) {
      const lastPaid = toStartOfDay(new Date(room.last_payment_date))
      if (isSameMonth(lastPaid, today)) return true
    }

    return payments.value.some(payment => {
      if (payment.room_id !== room.id) return false
      if (!payment.payment_date) return false
      if (payment.status === 'cancelled') return false
      if (payment.payment_type === 'refund') return false
      const paymentDate = toStartOfDay(new Date(payment.payment_date))
      return isSameMonth(paymentDate, today)
    })
  }

  const buildDueDate = (year: number, month: number, day: number) => {
    const daysInMonth = new Date(year, month + 1, 0).getDate()
    return new Date(year, month, Math.min(day, daysInMonth))
  }

  const addMonthsByDueDay = (base: Date, months: number, dueDay: number) => {
    const d = new Date(base)
    d.setDate(1)
    d.setMonth(d.getMonth() + months)
    const adjusted = buildDueDate(d.getFullYear(), d.getMonth(), dueDay)
    adjusted.setHours(0, 0, 0, 0)
    return adjusted
  }

  const getPaymentDueContext = (room: Room) => {
    const today = toStartOfDay(new Date())
    const cutoffTs = new Date(overdueCutoffDate.value + 'T00:00:00').getTime()
    const cycleMonths = Math.max(1, Number(room.payment_cycle || 1))
    const anchorSource = room.lease_start || room.last_payment_date || new Date().toISOString().split('T')[0]
    const anchorDate = toStartOfDay(new Date(anchorSource))
    const dueDay = anchorDate.getDate()

    let cursor = buildDueDate(anchorDate.getFullYear(), anchorDate.getMonth(), dueDay)
    cursor = toStartOfDay(cursor)
    let previousDue: Date | null = null
    let prevPrevDue: Date | null = null

    while (cursor <= today) {
      prevPrevDue = previousDue
      previousDue = cursor
      cursor = addMonthsByDueDay(cursor, cycleMonths, dueDay)
    }

    const nextDue = cursor
    const currentCycleDue = previousDue || buildDueDate(today.getFullYear(), today.getMonth(), dueDay)
    const currentCycleDueStart = toStartOfDay(currentCycleDue)
    const lastPaid = room.last_payment_date ? toStartOfDay(new Date(room.last_payment_date)) : null
    const billingCycleStart = prevPrevDue ? toStartOfDay(prevPrevDue) : currentCycleDueStart
    const paidByRentRecord = prevPrevDue
      ? hasRentPaymentAfter(room.id, toStartOfDay(prevPrevDue))
      : hasAnyRentPayment(room.id)
    const paidCurrentCycle =
      hasRecentRentPayment(room.id) ||
      !!(lastPaid && lastPaid > billingCycleStart) ||
      paidByRentRecord ||
      (room.room_number !== '502-2' && currentCycleDueStart.getTime() < cutoffTs)

    const targetDue = paidCurrentCycle ? nextDue : currentCycleDueStart
    const daysToDue = Math.ceil((targetDue.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))

    return { targetDue, nextDue, currentCycleDue: currentCycleDueStart, paidCurrentCycle, daysToDue }
  }

  // 计算收租目标日期（当前周期未收则显示当前应交日；已收则显示下一次应交日）
  const getNextPaymentDate = (room: Room) => {
    const { targetDue } = getPaymentDueContext(room)
    return targetDue.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    })
  }

  // 计算距离收租目标日期的天数（正数=未到期，0=当天，负数=已逾期）
  const getNextPaymentDays = (room: Room) => {
    return getPaymentDueContext(room).daysToDue
  }

  return {
    advanceRentDays,
    latestUnpaidUtilityAmountByRoom,
    overdueRooms,
    expiringRooms,
    recentReadingDays,
    getRecentUnpaidReadingForRoom,
    canMarkExpiringRoomPaid,
    markExpiringRoomPaid,
    getDaysDiff,
    formatDate,
    getLatestCollectionDetailText,
    sendReminder,
    hasPaidThisMonth,
    hasRecentRentPayment,
    toStartOfDay,
    isSameMonth,
    buildDueDate,
    addMonthsByDueDay,
    getPaymentDueContext,
    getNextPaymentDate,
    getNextPaymentDays,
  }
}
