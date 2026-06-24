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

  // 后端逾期/到期数据
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
      const data = res.data as any
      overdueRoomsFromBackend.value = data.overdue_rooms || []
      expiringRoomsFromBackend.value = data.expiring_rooms || []
    } catch (err) {
      console.error('[useOverdueManagement] 后端API获取逾期/到期数据失败:', err)
      overdueRoomsFromBackend.value = []
      expiringRoomsFromBackend.value = []
      ElMessage.error('获取收租状态失败，请检查后端服务')
    } finally {
      backendLoading.value = false
    }
  }

  // 当配置或数据变化时重新获取
  watch([overdueCutoffDate, advanceRentDays, expiringDays, payments, allRooms], () => {
    fetchPaymentStatus()
  }, { deep: true })

  // 对外暴露的逾期/到期数据
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
      if (room) {
        ;(room as any).__daysUntilPayment = item.days_until_payment
        return room
      }
      return { id: item.room_id, room_number: item.room_number } as Room
    })
  })

  const overdueRooms = overdueItems
  const expiringRooms = expiringItems

  // 水电相关（仍需前端本地计算）
  const mergedAllReadings = computed(() =>
    mergeReadings(allReadings.value, roomOptions.value)
  )

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

  // 催租消息
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

  // 从后端数据的 __daysUntilPayment 获取到期天数
  const getNextPaymentDays = (room: Room): number => {
    return (room as any).__daysUntilPayment ?? 0
  }

  return {
    overdueRooms,
    expiringRooms,
    backendLoading,
    canMarkExpiringRoomPaid,
    markExpiringRoomPaid,
    getLatestCollectionDetailText,
    sendReminder,
    getNextPaymentDays,
  }
}
