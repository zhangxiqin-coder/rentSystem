<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { paymentApi } from '@/api/payment'
import { roomApi } from '@/api/room'
import { useOverdueConfig } from '@/composables/useOverdueConfig'
import type { Payment } from '@/types'
import type { Room } from '@/types'
import { useAmountVisibility } from '@/composables/useAmountVisibility'
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

const payments = ref<Payment[]>([])
const rooms = ref<Room[]>([])
const loading = ref(false)
const selectedRoomId = ref<number | null>(null)
const { hideAmounts, formatAmount } = useAmountVisibility()

// 批量选择相关
const selectedGroups = ref<string[]>([])
const selectAll = ref(false)

const { overdueCutoffDate, lookbackMonths } = useOverdueConfig()

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
  return Object.values(groups).sort((a, b) => 
    new Date(b.payment_date).getTime() - new Date(a.payment_date).getTime()
  )
})

// 检测漏交月份的提醒
const missedPaymentWarnings = computed(() => {
  const warnings: string[] = []
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
          warnings.push(
            `${room.room_number} 可能有 ${Math.round(gapBetweenPeriods / 30)} 个月未交租 ` +
            `(${sorted[i - 1].period_end} → ${sorted[i].period_start})`
          )
        }
      } else if (gapDays > expectedGapDays * 1.5) {
        // 没有 period 信息时，用天数间隔判断（允许50%的容差）
        const missedMonths = Math.round(gapDays / 30) - cycle
        if (missedMonths > 0) {
          warnings.push(
            `${room.room_number} 可能有 ${missedMonths} 个月未交租 ` +
            `(${sorted[i - 1].payment_date.split('T')[0]} → ${sorted[i].payment_date.split('T')[0]})`
          )
        }
      }
    }
  })
  
  return warnings
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

const loadPayments = async () => {
  loading.value = true
  try {
    const [paymentsRes, roomsRes] = await Promise.all([
      paymentApi.getPayments({ page: 1, size: 1000 }),
      roomApi.getRooms({ page: 1, size: 100 })
    ])
    payments.value = paymentsRes.data.items
    rooms.value = roomsRes.data.items || roomsRes.data
  } catch (error) {
    console.error('加载缴费记录失败:', error)
  } finally {
    loading.value = false
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
  loadPayments()
})
</script>

<template>
  <div class="payments-view">
    <header class="view-header">
      <h1>缴费记录</h1>
    </header>

    <main class="view-content">
      <!-- 漏交提醒 -->
      <div v-if="missedPaymentWarnings.length > 0" class="warning-alert">
        <div class="alert-icon">⚠️</div>
        <div class="alert-content">
          <strong>漏交提醒：</strong>
          <ul>
            <li v-for="(warning, index) in missedPaymentWarnings" :key="index">{{ warning }}</li>
          </ul>
        </div>
      </div>

      <!-- 收租概况 -->
      <div class="collection-toolbar">
        <span class="collection-toolbar-label">收租概况：显示最近</span>
        <el-input-number
          v-model="lookbackMonths"
          :min="1"
          :max="12"
          :step="1"
          size="small"
          style="width: 100px"
        />
        <span class="collection-toolbar-label">个月</span>
      </div>
      <div v-if="rentCollectionByMonth.length > 0" class="rent-collection">
        <div v-for="monthGroup in rentCollectionByMonth" :key="monthGroup.key" class="collection-month">
          <div class="collection-summary">
            <span class="collection-month-label">{{ monthGroup.label }}</span>
            <span class="collection-stat">
              应收 <strong>{{ monthGroup.unpaid.length + monthGroup.paid.length }}</strong> 间
              <template v-if="!hideAmounts">
                <span class="stat-divider">|</span>
                合计 <strong>¥{{ monthGroup.totalRent }}</strong>
                <span class="stat-divider">|</span>
                已收 <strong class="stat-paid">¥{{ monthGroup.paidRent }}</strong>
                <span class="stat-divider">|</span>
                未收 <strong class="stat-unpaid">¥{{ monthGroup.totalRent - monthGroup.paidRent }}</strong>
              </template>
            </span>
          </div>

          <!-- 未收 -->
          <div v-if="monthGroup.unpaid.length > 0" class="unpaid-section">
            <div class="section-label unpaid-label">未收 {{ monthGroup.unpaid.length }} 间</div>
            <div class="unpaid-room-list">
              <div v-for="item in monthGroup.unpaid" :key="`u-${monthGroup.key}-${item.room.id}`" class="unpaid-room-item">
                <span class="room-number">{{ item.room.room_number }}</span>
                <span class="room-due">应交{{ item.dueDateStr }}</span>
                <span class="room-cycle" v-if="item.cycle > 1">（{{ item.cycleLabel }}付）</span>
                <span class="room-rent">{{ hideAmounts ? '****' : `¥${item.rentDue}` }}</span>
              </div>
            </div>
          </div>

          <!-- 已收 -->
          <div v-if="monthGroup.paid.length > 0" class="paid-section">
            <div class="section-label paid-label">已收 {{ monthGroup.paid.length }} 间</div>
            <div class="paid-room-list">
              <div v-for="item in monthGroup.paid" :key="`p-${monthGroup.key}-${item.room.id}`" class="paid-room-item">
                <span class="room-number">{{ item.room.room_number }}</span>
                <span class="room-due">{{ item.dueDateStr }}交</span>
                <span class="room-cycle" v-if="item.cycle > 1">（{{ item.cycleLabel }}付）</span>
                <span class="room-rent paid-rent">{{ hideAmounts ? '****' : `¥${item.rentDue}` }}</span>
              </div>
            </div>
          </div>

          <!-- 不收租 -->
          <div v-if="monthGroup.skipped.length > 0" class="skipped-section">
            <div class="section-label skipped-label">不收租 {{ monthGroup.skipped.length }} 间</div>
            <div class="skipped-room-list">
              <div v-for="item in monthGroup.skipped" :key="`s-${monthGroup.key}-${item.room.id}`" class="skipped-room-item">
                <span class="room-number">{{ item.room.room_number }}</span>
                <span class="room-reason">{{ item.reason }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 筛选工具栏 -->
      <div class="filter-toolbar">
        <label class="filter-label">
          筛选房号：
          <select v-model="selectedRoomId" class="room-select">
            <option :value="null">全部房间</option>
            <option v-for="room in rooms" :key="room.id" :value="room.id">
              {{ room.room_number }}
            </option>
          </select>
        </label>
        <span v-if="selectedRoomId" class="filter-info">
          已选择：{{ rooms.find(r => r.id === selectedRoomId)?.room_number }}
          <button @click="selectedRoomId = null" class="clear-btn">清除</button>
        </span>
      </div>

      <!-- 月度统计图表 -->
      <div v-if="monthlyStats.length > 0" class="chart-container">
        <v-chart :option="chartOption" style="height: 400px" autoresize />
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
              <td>
                <button @click="handleDeleteGroup(payment)" class="delete-btn">
                  🗑️ 删除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="selectedGroups.length > 0" class="batch-actions">
          <span>已选择 {{ selectedGroups.length }} 条记录</span>
          <button @click="handleBatchDelete" class="batch-delete-btn">
            🗑️ 批量删除
          </button>
        </div>
      </div>
    </main>
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
.collection-toolbar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  background: white;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 0.5rem 1rem;
}

