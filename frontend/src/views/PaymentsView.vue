<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { paymentApi } from '@/api/payment'
import { roomApi } from '@/api/room'
import * as utilityBillApi from '@/api/utility_bills'
import { useOverdueConfig } from '@/composables/useOverdueConfig'
import { useAmountVisibility } from '@/composables/useAmountVisibility'
import { useAuthStore } from '@/stores/auth'
import type { Payment } from '@/types'
import type { Room } from '@/types'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'

use([
  CanvasRenderer,
  BarChart,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

// 漏交警告接口
interface MissedPaymentWarning {
  id: string
  roomNumber: string
  message: string
  startDate: string
  endDate: string
}

// 已忽略的警告记录接口
interface IgnoredWarning {
  id: string
  roomNumber: string
  message: string
  startDate: string
  endDate: string
  reason: string
  ignoredAt: string
}

const authStore = useAuthStore()
const payments = ref<Payment[]>([])
const rooms = ref<Room[]>([])
const loading = ref(false)
const initialized = ref(false)  // 标记是否已初始化完成
const selectedRoomId = ref<number | null>(null)
const { hideAmounts, formatAmount } = useAmountVisibility()

// 已忽略的警告记录列表（从localStorage加载）
const ignoredWarnings = ref<IgnoredWarning[]>([])

// 查看已忽略警告对话框是否显示
const showIgnoredWarningsDialog = ref(false)

// 水电收益统计
const utilityProfit = ref<utilityBillApi.UtilityBillProfitStats | null>(null)
const utilityBills = ref<utilityBillApi.UtilityBill[]>([])
const seriesList = ref<utilityBillApi.SeriesInfo[]>([])
const showBillDialog = ref(false)
const billForm = ref<utilityBillApi.UtilityBillCreate>({
  series: '',
  year: new Date().getFullYear(),
  month: new Date().getMonth() + 1,
  utility_type: 'water',
  cost: 0,
  notes: ''
})

// 系列水电明细对话框
const showSeriesDetailDialog = ref(false)
const seriesDetailLoading = ref(false)
const seriesDetailData = ref<utilityBillApi.SeriesUtilityDetail[]>([])
const seriesDetailTitle = ref('')

// 计算上个月作为默认值
const today = new Date()
const lastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1)
billForm.value.year = lastMonth.getFullYear()
billForm.value.month = lastMonth.getMonth() + 1
const editingBillId = ref<number | null>(null)
const loadingUtilityData = ref(false)

// 加载已忽略的警告记录
const loadIgnoredWarnings = () => {
  const stored = localStorage.getItem('ignoredMissedWarnings')
  if (stored) {
    ignoredWarnings.value = JSON.parse(stored)
  }
}

// 保存已忽略的警告记录到localStorage
const saveIgnoredWarnings = () => {
  localStorage.setItem('ignoredMissedWarnings', JSON.stringify(ignoredWarnings.value))
}

// 忽略警告（带备注）
const ignoreWarning = (warning: MissedPaymentWarning) => {
  ElMessageBox.prompt('请输入忽略此提醒的原因（方便以后查看）', '标记为已知', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputPlaceholder: '例如：已现金收取、租客延期等',
    inputType: 'textarea',
    inputValidator: (value) => {
      if (!value || !value.trim()) {
        return '请输入忽略原因'
      }
      return true
    }
  }).then(({ value: reason }) => {
    const ignoredRecord: IgnoredWarning = {
      id: warning.id,
      roomNumber: warning.roomNumber,
      message: warning.message,
      startDate: warning.startDate,
      endDate: warning.endDate,
      reason: reason.trim(),
      ignoredAt: new Date().toISOString()
    }
    ignoredWarnings.value.push(ignoredRecord)
    saveIgnoredWarnings()
    ElMessage.success('已标记为已知')
  }).catch(() => {
    // 用户取消
  })
}

// 恢复单个已忽略的警告
const restoreWarning = (warningId: string) => {
  ElMessageBox.confirm('确定要恢复这个漏交提醒吗？', '恢复提醒', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    ignoredWarnings.value = ignoredWarnings.value.filter(w => w.id !== warningId)
    saveIgnoredWarnings()
    ElMessage.success('已恢复漏交提醒')
  }).catch(() => {
    // 用户取消
  })
}

// 恢复所有已忽略的警告
const restoreAllWarnings = () => {
  ElMessageBox.confirm('确定要恢复所有已忽略的漏交提醒吗？', '恢复全部', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    ignoredWarnings.value = []
    saveIgnoredWarnings()
    ElMessage.success('已恢复所有漏交提醒')
  }).catch(() => {
    // 用户取消
  })
}

