import { computed, ref, watch, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { utilityApi } from '@/api/utility'
import { statisticsApi } from '@/api/statistics'
import { mergeReadings, type MergedReading } from '@/composables/useMergedReadings'
import { useOverdueConfig } from '@/composables/useOverdueConfig'
import type { UtilityReading, Room, Payment as RentPayment } from '@/types'

export function useOverdueManagement(deps: {
  allRooms: Ref<Room[]>
  payments: Ref<RentPayment[]>
  allReadings: Ref<UtilityReading[]>
  roomOptions: Ref<Room[]>
  formatAmount: (value: number, currency?: string) => string
  formatAmountForNotification: (value: number, currency?: string) => string
  mergedReadings: Ref<MergedReading[]>
  showPaymentDialog: (row: MergedReading) => void
}) {
  const {
    allRooms,
    payments,
    allReadings,
    roomOptions,
    formatAmount,
    formatAmountForNotification,
    mergedReadings,
    showPaymentDialog,
  } = deps

  const { overdueCutoffDate, advanceRentDays, expiringDays, recentPaymentDays, recentReadingDays } = useOverdueConfig()

  // 后端逾期/到期数据（取代前端本地计算）
  const overdueRoomsFromBackend = ref<Array<{
    room_id: number
    room_number: string
    tenant_name: string | null
    overdue_days: number
    overdue_amount: number
    last_payment_date: string | null
    next_payment_date: string | null
    monthly_rent: number
    payment_cycle: number
  }>>([])

  const expiringRoomsFromBackend = ref<Array<{
    room_id: number
    room_number: string
    tenant_name: string | null
    days_until_payment: number
    monthly_rent: number
    payment_cycle: number
  }>>([])

  const backendLoading = ref(false)

  // 从后端API获取逾期/到期数据
  const fetchPaymentStatus = async () => {
    backendLoading.value = true
    try {
      const res = await statisticsApi.getRentPaymentStatus({
        overdue_cutoff_date: overdueCutoffDate.value,
        advance_rent_days: advanceRentDays.value,
        expiring_days: expiringDays.value,
      })
      // axios res.data 直接是后端返回的数据
      const data = res.data as any
      overdueRoomsFromBackend.value = data.overdue_rooms || []
      expiringRoomsFromBackend.value = data.expiring_rooms || []
    } catch (err) {
      console.error('[useOverdueManagement] 后端API获取失败，使用本地计算:', err)
      // 失败时触发本地计算
      loadFromLocal()
    } finally {
      backendLoading.value = false
    }
  }

  // 本地计算（回退方案）
  const loadFromLocal = () => {
    const localOverdue = computeLocalOverdue()
    const localExpiring = computeLocalExpiring()
    overdueRoomsFromBackend.value = localOverdue.map(item => ({
      room_id: item.room.id,
      room_number: item.room.room_number,
      tenant_name: item.room.tenant_name || null,
      overdue_days: item.overdueDays,
      overdue_amount: item.overdueAmount,
      last_payment_date: item.lastPaymentDate,
      next_payment_date: item.nextPaymentDate,
      monthly_rent: Number(item.room.monthly_rent || 0),
      payment_cycle: item.room.payment_cycle || 1,
    }))
    expiringRoomsFromBackend.value = localExpiring.map(room => ({
      room_id: room.id,
      room_number: room.room_number,
      tenant_name: room.tenant_name || null,
      days_until_payment: getNextPaymentDays(room),
      monthly_rent: Number(room.monthly_rent || 0),
      payment_cycle: room.payment_cycle || 1,
    }))
  }

  // 当配置变化时重新获取
  watch([overdueCutoffDate, advanceRentDays, expiringDays, payments, allRooms], () => {
    fetchPaymentStatus()
  }, { deep: true })

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

  // 对外暴露的逾期/到期数据（以后端为主）
  const overdueItems = computed(() => {
    return overdueRoomsFromBackend.value.map(item => {
      const room = allRooms.value.find(r => r.id === item.room_id)
      return {
        room: room || { id: item.room_id, room_number: item.room_number } as Room,
        overdueDays: item.overdue_days,
        overdueAmount: item.overdue_amount,
        lastPaymentDate: item.last_payment_date || '',
        nextPaymentDate: item.next_payment_date || '',
      }
    })
  })

  const expiringItems = computed(() => {
    return expiringRoomsFromBackend.value.map(item => {
      const room = allRooms.value.find(r => r.id === item.room_id)
      return room || { id: item.room_id, room_number: item.room_number } as Room
    })
  })

  // 保留兼容原接口
  const overdueRooms = overdueItems
  const expiringRooms = expiringItems

  // ---- 本地计算逻辑（回退用，仅保留关键方法） ----
  const computeLocalOverdue = () => {
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
      if (room.lease_start && toStartOfDay(new Date(room.lease_start)) > toStartOfDay(new Date())) return

      const nextPaymentDays = getNextPaymentDays(room)

      if (nextPaymentDays <= advanceRentDays.value) {
        const overdueDays = Math.max(0, -nextPaymentDays)
        const lastPaymentDate = room.last_payment_date || room.lease_start
        const utilityAmount = latestUnpaidUtilityAmountByRoom.value.get(room.id) || 0
        const cycle = Math.max(1, Number(room.payment_cycle || 1))
        const overdueAmount = Number(room.monthly_rent || 0) * cycle + utilityAmount

        overdue.push({
          room,
          overdueDays,
          overdueAmount,
          lastPaymentDate: formatDate(lastPaymentDate!),
          nextPaymentDate: getNextPaymentDate(room)
        })
      }
    })

    return overdue.sort((a, b) => b.overdueDays - a.overdueDays)
  }

  const computeLocalExpiring = () => {
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
  }

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

  const getRecentReadingForRoom = (roomId: number): MergedReading | undefined => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)

    return mergedAllReadings.value
      .filter(item => item.room_id === roomId)
      .filter(item => {
        const readingDate = new Date(item.reading_date)
        readingDate.setHours(0, 0, 0, 0)
        const diffDays = Math.floor((today.getTime() - readingDate.getTime()) / (1000 * 60 * 60 * 24))
        return diffDays >= 0 && diffDays <= 15
      })
      .sort((a, b) => new Date(b.reading_date).getTime() - new Date(a.reading_date).getTime())[0]
  }

  const canMarkExpiringRoomPaid = (room: Room) => {
    const recentReading = getRecentReadingForRoom(room.id)
    return !!(recentReading && !recentReading.is_paid)
  }

  const markExpiringRoomPaid = (room: Room) => {
    const row = getRecentUnpaidReadingForRoom(room.id)
    if (!row) {
      ElMessage.warning(`房间 ${room.room_number} 暂无近${recentReadingDays.value}天未收租的水电记录`)
      return
    }
    showPaymentDialog(row)
  }

  const getDaysDiff = (leaseEnd: string) => {
    const today = new Date()
    const endDate = new Date(leaseEnd)
    const diff = Math.ceil((endDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
    return Math.max(0, diff)
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    })
  }

  const getLatestCollectionDetailText = async (room: Room) => {
    try {
      const res = await utilityApi.getReadingsByRoom(room.id, { page: 1, size: 50 })
      const mergedList = mergeReadings(res.data.items || [], roomOptions.value)
      const latest = mergedList[0]
      const cycle = Math.max(1, Number(room.payment_cycle || 1))
      const rentDue = Number(room.monthly_rent || 0) * cycle
      const rentLabel = cycle > 1 ? `房租（${cycle}个月）` : '房租'
      if (!latest) return `【${room.room_number} 收租明细】
抄表日期：-

💰 合计：${formatAmountForNotification(rentDue)}
🏠 ${rentLabel}：${formatAmountForNotification(rentDue)}
💧 水费：暂无抄表记录
⚡ 电费：暂无抄表记录`

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
        ? `💧 水费：${waterPrev}→${waterCurr}（用量${waterUsage}吨 × ¥${waterRate}/吨 = ${formatAmountForNotification(waterAmount)}）`
        : '💧 水费：暂无抄表记录'
      const electricLine = electric
        ? `⚡ 电费：${elecPrev}→${elecCurr}（用量${elecUsage}度 × ¥${elecRate}/度 = ${formatAmountForNotification(elecAmount)}）`
        : '⚡ 电费：暂无抄表记录'

      return `【${room.room_number} 收租明细】
抄表日期：${date}

💰 合计：${formatAmountForNotification(total)}
🏠 ${rentLabel}：${formatAmountForNotification(rent)}
${waterLine}
${electricLine}`
    } catch {
      const cycle = Math.max(1, Number(room.payment_cycle || 1))
      const rentDue = Number(room.monthly_rent || 0) * cycle
      const rentLabel = cycle > 1 ? `房租（${cycle}个月）` : '房租'
      return `【${room.room_number} 收租明细】
抄表日期：-

💰 合计：${formatAmountForNotification(rentDue)}
🏠 ${rentLabel}：${formatAmountForNotification(rentDue)}
💧 水费：获取失败
⚡ 电费：获取失败`
    }
  }

  const copyToClipboard = async (text: string): Promise<boolean> => {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text)
        return true
      } catch {
        // Fall through
      }
    }

    const textArea = document.createElement('textarea')
    textArea.value = text
    textArea.style.position = 'fixed'
    textArea.style.left = '-999999px'
    textArea.style.top = '-999999px'
    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()

    try {
      const successful = document.execCommand('copy')
      document.body.removeChild(textArea)
      return successful
    } catch {
      document.body.removeChild(textArea)
      return false
    }
  }

  const sendReminder = async (room: Room, type: 'overdue' | 'upcoming') => {
    try {
      const message = await getLatestCollectionDetailText(room)

      const success = await copyToClipboard(message)
      if (success) {
        ElMessage.success('✅ 催租消息已复制，可直接粘贴发送')
      } else {
        ElMessage.error('复制失败，请手动复制消息')
        console.log('消息内容:', message)
      }
    } catch (error) {
      console.error('Failed to send reminder:', error)
      ElMessage.error('生成催租消息失败')
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
     if (payment.payment_type !== 'rent') return false
     if (payment.payment_type === 'refund') return false
     const paymentDate = toStartOfDay(new Date(payment.payment_date))
     const diffDays = Math.floor((today.getTime() - paymentDate.getTime()) / (1000 * 60 * 60 * 24))
      const room = allRooms.value.find(r => r.id === roomId)
      const cycleMonths = Math.max(1, Number(room?.payment_cycle || 1))
      const thresholdDays = cycleMonths * 30 - 5
      return diffDays >= 0 && diffDays <= thresholdDays
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

    const hasPaymentThisMonth = payments.value.some(payment => {
      if (payment.room_id !== room.id) return false
      if (!payment.payment_date) return false
      if (payment.status === 'cancelled') return false
      if (payment.payment_type !== 'rent') return false
      if (payment.payment_type === 'refund') return false
      const paymentDate = toStartOfDay(new Date(payment.payment_date))
      return isSameMonth(paymentDate, today)
    })

    if (hasPaymentThisMonth) {
      const daysToNext = getNextPaymentDays(room)
      if (daysToNext <= expiringDays.value) {
        return false
      }
      return true
    }

    if (room.last_payment_date) {
      const lastPaid = toStartOfDay(new Date(room.last_payment_date))
      if (isSameMonth(lastPaid, today)) {
        const daysToNext = getNextPaymentDays(room)
        if (daysToNext <= expiringDays.value) {
          return false
        }
        return true
      }
    }

    return false
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
      ? hasRentPaymentAfter(room.id, new Date(currentCycleDueStart.getTime() - 14 * 86400000))
      : hasAnyRentPayment(room.id)
    const paidCurrentCycle =
      hasRecentRentPayment(room.id) ||
      !!(lastPaid && Math.abs((lastPaid.getTime() - currentCycleDueStart.getTime()) / (1000 * 60 * 60 * 24)) <= 14) ||
      paidByRentRecord ||
      (room.room_number !== '502-2' && currentCycleDueStart.getTime() < cutoffTs)

    const targetDue = paidCurrentCycle ? nextDue : currentCycleDueStart
    const daysToDue = Math.ceil((targetDue.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))

    return { targetDue, nextDue, currentCycleDue: currentCycleDueStart, paidCurrentCycle, daysToDue }
  }

  const getNextPaymentDate = (room: Room) => {
    const { targetDue } = getPaymentDueContext(room)
    return targetDue.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    })
  }

  const getNextPaymentDays = (room: Room) => {
    return getPaymentDueContext(room).daysToDue
  }

  return {
    advanceRentDays,
    latestUnpaidUtilityAmountByRoom,
    overdueRooms,
    expiringRooms,
    backendLoading,
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