.collection-toolbar-label {
  font-size: 0.875rem;
  color: #606266;
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
  border-radius: 8px;
  padding: 1rem 1.5rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.06);
}

.collection-summary {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}

.collection-month-label {
  font-weight: 700;
  font-size: 1rem;
  color: #303133;
}

.collection-stat {
  font-size: 0.875rem;
  color: #606266;
}

.collection-stat strong {
  font-size: 1rem;
}

.stat-divider {
  color: #dcdfe6;
  margin: 0 0.25rem;
}

.stat-paid {
  color: #67c23a;
}

.stat-unpaid {
  color: #f56c6c;
}

.section-label {
  font-size: 0.85rem;
  font-weight: 600;
  margin-bottom: 0.4rem;
  padding-left: 0.25rem;
}

.unpaid-label {
  color: #c45656;
}

.paid-label {
  color: #529b2e;
}

.unpaid-section {
  margin-bottom: 0.75rem;
}

.paid-section {
}

.unpaid-room-list, .paid-room-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.unpaid-room-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: #fef0f0;
  border: 1px solid #fbc4c4;
  border-radius: 6px;
  padding: 0.35rem 0.75rem;
  font-size: 0.875rem;
}

.paid-room-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: #f0f9eb;
  border: 1px solid #c2e7b0;
  border-radius: 6px;
  padding: 0.35rem 0.75rem;
  font-size: 0.875rem;
}

.unpaid-room-item .room-number,
.paid-room-item .room-number {
  font-weight: 700;
  color: #303133;
}

.unpaid-room-item .room-due,
.paid-room-item .room-due {
  color: #e6a23c;
  font-size: 0.8rem;
}

.unpaid-room-item .room-cycle,
.paid-room-item .room-cycle {
  color: #e6a23c;
  font-size: 0.8rem;
}

.unpaid-room-item .room-rent {
  color: #f56c6c;
  font-weight: 600;
}

.paid-rent {
  color: #67c23a;
  font-weight: 600;
}

.skipped-section {
  margin-top: 0.5rem;
}

.skipped-label {
  color: #909399;
}

.skipped-room-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.skipped-room-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: #f5f7fa;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  padding: 0.35rem 0.75rem;
  font-size: 0.875rem;
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
  padding-left: 1.5rem;
  list-style: disc;
}

.alert-content li {
  color: #856404;
  margin-bottom: 0.25rem;
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
</style>