// 格式化忽略时间
const formatIgnoredAt = (ignoredAt: string) => {
  const date = new Date(ignoredAt)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}`
}

// 是否显示删除按钮（仅超级管理员可见）
const showDeleteButtons = computed(() => authStore.isSuperAdmin)

// 先初始化配置（lookbackMonths等）
const { overdueCutoffDate, lookbackMonths } = useOverdueConfig()

// 日期范围：由 lookbackMonths 控制，统一影响全页面
const startDate = ref<Date>(new Date())
const endDate = ref<Date>(new Date())

// 根据lookbackMonths更新日期范围
const updateDateRange = () => {
  const now = new Date()
  const months = lookbackMonths.value || 1
  // 开始日期：N个月前的1号
  startDate.value = new Date(now.getFullYear(), now.getMonth() - months + 1, 1)
  // 结束日期：当月最后一天
  endDate.value = new Date(now.getFullYear(), now.getMonth() + 1, 0)
}

// 初始化
updateDateRange()

// 日期范围显示文本
const dateRangeDisplay = computed(() => {
  const fmt = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  return `${fmt(startDate.value)} ~ ${fmt(endDate.value)}`
})

// 批量选择相关
const selectedGroups = ref<string[]>([])
const selectAll = ref(false)

// 收租概况：按月分组，区分已收/未收/不收租
const rentCollectionByMonth = computed(() => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const currentYear = today.getFullYear()
  const currentMonth = today.getMonth()

  const buildDue = (y: number, m: number, day: number) => {
    const dim = new Date(y, m + 1, 0).getDate()
    const d = new Date(y, m, Math.min(day, dim))
    d.setHours(0, 0, 0, 0)
    return d
  }

  type RoomItem = { room: Room; cycle: number; cycleLabel: string; rentDue: number; dueDay: number; dueDateStr: string }
  type SkippedItem = { room: Room; reason: string }

  const months: Array<{
    key: string
    label: string
    unpaid: RoomItem[]
    paid: RoomItem[]
    skipped: SkippedItem[]
    totalRent: number
    paidRent: number
  }> = []

  for (let i = lookbackMonths.value; i >= 0; i--) {
    const m = currentMonth - i
    const year = currentYear + Math.floor(m / 12)
    const month = ((m % 12) + 12) % 12
    const isCurrent = (i === 0)
    const label = isCurrent ? `${month + 1}月（本月）` : `${month + 1}月`
    const key = `${year}-${String(month + 1).padStart(2, '0')}`

    const unpaidRooms: RoomItem[] = []
    const paidRooms: RoomItem[] = []
    const skippedRooms: SkippedItem[] = []

    rooms.value.forEach(room => {
      // 非已出租状态
      if (room.status !== 'occupied') {
        const statusMap: Record<string, string> = { available: '空置', maintenance: '维修中' }
        skippedRooms.push({ room, reason: statusMap[room.status] || room.status })
        return
      }

      // 无租金
      if (!room.monthly_rent || room.monthly_rent <= 0) {
        skippedRooms.push({ room, reason: '无租金' })
        return
      }

      const cycle = Math.max(1, Number(room.payment_cycle || 1))
      const anchorSource = room.lease_start || ''
      const anchor = anchorSource ? new Date(anchorSource) : null
      const dueDay = anchor ? anchor.getDate() : 0

      if (!dueDay) {
        skippedRooms.push({ room, reason: '无租期信息' })
        return
      }

      const dueDateThisMonth = buildDue(year, month, dueDay)
      const cutoffDate = new Date(overdueCutoffDate.value)
      cutoffDate.setHours(0, 0, 0, 0)

      if (dueDateThisMonth < cutoffDate) {
        skippedRooms.push({ room, reason: '豁免日期之前' })
        return
      }

      // 租期未开始
      if (anchorSource) {
        const leaseStart = new Date(anchorSource)
        leaseStart.setHours(0, 0, 0, 0)
        if (leaseStart > dueDateThisMonth) {
          skippedRooms.push({ room, reason: '租期未开始' })
          return
        }
      }

      // 季付/半年付：非周期月
      if (cycle > 1) {
        if (!anchorSource) {
          skippedRooms.push({ room, reason: '无租期信息' })
          return
        }
        const anchorMonth = anchor!.getMonth()
        const diff = ((month - anchorMonth) % 12 + 12) % 12
        if (diff % cycle !== 0) {
          const monthsUntilNext = cycle - (diff % cycle)
          const nextCycleDiff = diff + monthsUntilNext
          const nextCycleMonthNum = (anchorMonth + nextCycleDiff) % 12
          const cycleName = cycle === 3 ? '季付' : cycle === 6 ? '半年付' : `${cycle}个月付`
          skippedRooms.push({ room, reason: `${cycleName}（下次${nextCycleMonthNum + 1}月收）` })
          return
        }
      }

      // 判断是否首个账单周期（新签租客）
      const isFirstCycle = anchorSource
        ? Math.abs(dueDateThisMonth.getTime() - new Date(anchorSource).setHours(0, 0, 0, 0)) < 86400000
        : false

      // 已收判断
      const halfCycleMs = cycle * 15 * 86400000

      const roomRentPayments = payments.value.filter(p =>
        p.room_id === room.id &&
        p.payment_type === 'rent' &&
        p.status !== 'cancelled' &&
        p.payment_date
      )

      const isPaid = isFirstCycle
        ? roomRentPayments.length > 0
        : roomRentPayments.some(p => {
            const d = new Date(p.payment_date!)
            d.setHours(0, 0, 0, 0)
            return Math.abs(d.getTime() - dueDateThisMonth.getTime()) <= halfCycleMs
          })

      const rentDue = Number(room.monthly_rent || 0) * cycle
      const cycleLabel = cycle > 1 ? `${cycle}个月` : ''
      const item: RoomItem = { room, cycle, cycleLabel, rentDue, dueDay, dueDateStr: `${dueDay}号` }

      if (isPaid) {
        paidRooms.push(item)
      } else {
        unpaidRooms.push(item)
      }
    })

    if (unpaidRooms.length > 0 || paidRooms.length > 0 || skippedRooms.length > 0) {
      unpaidRooms.sort((a, b) => a.dueDay - b.dueDay)
      paidRooms.sort((a, b) => a.dueDay - b.dueDay)
      skippedRooms.sort((a, b) => a.room.room_number.localeCompare(b.room.room_number))
      const totalRent = [...unpaidRooms, ...paidRooms].reduce((s, r) => s + r.rentDue, 0)
      const paidRent = paidRooms.reduce((s, r) => s + r.rentDue, 0)
      months.push({ key, label, unpaid: unpaidRooms, paid: paidRooms, skipped: skippedRooms, totalRent, paidRent })
    }
  }

  return months
})

// 收租概况倒序（最新月份在前）+ 当前选中tab
const rentCollectionByMonthDesc = computed(() => [...rentCollectionByMonth.value].reverse())
const activeMonthTab = ref('')
const expandedMonthDetail = ref<Record<string, boolean>>({})

const toggleMonthDetail = (key: string, _type: string) => {
  expandedMonthDetail.value[key] = !expandedMonthDetail.value[key]
}

// 数据加载后默认选中第一个（最新的）
watch(rentCollectionByMonthDesc, (val) => {
  if (val.length > 0 && !activeMonthTab.value) {
    activeMonthTab.value = val[0].key
  }
}, { immediate: true })

// 水电月度明细按月份分组
const utilityBreakdownByMonth = computed(() => {
  if (!utilityProfit.value?.monthly_breakdown) return []
  const map = new Map<string, { key: string; label: string; rows: typeof utilityProfit.value.monthly_breakdown; monthTotal: number; monthWaterCollected: number; monthWaterCost: number; monthWaterProfit: number; monthElectricCollected: number; monthElectricCost: number; monthElectricProfit: number }>()
  for (const row of utilityProfit.value.monthly_breakdown) {
    const key = `${row.year}-${String(row.month).padStart(2, '0')}`
    if (!map.has(key)) {
      map.set(key, { key, label: `${row.year}年${row.month}月`, rows: [], monthTotal: 0, monthWaterCollected: 0, monthWaterCost: 0, monthWaterProfit: 0, monthElectricCollected: 0, monthElectricCost: 0, monthElectricProfit: 0 })
    }
    const g = map.get(key)!
    g.rows.push(row)
    g.monthWaterCollected += row.water_collected
    g.monthWaterCost += row.water_cost
    g.monthWaterProfit += row.water_profit
    g.monthElectricCollected += row.electric_collected
    g.monthElectricCost += row.electric_cost
    g.monthElectricProfit += row.electric_profit
    g.monthTotal += row.total_profit
  }
  // 按 key 降序（最新月份在前）
  return [...map.values()].sort((a, b) => b.key.localeCompare(a.key))
})
const utilityMonthTab = ref('')
watch(utilityBreakdownByMonth, (val) => {
  if (val.length > 0 && !utilityMonthTab.value) {
    utilityMonthTab.value = val[0].key
  }
}, { immediate: true })


const exportYear = ref(new Date().getFullYear())
const exporting = ref(false)

const handleExportCSV = async () => {
  exporting.value = true
  try {
    const res = await paymentApi.exportPaymentsByYear(exportYear.value)
    const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `交租记录_${exportYear.value}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    ElMessage.success(`已导出 ${exportYear.value} 年交租记录`)
  } catch (error: any) {
    console.error('导出失败:', error)
    ElMessage.error(error.response?.data?.detail || '导出失败')
  } finally {
    exporting.value = false
  }
}

const getStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    pending: '待处理',
    completed: '已完成',
    overdue: '逾期',
    cancelled: '已取消',
  }
  return labels[status] || status
}

// 合并同一次收租的记录（按 room_id + payment_date 分组）
const groupedPayments = computed(() => {
  const groups: { [key: string]: any } = {}
  
  payments.value.forEach(payment => {
    // 如果选择了房号，只显示该房间的记录
    if (selectedRoomId.value !== null && payment.room_id !== selectedRoomId.value) {
      return
    }
    
    const key = `${payment.room_id}_${payment.payment_date}`
    
    if (!groups[key]) {
      // 优先使用API返回的room_number，如果没有才从rooms数组查找
      const roomNumber = payment.room_number || 
                        rooms.value.find(r => r.id === payment.room_id)?.room_number || 
                        `房间 ${payment.room_id}`
      groups[key] = {
        room_id: payment.room_id,
        room_number: roomNumber,
        payment_date: payment.payment_date,
        status: payment.status,
        rent: 0,
        water: 0,
        electricity: 0,
        total: 0
      }
    }
    
    // 根据payment_type累加金额
    if (payment.payment_type === 'rent') {
      groups[key].rent += Number(payment.amount) || 0
    } else if (payment.payment_type === 'utility') {
      // 通过description判断是水费还是电费
      const desc = (payment.description || '').toLowerCase()
      if (desc.includes('水') || desc.includes('water')) {
        groups[key].water += Number(payment.amount) || 0
      } else if (desc.includes('电') || desc.includes('electricity')) {
        groups[key].electricity += Number(payment.amount) || 0
      } else {
        // 如果无法区分，根据金额判断（通常水费较小）
        if (Number(payment.amount) < 50) {
          groups[key].water += Number(payment.amount) || 0
        } else {
          groups[key].electricity += Number(payment.amount) || 0
        }
      }
    } else if (payment.payment_type === 'refund') {
      // 退租记录显示在房租列（负数）
      groups[key].rent += Number(payment.amount) || 0
    }
    
    groups[key].total += Number(payment.amount) || 0
  })
  
  // 转为数组并按日期降序排序
  const sorted = Object.values(groups).sort((a, b) => 
    new Date(b.payment_date).getTime() - new Date(a.payment_date).getTime()
  )

  // 按当前选中月份tab过滤
  if (activeMonthTab.value) {
    return sorted.filter(p => {
      if (!p.payment_date) return false
      const d = new Date(p.payment_date)
      const ym = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
      return ym === activeMonthTab.value
    })
  }
  return sorted
})

// 检测漏交月份的提醒
const missedPaymentWarnings = computed<MissedPaymentWarning[]>(() => {
  const warnings: MissedPaymentWarning[] = []
  const DAY = 86400000

  // 按房间分组
  const roomPayments: { [roomId: number]: any[] } = {}
  payments.value.forEach(payment => {
    if (payment.payment_type === 'rent') {
      if (!roomPayments[payment.room_id]) roomPayments[payment.room_id] = []
      roomPayments[payment.room_id].push(payment)
    }
  })

  Object.keys(roomPayments).forEach(roomId => {
    const room = rooms.value.find(r => r.id === Number(roomId))
    if (!room) return

    const cycle = Math.max(1, Number(room.payment_cycle || 1))
    const anchorSource = room.lease_start || ''
    if (!anchorSource) return
    const anchor = new Date(anchorSource)
    const dueDay = anchor.getDate()
    // 预期两次缴费之间的天数（约 cycle 个月）
    const expectedGapDays = cycle * 30

    const sorted = roomPayments[Number(roomId)]
      .sort((a, b) => new Date(a.payment_date).getTime() - new Date(b.payment_date).getTime())

    for (let i = 1; i < sorted.length; i++) {
      const prev = new Date(sorted[i - 1].payment_date)
      prev.setHours(0, 0, 0, 0)
      const curr = new Date(sorted[i].payment_date)
      curr.setHours(0, 0, 0, 0)
      const gapDays = Math.round((curr.getTime() - prev.getTime()) / DAY)

      // 如果有 period 信息，直接用 period 判断
      if (sorted[i - 1].period_end && sorted[i].period_start) {
        const prevEnd = new Date(sorted[i - 1].period_end)
        prevEnd.setHours(0, 0, 0, 0)
        const currStart = new Date(sorted[i].period_start)
        currStart.setHours(0, 0, 0, 0)
        const gapBetweenPeriods = Math.round((currStart.getTime() - prevEnd.getTime()) / DAY)
        if (gapBetweenPeriods > 1) {
          const startDate = sorted[i - 1].period_end
          const endDate = sorted[i].period_start
          const missedMonths = Math.round(gapBetweenPeriods / 30)
          const id = `${room.id}-${startDate}-${endDate}`
          
          warnings.push({
            id,
            roomNumber: room.room_number,
            message: `${room.room_number} 可能有 ${missedMonths} 个月未交租 (${startDate} → ${endDate})`,
            startDate,
            endDate
          })
        }
      } else if (gapDays > expectedGapDays * 1.5) {
        // 没有 period 信息时，用天数间隔判断（允许50%的容差）
        const missedMonths = Math.round(gapDays / 30) - cycle
        if (missedMonths > 0) {
          const startDate = sorted[i - 1].payment_date.split('T')[0]
          const endDate = sorted[i].payment_date.split('T')[0]
          const id = `${room.id}-${startDate}-${endDate}`
          
          warnings.push({
            id,
            roomNumber: room.room_number,
            message: `${room.room_number} 可能有 ${missedMonths} 个月未交租 (${startDate} → ${endDate})`,
            startDate,
            endDate
          })
        }
      }
    }
  })
  
  // 过滤掉已忽略的警告
  const ignoredIds = ignoredWarnings.value.map(w => w.id)
  // 过滤掉已知的退租重租导致的假警告（租客搬进搬出产生的间隔）
  const knownFalseWarnings = [
    '35-2026-04-10-2026-05-30',  // 102A-1 租客搬进搬出两次
  ]
  return warnings.filter(w => !ignoredIds.includes(w.id) && !knownFalseWarnings.includes(w.id))
})

// 月度统计数据
const monthlyStats = computed(() => {
  const stats: { [key: string]: { rent: number; water: number; electricity: number; total: number } } = {}

  payments.value.forEach(payment => {
    const date = new Date(payment.payment_date)
    const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`

    if (!stats[monthKey]) {
      stats[monthKey] = { rent: 0, water: 0, electricity: 0, total: 0 }
    }

    const amount = Number(payment.amount) || 0

    if (payment.payment_type === 'rent') {
      stats[monthKey].rent += amount
    } else if (payment.payment_type === 'utility') {
      const desc = (payment.description || '').toLowerCase()
      if (desc.includes('水') || desc.includes('water')) {
        stats[monthKey].water += amount
      } else if (desc.includes('电') || desc.includes('electricity')) {
        stats[monthKey].electricity += amount
      } else {
        if (amount < 50) {
          stats[monthKey].water += amount
        } else {
          stats[monthKey].electricity += amount
        }
      }
    }

    stats[monthKey].total += amount
  })

  // 转为数组并按月份排序
  return Object.entries(stats)
    .map(([month, data]) => ({ month, ...data }))
    .sort((a, b) => a.month.localeCompare(b.month))
})

// 图表配置
const chartOption = computed(() => {
  const months = monthlyStats.value.map(s => s.month)
  const rentData = monthlyStats.value.map(s => s.rent)
  const waterData = monthlyStats.value.map(s => s.water)
  const electricityData = monthlyStats.value.map(s => s.electricity)
  const totalData = monthlyStats.value.map(s => s.total)

  return {
    title: {
      text: '月度收租统计',
      left: 'center',
      textStyle: { fontSize: 18 }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        let result = `${params[0].axisValue}<br/>`
        params.forEach((param: any) => {
          result += `${param.marker} ${param.seriesName}: ${hideAmounts.value ? '****' : `¥${Number(param.value || 0).toFixed(2)}`}<br/>`
        })
        return result
      }
    },
    legend: {
      data: ['房租', '水费', '电费', '合计'],
      top: 30
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: months,
      axisLabel: { rotate: 45 }
    },
    yAxis: {
      type: 'value',
      name: '金额 (元)',
      axisLabel: {
        formatter: (value: number) => (hideAmounts.value ? '***' : `¥${value}`)
      }
    },
    series: [
      {
        name: '房租',
        type: 'bar',
        data: rentData,
        itemStyle: { color: '#409eff' }
      },
      {
        name: '水费',
        type: 'bar',
        data: waterData,
        itemStyle: { color: '#67c23a' }
      },
      {
        name: '电费',
        type: 'bar',
        data: electricityData,
        itemStyle: { color: '#e6a23c' }
      },
      {
        name: '合计',
        type: 'line',
        data: totalData,
        itemStyle: { color: '#f56c6c' },
        lineStyle: { width: 3 }
      }
    ]
  }
})

const setYearToDate = () => {
  const now = new Date()
  startDate.value = new Date(now.getFullYear(), 0, 1)
  endDate.value = now
  loadPayments()
}

const loadPayments = async () => {
  loading.value = true
  try {
    // 格式化日期为 YYYY-MM-DD
    const formatDate = (date: Date) => {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      return `${year}-${month}-${day}`
    }

    const params: any = { page: 1, size: 1000 }
    if (startDate.value) {
      // 往前多推90天，确保季度付/半年付房间提前交的房租记录也被加载（用于isPaid判断）
      const apiStartDate = new Date(startDate.value)
      apiStartDate.setDate(apiStartDate.getDate() - 90)
      params.start_date = formatDate(apiStartDate)
    }
    if (endDate.value) {
      params.end_date = formatDate(endDate.value)
    }

    const [paymentsRes, roomsRes] = await Promise.all([
      paymentApi.getPayments(params),
      roomApi.getRooms({ page: 1, size: 100 })
    ])
    payments.value = paymentsRes.data.items
    rooms.value = roomsRes.data.items || roomsRes.data
  } catch (error) {
    console.error('加载缴费记录失败:', error)
  } finally {
    loading.value = false
    initialized.value = true  // 标记初始化完成
  }
}

// 加载水电收益数据
const loadUtilityProfit = async () => {
  loadingUtilityData.value = true
  try {
    utilityProfit.value = await utilityBillApi.getUtilityBillProfit()
  } catch (error) {
    console.error('加载水电收益失败:', error)
  } finally {
    loadingUtilityData.value = false
  }
}

// 加载水电账单列表
const loadUtilityBills = async () => {
  try {
    utilityBills.value = await utilityBillApi.getUtilityBills()
  } catch (error) {
    console.error('加载水电账单列表失败:', error)
  }
}

// 加载房子系列列表
const loadSeriesList = async () => {
  try {
    const data = await utilityBillApi.getSeriesList()
    seriesList.value = data
  } catch (error) {
    console.error('加载系列列表失败:', error)
  }
}

// 打开系列水电明细对话框
const openSeriesDetail = async (series: string, year: number, month: number) => {
  seriesDetailLoading.value = true
  seriesDetailTitle.value = `${series}系列 ${year}年${month}月 水电收租明细`
  showSeriesDetailDialog.value = true
  
  try {
    seriesDetailData.value = await utilityBillApi.getSeriesUtilityDetail(series, year, month)
  } catch (error: any) {
    console.error('加载系列明细失败:', error)
    ElMessage.error(error.response?.data?.detail || '加载明细失败')
    showSeriesDetailDialog.value = false
  } finally {
    seriesDetailLoading.value = false
  }
}

// 打开录入对话框
const openBillDialog = (bill?: utilityBillApi.UtilityBill) => {
  if (bill) {
    // 编辑模式
    editingBillId.value = bill.id
    billForm.value = {
      series: bill.series,
      year: bill.year,
      month: bill.month,
      utility_type: bill.utility_type,
      cost: bill.cost,
      notes: bill.notes || ''
    }
  } else {
    // 新增模式 - 默认为上个月（因为水电费是月初收上个月的）
    editingBillId.value = null
    const today = new Date()
    const lastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1)
    billForm.value = {
      series: '',
      year: lastMonth.getFullYear(),
      month: lastMonth.getMonth() + 1,
      utility_type: 'water',
      cost: 0,
      notes: ''
    }
  }
  loadSeriesList()
  showBillDialog.value = true
}

// 保存水电账单
const saveUtilityBill = async () => {
  try {
    if (editingBillId.value) {
      // 更新（只传后端支持的字段）
      const { utility_type, cost, notes } = billForm.value
      await utilityBillApi.updateUtilityBill(editingBillId.value, { utility_type, cost, notes })
      ElMessage.success('更新成功')
    } else {
      // 创建
      await utilityBillApi.createUtilityBill(billForm.value)
      ElMessage.success('创建成功')
    }
    showBillDialog.value = false
    await loadUtilityBills()
    await loadUtilityProfit()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  }
}

// 删除水电账单
const deleteUtilityBill = async (bill: utilityBillApi.UtilityBill) => {
  try {
    await ElMessageBox.confirm(
      `确认删除 ${bill.year}年${bill.month}月 的账单吗？`,
      '删除确认',
      { type: 'warning' }
    )
    await utilityBillApi.deleteUtilityBill(bill.id)
    ElMessage.success('删除成功')
    await loadUtilityBills()
    await loadUtilityProfit()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

// 全选/取消全选
const toggleSelectAll = () => {
  if (selectAll.value) {
    selectedGroups.value = groupedPayments.value.map(
      p => `${p.room_id}_${p.payment_date}`
    )
  } else {
    selectedGroups.value = []
  }
}

// 删除单个组（房租+水费+电费）
const handleDeleteGroup = async (group: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除 ${group.room_number} ${group.payment_date} 的收租记录吗？\n\n` +
      `房租: ${formatAmount(group.rent)}\n` +
      `水费: ${formatAmount(group.water)}\n` +
      `电费: ${formatAmount(group.electricity)}\n` +
      `合计: ${formatAmount(group.total)}`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    // 查找该组的所有支付记录ID
    const groupPayments = payments.value.filter(
      p => p.room_id === group.room_id && p.payment_date === group.payment_date
    )

    // 批量删除
    await paymentApi.batchDeletePayments(groupPayments.map(p => p.id))

    ElMessage.success('删除成功')
    await loadPayments()
    selectedGroups.value = []
    selectAll.value = false
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败: ' + (error.response?.data?.detail || error.message))
    }
  }
}

// 批量删除选中的记录
const handleBatchDelete = async () => {
  if (selectedGroups.value.length === 0) {
    ElMessage.warning('请先选择要删除的记录')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedGroups.value.length} 条收租记录吗？`,
      '批量删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    // 收集所有选中的支付记录ID
    const allPaymentIds: number[] = []
    selectedGroups.value.forEach(groupKey => {
      const [room_id, payment_date] = groupKey.split('_')
      const groupPayments = payments.value.filter(
        p => p.room_id === parseInt(room_id) && p.payment_date === payment_date
      )
      groupPayments.forEach(p => allPaymentIds.push(p.id))
    })

    // 批量删除
    await paymentApi.batchDeletePayments(allPaymentIds)

    ElMessage.success(`成功删除 ${selectedGroups.value.length} 条记录`)
    await loadPayments()
    selectedGroups.value = []
    selectAll.value = false
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('批量删除失败:', error)
      ElMessage.error('批量删除失败: ' + (error.response?.data?.detail || error.message))
    }
  }
}

onMounted(() => {
  loadIgnoredWarnings()
  loadPayments()
  loadSeriesList()
  loadUtilityProfit()
  loadUtilityBills()
})

// lookbackMonths变化 → 更新日期范围 → 重新加载全部数据
watch(lookbackMonths, () => {
  updateDateRange()
  loadPayments()
  loadUtilityProfit()
  loadUtilityBills()
})
</script>

<template>
  <div class="payments-view">
    <header class="view-header">
      <h1>缴费记录</h1>
      <div class="header-actions">
        <el-select v-model="exportYear" style="width: 120px; margin-right: 8px;">
          <el-option
            v-for="y in [...Array(10)].map((_, i) => new Date().getFullYear() - i)"
            :key="y"
            :label="`${y}年`"
            :value="y"
          />
        </el-select>
        <el-button type="success" :loading="exporting" @click="handleExportCSV">
          📥 导出CSV
        </el-button>
      </div>
    </header>

    <main class="view-content">
      <!-- 全局时间提示（从设置读取） -->
      <div class="global-time-control">
        <span class="time-control-label">📅 显示最近 {{ lookbackMonths }} 个月</span>
        <span class="time-control-hint">（{{ dateRangeDisplay }}）</span>
        <router-link to="/settings" class="time-control-link">修改设置</router-link>
      </div>

      <!-- 月度趋势图表 -->
      <div v-if="monthlyStats.length > 0" class="chart-container">
        <v-chart :option="chartOption" style="height: 350px" autoresize />
      </div>

      <!-- 水电收益统计 -->
      <div v-if="!hideAmounts && utilityProfit" class="utility-profit-card">
        <div class="profit-header">
          <h2>💧⚡ 水电收益统计</h2>
          <el-button type="primary" size="small" @click="openBillDialog()">
            + 录入支出
          </el-button>
        </div>
        <div class="profit-stats">
          <div class="stat-item">
            <span class="stat-label">累计水费收益</span>
            <span class="stat-value water-profit">¥{{ utilityProfit.total_water_profit.toFixed(2) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">累计电费收益</span>
            <span class="stat-value electric-profit">¥{{ utilityProfit.total_electric_profit.toFixed(2) }}</span>
          </div>
          <div class="stat-item total">
            <span class="stat-label">累计总收益</span>
            <span class="stat-value">¥{{ utilityProfit.total_profit.toFixed(2) }}</span>
          </div>
        </div>
        
        <!-- 月度明细 -->
        <div v-if="utilityProfit.monthly_breakdown.length > 0" class="monthly-breakdown">
          <h3>月度明细</h3>
          <el-tabs v-model="utilityMonthTab" type="border-card">
            <el-tab-pane v-for="monthGroup in utilityBreakdownByMonth" :key="monthGroup.key" :label="monthGroup.label" :name="monthGroup.key">
              <!-- 桌面端：表格 -->
              <el-table :data="monthGroup.rows" size="small" class="hidden-mobile" show-summary :summary-method="() => [
                '月度合计',
                `收: ¥${monthGroup.monthWaterCollected.toFixed(2)}\n支: ¥${monthGroup.monthWaterCost.toFixed(2)}\n益: ¥${monthGroup.monthWaterProfit.toFixed(2)}`,
                `收: ¥${monthGroup.monthElectricCollected.toFixed(2)}\n支: ¥${monthGroup.monthElectricCost.toFixed(2)}\n益: ¥${monthGroup.monthElectricProfit.toFixed(2)}`,
                `¥${monthGroup.monthTotal.toFixed(2)}`
              ]">
                <el-table-column label="系列" width="100">
                  <template #default="{ row }">
                    <div>{{ row.series }}</div>
                    <el-button
                      type="primary"
                      link
                      size="small"
                      @click="openSeriesDetail(row.series, row.year, row.month)"
                      style="margin-top: 4px;"
                    >
                      查看明细
                    </el-button>
                  </template>
                </el-table-column>
                <el-table-column label="水费">
                  <template #default="{ row }">
                    <div>收: ¥{{ row.water_collected.toFixed(2) }}</div>
                    <div>支: ¥{{ row.water_cost.toFixed(2) }}</div>
                    <div class="profit-value">益: ¥{{ row.water_profit.toFixed(2) }}</div>
                  </template>
                </el-table-column>
                <el-table-column label="电费">
                  <template #default="{ row }">
                    <div>收: ¥{{ row.electric_collected.toFixed(2) }}</div>
                    <div>支: ¥{{ row.electric_cost.toFixed(2) }}</div>
                    <div class="profit-value">益: ¥{{ row.electric_profit.toFixed(2) }}</div>
                  </template>
                </el-table-column>
                <el-table-column label="总收益">
                  <template #default="{ row }">
                    <span class="total-profit">¥{{ row.total_profit.toFixed(2) }}</span>
                  </template>
                </el-table-column>
              </el-table>
              <!-- 手机端：卡片 -->
              <div class="monthly-cards hidden-desktop">
                <div v-for="(row, idx) in monthGroup.rows" :key="idx" class="monthly-card">
                  <div class="monthly-card-header">
                    <span>{{ row.series }}</span>
                    <el-button type="primary" link size="small" @click="openSeriesDetail(row.series, row.year, row.month)">明细</el-button>
                  </div>
                  <div class="monthly-card-body">
                    <div class="monthly-card-cell">
                      <span class="label">水收</span>
                      <span>¥{{ row.water_collected.toFixed(2) }}</span>
                    </div>
                    <div class="monthly-card-cell">
                      <span class="label">水支</span>
                      <span>¥{{ row.water_cost.toFixed(2) }}</span>
                    </div>
                    <div class="monthly-card-cell">
                      <span class="label">电收</span>
                      <span>¥{{ row.electric_collected.toFixed(2) }}</span>
                    </div>
                    <div class="monthly-card-cell">
                      <span class="label">电支</span>
                      <span>¥{{ row.electric_cost.toFixed(2) }}</span>
                    </div>
                    <div class="monthly-card-cell">
                      <span class="label">水益</span>
                      <span class="profit-value">¥{{ row.water_profit.toFixed(2) }}</span>
                    </div>
                    <div class="monthly-card-cell">
                      <span class="label">电益</span>
                      <span class="profit-value">¥{{ row.electric_profit.toFixed(2) }}</span>
                    </div>
                    <div class="monthly-card-total">
                      总收益: ¥{{ row.total_profit.toFixed(2) }}
                    </div>
                  </div>
                </div>
                <!-- 手机端月度合计 -->
                <div class="monthly-card monthly-card-summary">
                  <div class="monthly-card-header">
                    <span>📊 月度合计</span>
                  </div>
                  <div class="monthly-card-body">
                    <div class="monthly-card-cell">
                      <span class="label">水收</span>
                      <span>¥{{ monthGroup.monthWaterCollected.toFixed(2) }}</span>
                    </div>
                    <div class="monthly-card-cell">
                      <span class="label">水支</span>
                      <span>¥{{ monthGroup.monthWaterCost.toFixed(2) }}</span>
                    </div>
                    <div class="monthly-card-cell">
                      <span class="label">电收</span>
                      <span>¥{{ monthGroup.monthElectricCollected.toFixed(2) }}</span>
                    </div>
                    <div class="monthly-card-cell">
                      <span class="label">电支</span>
                      <span>¥{{ monthGroup.monthElectricCost.toFixed(2) }}</span>
                    </div>
                    <div class="monthly-card-cell">
                      <span class="label">水益</span>
                      <span class="profit-value">¥{{ monthGroup.monthWaterProfit.toFixed(2) }}</span>
                    </div>
                    <div class="monthly-card-cell">
                      <span class="label">电益</span>
                      <span class="profit-value">¥{{ monthGroup.monthElectricProfit.toFixed(2) }}</span>
                    </div>
                    <div class="monthly-card-total">
                      月度总收益: ¥{{ monthGroup.monthTotal.toFixed(2) }}
                    </div>
                  </div>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </div>

      <!-- 已录入账单列表 -->
      <div v-if="!hideAmounts && utilityBills.length > 0" class="utility-bills-list-card">
        <el-collapse>
          <el-collapse-item name="bills">
            <template #title>
              <span class="bills-list-title">📋 已录入账单（{{ utilityBills.length }}条）</span>
            </template>
            <!-- 桌面端表格 -->
            <el-table :data="utilityBills" size="small" class="hidden-mobile">
              <el-table-column label="系列" prop="series" width="90" />
              <el-table-column label="年月" width="90">
                <template #default="{ row }">{{ row.year }}-{{ String(row.month).padStart(2, '0') }}</template>
              </el-table-column>
              <el-table-column label="类型" width="70">
                <template #default="{ row }">
                  <el-tag :type="row.utility_type === 'water' ? 'info' : 'warning'" size="small">
                    {{ row.utility_type === 'water' ? '💧 水费' : '⚡ 电费' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="金额" width="100">
                <template #default="{ row }">¥{{ row.cost.toFixed(2) }}</template>
              </el-table-column>
              <el-table-column label="备注" prop="notes" show-overflow-tooltip />
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button type="primary" link size="small" @click="openBillDialog(row)">编辑</el-button>
                  <el-button type="danger" link size="small" @click="deleteUtilityBill(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            <!-- 手机端卡片 -->
            <div class="hidden-desktop">
              <div v-for="bill in utilityBills" :key="bill.id" class="bill-card-item">
                <div class="bill-card-info">
                  <span class="bill-series">{{ bill.series }}</span>
                  <span>{{ bill.year }}-{{ String(bill.month).padStart(2, '0') }}</span>
                  <el-tag :type="bill.utility_type === 'water' ? 'info' : 'warning'" size="small">
                    {{ bill.utility_type === 'water' ? '💧水费' : '⚡电费' }}
                  </el-tag>
                  <span class="bill-cost">¥{{ bill.cost.toFixed(2) }}</span>
                </div>
                <div class="bill-card-actions">
                  <el-button type="primary" link size="small" @click="openBillDialog(bill)">编辑</el-button>
                  <el-button type="danger" link size="small" @click="deleteUtilityBill(bill)">删除</el-button>
                </div>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <!-- 录入/编辑对话框 -->
      <el-dialog
        v-model="showBillDialog"
        :title="editingBillId ? '编辑水电账单' : '录入水电账单'"
        width="500px"
      >
        <el-form :model="billForm" label-width="100px">
          <el-form-item label="房子系列">
            <el-select 
              v-model="billForm.series" 
              placeholder="请选择房子系列"
              style="width: 100%"
              :disabled="!!editingBillId"
            >
              <el-option
                v-for="item in seriesList"
                :key="item.series"
                :label="`${item.series} 系列 (${item.room_count}个房间)`"
                :value="item.series"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="费用类型">
            <el-radio-group v-model="billForm.utility_type">
              <el-radio value="water">💧 水费</el-radio>
              <el-radio value="electric">⚡ 电费</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="年份">
            <el-input-number v-model="billForm.year" :min="2020" :max="2100" :disabled="!!editingBillId" />
          </el-form-item>
          <el-form-item label="月份">
            <el-input-number v-model="billForm.month" :min="1" :max="12" :disabled="!!editingBillId" />
          </el-form-item>
          <el-form-item :label="billForm.utility_type === 'water' ? '水费支出' : '电费支出'">
            <el-input-number v-model="billForm.cost" :min="0" :precision="2" />
            <span style="margin-left: 8px; color: #909399;">元</span>
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="billForm.notes" type="textarea" :rows="3" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showBillDialog = false">取消</el-button>
          <el-button type="primary" @click="saveUtilityBill">保存</el-button>
        </template>
      </el-dialog>

      <!-- 系列水电明细对话框 -->
      <el-dialog
        v-model="showSeriesDetailDialog"
        :title="seriesDetailTitle"
        width="900px"
      >
        <el-table
          :data="seriesDetailData"
          v-loading="seriesDetailLoading"
          size="small"
          :default-sort="{ prop: 'room_number', order: 'ascending' }"
        >
          <el-table-column prop="room_number" label="房间号" width="100" sortable />
          <el-table-column label="水费" width="180">
            <template #default="{ row }">
              <div v-if="row.water_amount !== null">
                <div>{{ row.water_previous }}→{{ row.water_current }}</div>
                <div style="font-size: 12px; color: #909399;">用量: {{ row.water_usage }}吨</div>
                <div style="font-weight: 500;">¥{{ row.water_amount.toFixed(2) }}</div>
              </div>
              <span v-else style="color: #909399;">未录入</span>
            </template>
          </el-table-column>
          <el-table-column label="电费" width="180">
            <template #default="{ row }">
              <div v-if="row.electric_amount !== null">
                <div>{{ row.electric_previous }}→{{ row.electric_current }}</div>
                <div style="font-size: 12px; color: #909399;">用量: {{ row.electric_usage }}度</div>
                <div style="font-weight: 500;">¥{{ row.electric_amount.toFixed(2) }}</div>
              </div>
              <span v-else style="color: #909399;">未录入</span>
            </template>
          </el-table-column>
          <el-table-column label="合计" width="100">
            <template #default="{ row }">
              <span style="font-weight: 600; color: #409eff;">¥{{ row.total_amount.toFixed(2) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="录入日期" width="110">
            <template #default="{ row }">
              {{ row.water_date ? row.water_date.split('T')[0] : '' }}
            </template>
          </el-table-column>
        </el-table>
        <template #footer>
          <el-button @click="showSeriesDetailDialog = false">关闭</el-button>
        </template>
      </el-dialog>

      <!-- 漏交提醒 -->
      <div v-if="missedPaymentWarnings.length > 0" class="warning-alert">
        <div class="alert-icon">⚠️</div>
        <div class="alert-content">
          <strong>漏交提醒：</strong>
          <ul>
            <li v-for="warning in missedPaymentWarnings" :key="warning.id" class="warning-item">
              <span>{{ warning.message }}</span>
              <el-button
                type="primary"
                size="small"
                link
                @click="ignoreWarning(warning)"
                class="ignore-btn"
              >
                忽略
              </el-button>
            </li>
          </ul>
        </div>
      </div>

      <!-- 已忽略的漏交警告 -->
      <div v-if="ignoredWarnings.length > 0" class="warning-alert" style="background-color: #f4f4f5; border-left: 4px solid #909399;">
        <div class="alert-content" style="width: 100%;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
              <strong style="color: #606266;">已忽略 {{ ignoredWarnings.length }} 条漏交提醒</strong>
            </div>
            <div style="display: flex; gap: 8px;">
              <el-button size="small" @click="showIgnoredWarningsDialog = true">查看详情</el-button>
              <el-button size="small" type="warning" @click="restoreAllWarnings">恢复全部</el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 收租概况 -->
      <div v-if="initialized && !loading && rentCollectionByMonth.length > 0" class="rent-collection">
        <el-tabs v-model="activeMonthTab" type="border-card">
          <el-tab-pane v-for="monthGroup in rentCollectionByMonthDesc" :key="monthGroup.key" :label="monthGroup.label" :name="monthGroup.key">
          <!-- 月度统计卡片 -->
          <div class="collection-summary">
            <div class="summary-cards" v-if="!hideAmounts">
              <div class="summary-card card-total" @click="toggleMonthDetail(monthGroup.key, 'unpaid')">
                <span class="sc-label">应收</span>
                <span class="sc-value">{{ monthGroup.unpaid.length + monthGroup.paid.length }}间</span>
                <span class="sc-amount">¥{{ monthGroup.totalRent }}</span>
              </div>
              <div class="summary-card card-paid" @click="toggleMonthDetail(monthGroup.key, 'paid')">
                <span class="sc-label">已收</span>
                <span class="sc-value">{{ monthGroup.paid.length }}间</span>
                <span class="sc-amount">¥{{ monthGroup.paidRent }}</span>
              </div>
              <div class="summary-card card-unpaid" @click="toggleMonthDetail(monthGroup.key, 'unpaid')">
                <span class="sc-label">未收</span>
                <span class="sc-value">{{ monthGroup.unpaid.length }}间</span>
                <span class="sc-amount">¥{{ monthGroup.totalRent - monthGroup.paidRent }}</span>
              </div>
            </div>
            <div class="summary-cards" v-else>
              <div class="summary-card card-total" @click="toggleMonthDetail(monthGroup.key, 'unpaid')">
                <span class="sc-label">应收</span>
                <span class="sc-value">{{ monthGroup.unpaid.length + monthGroup.paid.length }}间</span>
              </div>
              <div class="summary-card card-paid" @click="toggleMonthDetail(monthGroup.key, 'paid')">
                <span class="sc-label">已收</span>
                <span class="sc-value">{{ monthGroup.paid.length }}间</span>
              </div>
              <div class="summary-card card-unpaid" @click="toggleMonthDetail(monthGroup.key, 'unpaid')">
                <span class="sc-label">未收</span>
                <span class="sc-value">{{ monthGroup.unpaid.length }}间</span>
              </div>
            </div>
          </div>

          <!-- 明细（点击展开） -->
          <template v-if="expandedMonthDetail[monthGroup.key]">
          <!-- 未收 -->
          <div v-if="monthGroup.unpaid.length > 0" class="unpaid-section">
            <div class="section-label unpaid-label">未收 {{ monthGroup.unpaid.length }} 间</div>
            <div class="room-chips">
              <div v-for="item in monthGroup.unpaid" :key="`u-${monthGroup.key}-${item.room.id}`" class="room-chip chip-unpaid">
                <span class="chip-name">{{ item.room.room_number }}</span>
                <span class="chip-due">{{ item.dueDateStr }}</span>
                <span class="chip-rent">{{ hideAmounts ? '****' : `¥${item.rentDue}` }}</span>
                <span class="chip-cycle" v-if="item.cycle > 1">{{ item.cycleLabel }}付</span>
              </div>
            </div>
          </div>

          <!-- 已收 -->
          <div v-if="monthGroup.paid.length > 0" class="paid-section">
            <div class="section-label paid-label">已收 {{ monthGroup.paid.length }} 间</div>
            <div class="room-chips">
              <div v-for="item in monthGroup.paid" :key="`p-${monthGroup.key}-${item.room.id}`" class="room-chip chip-paid">
                <span class="chip-name">{{ item.room.room_number }}</span>
                <span class="chip-due">{{ item.dueDateStr }}交</span>
                <span class="chip-rent chip-rent-paid">{{ hideAmounts ? '****' : `¥${item.rentDue}` }}</span>
                <span class="chip-cycle" v-if="item.cycle > 1">{{ item.cycleLabel }}付</span>
              </div>
            </div>
          </div>

          <!-- 不收租 -->
          <div v-if="monthGroup.skipped.length > 0" class="skipped-section">
            <div class="section-label skipped-label">不收租 {{ monthGroup.skipped.length }} 间</div>
            <div class="room-chips">
              <div v-for="item in monthGroup.skipped" :key="`s-${monthGroup.key}-${item.room.id}`" class="room-chip chip-skipped">
                <span class="chip-name">{{ item.room.room_number }}</span>
                <span class="chip-reason">{{ item.reason }}</span>
              </div>
            </div>
          </div>
          </template>
          </el-tab-pane>
        </el-tabs>
      </div>

      <div v-if="loading" class="loading">加载中...</div>
      <div v-else class="payments-list">
        <table>
          <thead>
            <tr>
              <th style="width: 40px">
                <input
                  type="checkbox"
                  v-model="selectAll"
                  @change="toggleSelectAll"
                />
              </th>
              <th>房号</th>
              <th>收租日期</th>
              <th>房租</th>
              <th>水费</th>
              <th>电费</th>
              <th>合计</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="payment in groupedPayments" :key="`${payment.room_id}_${payment.payment_date}`">
              <td>
                <input
                  type="checkbox"
                  v-model="selectedGroups"
                  :value="`${payment.room_id}_${payment.payment_date}`"
                />
              </td>
              <td><strong>{{ payment.room_number }}</strong></td>
              <td>{{ payment.payment_date }}</td>
              <td :class="{ 'negative-amount': payment.rent < 0 }">{{ formatAmount(payment.rent) }}</td>
              <td>{{ formatAmount(payment.water) }}</td>
              <td>{{ formatAmount(payment.electricity) }}</td>
              <td :class="{ 'negative-amount': payment.total < 0 }"><strong>{{ formatAmount(payment.total) }}</strong></td>
              <td :class="`status-${payment.status}`">{{ getStatusLabel(payment.status) }}</td>
              <td v-if="showDeleteButtons">
                <button @click="handleDeleteGroup(payment)" class="delete-btn">
                  🗑️ 删除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="selectedGroups.length > 0 && showDeleteButtons" class="batch-actions">
          <span>已选择 {{ selectedGroups.length }} 条记录</span>
          <button @click="handleBatchDelete" class="batch-delete-btn">
            🗑️ 批量删除
          </button>
        </div>
      </div>
    </main>

    <!-- 已忽略警告详情对话框 -->
    <el-dialog
      v-model="showIgnoredWarningsDialog"
      title="已忽略的漏交提醒"
      width="800px"
    >
      <el-table :data="ignoredWarnings" style="width: 100%">
        <el-table-column prop="roomNumber" label="房间号" width="100" />
        <el-table-column prop="message" label="漏交月份" width="200" />
        <el-table-column prop="reason" label="忽略原因" min-width="180" />
        <el-table-column label="忽略时间" width="160">
          <template #default="scope">
            {{ formatIgnoredAt(scope.row.ignoredAt) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="scope">
            <el-button 
              type="primary" 
              size="small" 
              link 
              @click="restoreWarning(scope.row.id)"
            >
              恢复
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="showIgnoredWarningsDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.payments-view {
  min-height: 100vh;
  background-color: #f5f5f5;
}

.view-header {
  background: white;
  padding: 1.5rem 2rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.view-header h1 {
  margin: 0;
  color: #333;
}

.view-content {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

/* 水电收益统计样式 */
.utility-profit-card {
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.utility-bills-list-card {
  background: white;
  border-radius: 8px;
  padding: 0.5rem 1.5rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.bills-list-title {
  font-weight: 600;
  font-size: 0.95rem;
  color: #303133;
}

.bill-card-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.6rem 0;
  border-bottom: 1px solid #f0f0f0;
}

.bill-card-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.bill-series {
  font-weight: 600;
}

.bill-cost {
  font-weight: 600;
  color: #f56c6c;
}

.bill-card-actions {
  display: flex;
  gap: 0.25rem;
}

.profit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.profit-header h2 {
  margin: 0;
  font-size: 1.25rem;
  color: #333;
}

.profit-stats {
  display: flex;
  gap: 2rem;
  margin-bottom: 1.5rem;
}

.stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 1rem;
  border-radius: 8px;
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
}

.stat-item.total {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.stat-label {
  font-size: 0.875rem;
  color: #666;
}

.stat-item.total .stat-label {
  color: rgba(255, 255, 255, 0.9);
}

.stat-value {
  font-size: 1.1rem;
  font-weight: 700;
  color: #333;
}

.stat-item.total .stat-value {
  color: white;
  font-size: 1.25rem;
}

.water-profit {
  color: #409eff;
}

.electric-profit {
  color: #f59e0b;
}

.monthly-breakdown {
  margin-top: 1.5rem;
}

.monthly-breakdown h3 {
  margin: 0 0 1rem 0;
  font-size: 1rem;
  color: #333;
}

.profit-value {
  font-weight: 700;
  color: #67c23a;
  font-size: 0.875rem;
}

.total-profit {
  font-weight: 700;
  color: #667eea;
  font-size: 1rem;
}

.loading {
  text-align: center;
  padding: 2rem;
  color: #666;
}

.payments-list {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

table {
  width: 100%;
  border-collapse: collapse;
}

thead {
  background-color: #f9f9f9;
}

th {
  padding: 1rem;
  text-align: left;
  font-weight: 600;
  color: #555;
}

td {
  padding: 1rem;
  border-top: 1px solid #eee;
}

.status-pending {
  color: #ff9800;
}

.status-completed {
  color: #4caf50;
}

.status-overdue {
  color: #f44336;
}

.status-cancelled {
  color: #999;
}

/* 收租概况样式 */
.global-time-control {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
  background: linear-gradient(135deg, #f0f5ff 0%, #e8f4f8 100%);
  border: 1px solid #d0e3f0;
  border-radius: 10px;
  padding: 0.6rem 1rem;
}

.time-control-label {
  font-size: 0.9rem;
  color: #409eff;
  font-weight: 500;
}

.time-control-hint {
  font-size: 0.8rem;
  color: #909399;
  margin-left: 0.3rem;
}

.time-control-link {
  font-size: 0.8rem;
  color: #409eff;
  margin-left: auto;
  text-decoration: none;
}
.time-control-link:hover {
  text-decoration: underline;
}

.rent-collection {
  margin-bottom: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.collection-month {
  background: white;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  padding: 1rem 1.25rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.collection-summary {
  margin-bottom: 0.75rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #f0f0f0;
}

.summary-title {
  font-weight: 700;
  font-size: 1.05rem;
  color: #303133;
  margin-bottom: 0.6rem;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.6rem;
}

.summary-card {
  border-radius: 8px;
  padding: 0.6rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  cursor: pointer;
  transition: box-shadow 0.2s;
}

.summary-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.12);
}

.card-total {
  background: linear-gradient(135deg, #e8f4fd, #d4ecfc);
  border: 1px solid #b8daff;
}

.card-paid {
  background: linear-gradient(135deg, #eaf8e8, #d4f0cf);
  border: 1px solid #b8e6b0;
}

.card-unpaid {
  background: linear-gradient(135deg, #fef0f0, #fce4e4);
  border: 1px solid #f5c4c4;
}

.sc-label {
  font-size: 0.75rem;
  color: #909399;
  font-weight: 500;
}

.sc-value {
  font-size: 1.1rem;
  font-weight: 700;
  color: #303133;
}

.sc-amount {
  font-size: 0.95rem;
  font-weight: 600;
}

.card-total .sc-amount { color: #409eff; }
.card-paid .sc-amount { color: #67c23a; }
.card-unpaid .sc-amount { color: #f56c6c; }

.section-label {
  font-size: 0.8rem;
  font-weight: 600;
  margin-bottom: 0.4rem;
  padding-left: 0.25rem;
}

.unpaid-label { color: #c45656; }
.paid-label { color: #529b2e; }

.unpaid-section {
  margin-bottom: 0.6rem;
}

/* 房间标签列表 */
.room-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.room-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  border-radius: 6px;
  padding: 0.3rem 0.65rem;
  font-size: 0.8rem;
  line-height: 1.4;
}

.chip-unpaid {
  background: #fff5f5;
  border: 1px solid #fbc4c4;
}

.chip-paid {
  background: #f7fdf5;
  border: 1px solid #c2e7b0;
}

.chip-skipped {
  background: #f9fafb;
  border: 1px solid #dcdfe6;
}

.chip-name {
  font-weight: 700;
  color: #303133;
}

.chip-due {
  color: #e6a23c;
  font-size: 0.75rem;
}

.chip-cycle {
  color: #e6a23c;
  font-size: 0.7rem;
}

.chip-rent {
  color: #f56c6c;
  font-weight: 600;
}

.chip-rent-paid {
  color: #67c23a;
}

.chip-reason {
  color: #909399;
  font-size: 0.75rem;
}

/* 手机端适配 */
@media (max-width: 768px) {
  .collection-month {
    padding: 0.75rem;
    border-radius: 8px;
  }

  .summary-cards {
    grid-template-columns: repeat(3, 1fr);
    gap: 0.4rem;
  }

  .summary-card {
    padding: 0.5rem 0.5rem;
    border-radius: 6px;
  }

  .sc-label {
    font-size: 0.7rem;
  }

  .sc-value {
    font-size: 0.95rem;
  }

  .sc-amount {
    font-size: 0.85rem;
  }

  .room-chip {
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
  }

  .section-label {
    font-size: 0.75rem;
  }
}

.skipped-room-item .room-number {
  font-weight: 700;
  color: #909399;
}

.room-reason {
  color: #909399;
  font-size: 0.8rem;
}

/* 漏交提醒样式 */
.warning-alert {
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 8px;
  padding: 1rem 1.5rem;
  margin-bottom: 1.5rem;
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  box-shadow: 0 2px 4px rgba(255, 193, 7, 0.2);
}

.alert-icon {
  font-size: 1.5rem;
  flex-shrink: 0;
}

.alert-content {
  flex: 1;
}

.alert-content strong {
  color: #856404;
  display: block;
  margin-bottom: 0.5rem;
}

.alert-content ul {
  margin: 0;
  padding-left: 0;
  list-style: none;
}

.warning-item {
  color: #856404;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  justify-content: space-between;
}

.warning-item:last-child {
  margin-bottom: 0;
}

.ignore-btn {
  font-size: 0.875rem;
  padding: 0.25rem 0.5rem;
}

/* 筛选工具栏样式 */
.filter-toolbar {
  background: white;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  margin-bottom: 1.5rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.filter-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #333;
  font-weight: 500;
}

.room-select {
  padding: 0.5rem 2rem 0.5rem 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  font-size: 0.9rem;
  color: #333;
  cursor: pointer;
  min-width: 150px;
}

.room-select:hover {
  border-color: #409eff;
}

.room-select:focus {
  outline: none;
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.1);
}

.filter-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #409eff;
  font-size: 0.9rem;
  background: #ecf5ff;
  padding: 0.5rem 1rem;
  border-radius: 4px;
}

.clear-btn {
  background: #409eff;
  color: white;
  border: none;
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.2s;
}

.clear-btn:hover {
  background: #66b1ff;
}

/* 图表容器样式 */
.chart-container {
  background: white;
  border-radius: 8px;
  padding: 2rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

/* 负数金额样式 */
.negative-amount {
  color: #f56c6c;
  font-weight: bold;
}

/* 删除按钮样式 */
.delete-btn {
  padding: 0.3rem 0.6rem;
  background: #f56c6c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background 0.3s;
}

.delete-btn:hover {
  background: #f78989;
}

/* 批量操作栏样式 */
.batch-actions {
  background: #f0f9ff;
  border-top: 1px solid #409eff;
  padding: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.batch-actions span {
  color: #409eff;
  font-weight: 600;
}

.batch-delete-btn {
  padding: 0.5rem 1rem;
  background: #f56c6c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background 0.3s;
}

.batch-delete-btn:hover {
  background: #f78989;
}

/* 移动端优化 */
.hidden-mobile {
  display: block;
}

.hidden-desktop {
  display: none;
}

@media (max-width: 768px) {
  .view-content {
    padding: 0.75rem;
  }

  /* 水电收益统计 - 手机端适配 */
  .utility-profit-card {
    padding: 0.75rem;
    margin-bottom: 1rem;
  }

  .profit-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .profit-header h2 {
    font-size: 1rem;
  }

  .profit-stats {
    flex-direction: column;
    gap: 0.75rem;
    margin-bottom: 1rem;
  }

  .stat-item {
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem;
  }

  .stat-item.total {
    flex-direction: row;
  }

  .stat-value {
    font-size: 1rem;
  }

  .stat-item.total .stat-value {
    font-size: 1.1rem;
  }

  /* 月度明细 - 手机端用卡片替代表格 */
  .monthly-breakdown .el-table {
    display: none !important;
  }

  .hidden-mobile {
    display: none !important;
  }

  .hidden-desktop {
    display: block !important;
  }

  .monthly-cards {
    display: flex !important;
    flex-direction: column;
    gap: 0.75rem;
  }

  .monthly-card {
    background: #f9fafb;
    border-radius: 8px;
    padding: 0.75rem;
  }

  .monthly-card-summary {
    background: #ecf5ff;
    border: 1px solid #409eff;
    margin-top: 0.5rem;
  }

  .monthly-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
    font-weight: 600;
    font-size: 0.9rem;
  }

  .monthly-card-body {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
    font-size: 0.8rem;
  }

  .monthly-card-cell {
    display: flex;
    justify-content: space-between;
  }

  .monthly-card-cell .label {
    color: #666;
  }

  .monthly-card-total {
    grid-column: 1 / -1;
    text-align: center;
    padding-top: 0.5rem;
    border-top: 1px solid #eee;
    font-weight: 700;
    color: #667eea;
    font-size: 1rem;
  }

  .payments-list {
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch;
  }

  .payments-list table {
    min-width: 800px;
  }

  .filter-toolbar {
    flex-direction: column;
    gap: 12px;
  }

  .filter-label {
    width: 100%;
    flex-direction: column;
    align-items: flex-start;
  }

  .room-select,
  .filter-label .el-date-picker {
    width: 100% !important;
  }

  .global-time-control {
    flex-wrap: wrap;
    gap: 6px;
  }

  .time-control-label {
    font-size: 14px;
  }
}
</style>
