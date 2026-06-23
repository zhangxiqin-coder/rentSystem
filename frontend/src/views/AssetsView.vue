<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Wallet, Edit, TrendCharts } from '@element-plus/icons-vue'
import { assetApi } from '@/api/assets'
import { useAmountVisibility } from '@/composables/useAmountVisibility'
import { useAuthStore } from '@/stores/auth'
import type { AssetSummary, AssetPlatformDetail, AssetRecord, AssetTrend } from '@/types'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'

use([
  CanvasRenderer,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

const authStore = useAuthStore()
const { hideAmounts, formatAmount } = useAmountVisibility()

const loading = ref(false)
const summary = ref<AssetSummary | null>(null)

// 趋势数据
const trendData = ref<AssetTrend | null>(null)
const trendLoading = ref(false)

// 历史总资产快照（从外部记录补充，无收益数据）
const HISTORICAL_SNAPSHOTS: { date: string; balance: number }[] = [
  { date: '2020-12-01', balance: 3300000 },
  { date: '2021-11-01', balance: 4104000 },
  { date: '2022-04-01', balance: 4069000 },
  { date: '2025-10-01', balance: 6969066 }
]

// 合并历史快照到趋势数据
const mergedPoints = computed(() => {
  if (!trendData.value) return []
  const points = [...(trendData.value.points || [])]
  for (const snap of HISTORICAL_SNAPSHOTS) {
    const existing = points.find(p => p.date.startsWith(snap.date.slice(0, 7)))
    if (!existing) {
      points.push({ date: snap.date, total_balance: snap.balance, total_earnings: 0, earnings_delta: 0 } as any)
    }
  }
  if (points.length === 0) return []
  points.sort((a, b) => a.date.localeCompare(b.date))
  return points
})

// 对2026年数据按3个月间隔采样，保留最新点
const sampledBalancePoints = computed(() => {
  const points = mergedPoints.value
  if (points.length === 0) return []
  const currentYear = '2026'
  // 找出2026年最新点（数据中日期最大的2026年点）
  const latest2026 = points.filter(p => p.date.startsWith(currentYear)).pop()
  const samplingMonths = [2, 5, 8, 11] // 2月、5月、8月、11月
  return points.filter(p => {
    if (!p.date.startsWith(currentYear)) return true // 非2026年的全保留（历史快照）
    // 2026年的，只保留采样月份和最新那天
    const month = parseInt(p.date.slice(5, 7))
    const isSamplingMonth = samplingMonths.includes(month)
    const isLatest = latest2026 && p.date === latest2026.date
    return isSamplingMonth || isLatest
  })
})

// 总资产趋势图（跨年，从0开始）
const balanceTrendOption = computed(() => {
  const points = sampledBalancePoints.value
  if (points.length === 0) return null
  const dates = points.map(p => p.date)
  const balances = points.map(p => p.total_balance)
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any[]) => {
        const date = params[0].axisValue
        let html = `<strong>${date}</strong><br/>`
        for (const p of params) {
          html += `${p.marker} ${p.seriesName}: ¥${Number(p.value).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}<br/>`
        }
        return html
      }
    },
    grid: { left: 80, right: 40, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: dates, axisLabel: { rotate: 30, fontSize: 11 } },
    yAxis: {
      type: 'value',
      name: '总资产 (¥)',
      min: 0,
      axisLabel: { formatter: (v: number) => v >= 10000 ? (v / 10000).toFixed(0) + '万' : v.toFixed(0) }
    },
    series: [{
      name: '总资产',
      type: 'line',
      data: balances,
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      lineStyle: { width: 2 },
      itemStyle: { color: '#409EFF' },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(64,158,255,0.25)' },
            { offset: 1, color: 'rgba(64,158,255,0.02)' }
          ]
        }
      }
    }]
  }
})

// 当年收益趋势图（仅本年，双Y轴：收益+总资产）
const earningsTrendOption = computed(() => {
  const points = mergedPoints.value
  if (points.length === 0) return null
  const currentYear = String(new Date().getFullYear())
  const yearPoints = points.filter(p => p.date.startsWith(currentYear))
  if (yearPoints.length === 0) return null
  const dates = yearPoints.map(p => p.date)
  const balances = yearPoints.map(p => p.total_balance)
  const earnings = yearPoints.map(p => p.total_earnings)
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any[]) => {
        const date = params[0].axisValue
        let html = `<strong>${date}</strong><br/>`
        for (const p of params) {
          const val = Number(p.value)
          const prefix = p.seriesName.includes('收益') ? '' : ''
          html += `${p.marker} ${p.seriesName}: ¥${val.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}<br/>`
        }
        return html
      }
    },
    legend: { data: ['本年总资产', '当年收益'], top: 0, right: 20, textStyle: { fontSize: 12 } },
    grid: { left: 80, right: 60, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: dates, axisLabel: { rotate: 30, fontSize: 11 } },
    yAxis: [
      {
        type: 'value',
        name: '总资产 (¥)',
        min: 0,
        axisLabel: { formatter: (v: number) => v >= 10000 ? (v / 10000).toFixed(0) + '万' : v.toFixed(0) }
      },
      {
        type: 'value',
        name: '收益 (¥)',
        axisLabel: { formatter: (v: number) => v >= 10000 ? (v / 10000).toFixed(1) + '万' : v.toFixed(0) },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '本年总资产',
        type: 'line',
        yAxisIndex: 0,
        data: balances,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2, color: '#409EFF' },
        itemStyle: { color: '#409EFF' }
      },
      {
        name: '当年收益',
        type: 'line',
        yAxisIndex: 1,
        data: earnings,
        smooth: true,
        symbol: 'diamond',
        symbolSize: 8,
        lineStyle: { width: 2 },
        itemStyle: {
          color: (params: any) => params.value >= 0 ? '#67C23A' : '#F56C6C'
        }
      }
    ]
  }
})

// 预设平台列表
const ALL_PLATFORMS = [
  '支付宝', '且慢', '网商银行', '腾讯理财通',
  '雪球', '京东金融', '平安证券', '其他',
]

// 已启用的平台
const getEnabledPlatforms = (): string[] => {
  try {
    const saved = localStorage.getItem('asset_enabled_platforms')
    return saved ? JSON.parse(saved) : ALL_PLATFORMS
  } catch {
    return ALL_PLATFORMS
  }
}
const enabledPlatforms = ref<string[]>(getEnabledPlatforms())

// 选取的年份
const selectedYear = ref<string>('')
const availableYears = computed(() => {
  if (!summary.value) return []
  const years = Object.keys(summary.value.yearly_earnings).sort().reverse()
  return years
})

// 当前显示的收益（根据选取的年份）
const displayEarnings = computed(() => {
  if (!summary.value) return 0
  if (!selectedYear.value) return summary.value.total_earnings
  return summary.value.yearly_earnings[selectedYear.value] || 0
})

// 获取平台上上次的余额和收益
const getPlatformData = (name: string): { balance: number; earnings: number } => {
  if (!summary.value) return { balance: 0, earnings: 0 }
  const p = summary.value.platforms.find(x => x.name === name)
  return p ? { balance: p.current_balance, earnings: p.total_earnings } : { balance: 0, earnings: 0 }
}

// 上报对话框
const showReportDialog = ref(false)
const reportForm = ref({
  platform_name: '',
  record_type: 'earnings' as 'balance' | 'earnings' | 'balance_only' | 'transfer_in' | 'transfer_out',
  reported_balance: 0,
  reported_earnings: 0,
  amount: 0,
  notes: ''
})
const reportLoading = ref(false)

// 展开记录
const expandedPlatformIds = ref<Set<number>>(new Set())

const loadSummary = async () => {
  loading.value = true
  try {
    summary.value = await assetApi.getSummary()
    // 默认选取最新年份
    const years = Object.keys(summary.value.yearly_earnings).sort()
    if (years.length > 0 && !selectedYear.value) {
      selectedYear.value = years[years.length - 1]
    }
  } catch (error) {
    ElMessage.error('加载资产数据失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const loadTrend = async () => {
  trendLoading.value = true
  try {
    trendData.value = await assetApi.getTrend()
  } catch (error) {
    console.error('加载趋势数据失败', error)
  } finally {
    trendLoading.value = false
  }
}

// 打开上报对话框
const openReport = (platformName?: string) => {
  const data = platformName ? getPlatformData(platformName) : { balance: 0, earnings: 0 }
  reportForm.value = {
    platform_name: platformName || '',
    record_type: 'earnings',
    reported_balance: data.balance,
    reported_earnings: data.earnings,
    amount: 0,
    notes: ''
  }
  showReportDialog.value = true
}

const submitReport = async () => {
  if (!reportForm.value.platform_name) {
    ElMessage.warning('请选择平台')
    return
  }
  reportLoading.value = true
  try {
    // 先找到或创建平台
    const platforms = await assetApi.listPlatforms()
    let platform = platforms.find(p => p.name === reportForm.value.platform_name)

    if (!platform) {
      const data = getPlatformData(reportForm.value.platform_name)
      platform = await assetApi.createPlatform({
        name: reportForm.value.platform_name,
        current_balance: data.balance,
      })
    }

    // 创建记录
    const data: any = {
      platform_id: platform.id,
      record_type: reportForm.value.record_type,
      notes: reportForm.value.notes || undefined
    }

    if (reportForm.value.record_type === 'balance') {
      data.reported_balance = Number(reportForm.value.reported_balance) || 0
      data.reported_earnings = Number(reportForm.value.reported_earnings) || 0
    } else if (reportForm.value.record_type === 'earnings') {
      data.amount = Number(reportForm.value.amount) || 0
    } else if (reportForm.value.record_type === 'balance_only') {
      data.reported_balance = Number(reportForm.value.reported_balance) || 0
    } else {
      data.amount = Number(reportForm.value.amount) || 0
    }

    await assetApi.createRecord(data)
    ElMessage.success('上报成功')
    showReportDialog.value = false
    await loadSummary()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '上报失败')
    console.error(error)
  } finally {
    reportLoading.value = false
  }
}

// 选择平台时自动填充当前数据
const onPlatformChange = (name: string) => {
  const data = getPlatformData(name)
  reportForm.value.reported_balance = data.balance
  reportForm.value.reported_earnings = data.earnings
}

// 赵平飞年度统计数据
const zhaopingfeiSummary = ref<{
  years: Array<{ year: string; transfer_in: number; transfer_out: number; net: number }>
  total_in: number
  total_out: number
  total_net: number
} | null>(null)

// 展开/收起记录
const toggleRecords = async (platformId: number) => {
  const s = new Set(expandedPlatformIds.value)
  if (s.has(platformId)) {
    s.delete(platformId)
  } else {
    s.add(platformId)
    // 如果是赵平飞，加载年度统计
    const p = summary.value?.platforms.find(x => x.id === platformId)
    if (p && p.name === '赵平飞') {
      try {
        zhaopingfeiSummary.value = await assetApi.getZhaopingfeiSummary()
      } catch (e) {
        console.error('加载赵平飞统计失败', e)
      }
    }
  }
  expandedPlatformIds.value = s
}

const formatDate = (d: string) => {
  const date = new Date(d)
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

const recordTypeLabel = (type: string) => {
  switch (type) {
    case 'balance': return '余额+收益'
    case 'earnings': return '仅收益'
    case 'balance_only': return '仅余额'
    case 'transfer_in': return '转入'
    case 'transfer_out': return '转出'
    default: return type
  }
}

const recordTypeTag = (type: string) => {
  switch (type) {
    case 'balance': return 'primary'
    case 'earnings': return 'success'
    case 'balance_only': return 'warning'
    case 'transfer_in': return 'success'
    case 'transfer_out': return 'warning'
    default: return 'info'
  }
}

// 编辑对话框
const showEditDialog = ref(false)
const editingRecord = ref<AssetRecord | null>(null)
const editForm = ref({
  reported_balance: 0,
  reported_earnings: 0,
  amount: 0,
  notes: ''
})
const editLoading = ref(false)

const openEdit = (record: AssetRecord) => {
  editingRecord.value = record
  editForm.value = {
    reported_balance: record.reported_balance || 0,
    reported_earnings: record.reported_earnings || 0,
    amount: record.amount || 0,
    notes: record.notes || ''
  }
  showEditDialog.value = true
}

const submitEdit = async () => {
  if (!editingRecord.value) return
  editLoading.value = true
  try {
    const data: any = {}
    if (editingRecord.value.record_type === 'balance') {
      data.reported_balance = Number(editForm.value.reported_balance) || 0
      data.reported_earnings = Number(editForm.value.reported_earnings) || 0
    } else if (editingRecord.value.record_type === 'earnings') {
      data.amount = Number(editForm.value.amount) || 0
    } else if (editingRecord.value.record_type === 'balance_only') {
      if (editForm.value.reported_balance !== null && editForm.value.reported_balance !== undefined && editForm.value.reported_balance !== '') {
        data.reported_balance = Number(editForm.value.reported_balance)
      }
    } else {
      data.amount = Number(editForm.value.amount) || 0
    }
    if (editForm.value.notes) {
      data.notes = editForm.value.notes
    }
    await assetApi.updateRecord(editingRecord.value.id, data)
    ElMessage.success('编辑成功')
    showEditDialog.value = false
    await loadSummary()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '编辑失败')
    console.error(error)
  } finally {
    editLoading.value = false
  }
}

// 移动端响应式检测
const isMobile = ref(window.innerWidth < 768)
const checkMobile = () => { isMobile.value = window.innerWidth < 768 }
window.addEventListener('resize', checkMobile)

onMounted(() => {
  loadSummary()
  loadTrend()
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})
</script>

<template>
  <div class="assets-page">
    <div class="page-header">
      <h2>
        <el-icon :size="24"><Wallet /></el-icon>
        个人资产
      </h2>
      <div class="header-actions">
        <el-button type="success" :icon="Plus" @click="openReport()">上报</el-button>
        <el-button type="default" @click="loadSummary">刷新</el-button>
      </div>
    </div>

    <!-- 总资产卡片 -->
    <div v-loading="loading" class="summary-cards">
      <el-card class="summary-card total-balance">
        <div class="card-label">总资产</div>
        <div class="card-value">{{ summary ? formatAmount(summary.total_balance) : '-' }}</div>
      </el-card>
      <el-card class="summary-card total-earnings">
        <div class="card-label-row">
          <div class="card-label">
            <template v-if="selectedYear">{{ selectedYear }}年收益</template>
            <template v-else>当年收益</template>
          </div>
          <el-select
            v-if="availableYears.length > 1"
            v-model="selectedYear"
            size="small"
            style="width: 100px;"
            @change="() => {}"
          >
            <el-option
              v-for="year in availableYears"
              :key="year"
              :label="year + '年'"
              :value="year"
            />
          </el-select>
        </div>
        <div :class="['card-value', 'earnings-value', displayEarnings < 0 ? 'negative' : '']">
          {{ summary ? formatAmount(displayEarnings) : '-' }}
        </div>
      </el-card>
    </div>

    <!-- 总资产趋势图 -->
    <el-card class="trend-card" v-loading="trendLoading">
      <div class="trend-header">
        <el-icon :size="18"><TrendCharts /></el-icon>
        <span>总资产趋势</span>
      </div>
      <div v-if="balanceTrendOption" class="trend-chart">
        <VChart :option="balanceTrendOption" autoresize style="width:100%;height:320px" />
      </div>
      <div v-else class="trend-empty">
        <el-empty description="暂无趋势数据，上报余额后自动生成" :image-size="80" />
      </div>
    </el-card>

    <!-- 2026年趋势图 -->
    <el-card class="trend-card" v-loading="trendLoading">
      <div class="trend-header">
        <el-icon :size="18"><TrendCharts /></el-icon>
        <span>2026年趋势</span>
      </div>
      <div v-if="earningsTrendOption" class="trend-chart">
        <VChart :option="earningsTrendOption" autoresize style="width:100%;height:260px" />
      </div>
      <div v-else class="trend-empty">
        <el-empty description="暂无当年收益数据" :image-size="80" />
      </div>
    </el-card>

    <!-- 各平台卡片 -->
    <div v-if="summary && summary.platforms.length === 0" class="empty-tip">
      <el-empty description="暂无资产数据，点击上方「上报」按钮开始记录" />
    </div>

    <div v-for="platform in summary?.platforms || []" :key="platform.id" class="platform-card">
      <el-card shadow="hover">
        <div class="platform-header">
          <div class="platform-info">
            <div class="platform-name">{{ platform.name }}</div>
            <div class="platform-balance">
              余额：<strong>{{ formatAmount(platform.current_balance) }}</strong>
            </div>
            <div :class="['platform-earnings', platform.total_earnings < 0 ? 'negative' : '']">
              {{ platform.current_year }}年收益：<strong>{{ formatAmount(platform.total_earnings) }}</strong>
              <span v-if="platform.annualized_return !== null" class="annualized-return" :class="platform.annualized_return >= 0 ? 'positive' : 'negative'">
                ({{ platform.annualized_return >= 0 ? '+' : '' }}{{ platform.annualized_return }}%)
              </span>
            </div>
          </div>
          <div class="platform-actions">
            <el-button type="primary" size="small" @click="openReport(platform.name)">上报</el-button>
            <el-button
              size="small"
              :type="expandedPlatformIds.has(platform.id) ? 'default' : 'info'"
              @click="toggleRecords(platform.id)"
            >
              {{ expandedPlatformIds.has(platform.id) ? '收起记录' : '查看记录' }}
            </el-button>
          </div>
        </div>

        <!-- 变动记录列表 -->
        <div v-if="expandedPlatformIds.has(platform.id)" class="record-list">
          <!-- 赵平飞：年度统计表 + 逐条明细 -->
          <template v-if="platform.name === '赵平飞'">
            <div class="zpf-summary-header">年度转账统计</div>
            <el-table v-if="zhaopingfeiSummary" :data="zhaopingfeiSummary.years" size="small" stripe class="zpf-table">
              <el-table-column prop="year" label="年份" min-width="60" />
              <el-table-column prop="transfer_in" label="转入" min-width="100">
                <template #default="{ row }">
                  <span class="transfer-in">{{ formatAmount(row.transfer_in) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="transfer_out" label="转出" min-width="100">
                <template #default="{ row }">
                  <span v-if="row.transfer_out > 0" class="transfer-out">{{ formatAmount(row.transfer_out) }}</span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column prop="net" label="净转入" min-width="100">
                <template #default="{ row }">
                  <span :class="row.net >= 0 ? 'transfer-in' : 'transfer-out'">{{ formatAmount(row.net) }}</span>
                </template>
              </el-table-column>
            </el-table>
            <div v-if="zhaopingfeiSummary" class="zpf-total">
              <span>合计：转入 {{ formatAmount(zhaopingfeiSummary.total_in) }}</span>
              <span v-if="zhaopingfeiSummary.total_out > 0"> / 转出 {{ formatAmount(zhaopingfeiSummary.total_out) }}</span>
              <span> / 净转入 <strong>{{ formatAmount(zhaopingfeiSummary.total_net) }}</strong></span>
            </div>
            <div class="zpf-records-divider">逐条明细</div>
            <div v-if="platform.records.length === 0" class="no-records">暂无变动记录</div>
            <div v-for="record in platform.records" :key="record.id" class="record-item">
              <div class="record-left">
                <el-tag :type="recordTypeTag(record.record_type)" size="small">
                  {{ recordTypeLabel(record.record_type) }}
                </el-tag>
                <span class="record-note" v-if="record.notes">{{ record.notes }}</span>
              </div>
              <div class="record-right">
                <template v-if="record.record_type === 'balance'">
                  <span class="record-balance">余额：{{ formatAmount(record.reported_balance || 0) }}</span>
                  <span :class="['record-earnings', (record.reported_earnings || 0) < 0 ? 'negative' : '']">收益：{{ formatAmount(record.reported_earnings || 0) }}</span>
                  <span v-if="record.calculated_transfer && record.calculated_transfer !== 0"
                    :class="['record-transfer', record.calculated_transfer > 0 ? 'transfer-in' : 'transfer-out']">
                    {{ record.calculated_transfer > 0 ? '转入' : '转出' }} {{ formatAmount(Math.abs(record.calculated_transfer)) }}
                  </span>
                </template>
                <template v-else-if="record.record_type === 'balance_only'">
                  <span class="record-balance">余额：{{ formatAmount(record.reported_balance || 0) }}</span>
                </template>
              <template v-else>
                  <span :class="record.record_type === 'transfer_in' ? 'transfer-in' : 'transfer-out'">
                    {{ formatAmount(record.amount || 0) }}
                  </span>
                </template>
                <span class="record-time">{{ formatDate(record.created_at) }}</span>
                <el-button
                  v-if="authStore.isSuperAdmin"
                  text
                  size="small"
                  type="primary"
                  :icon="Edit"
                  @click="openEdit(record)"
                  class="edit-btn"
                />
              </div>
            </div>
          </template>
          <!-- 其他平台：逐条记录 -->
          <template v-else>
          <div v-if="platform.records.length === 0" class="no-records">暂无变动记录</div>
          <div v-for="record in platform.records" :key="record.id" class="record-item">
            <div class="record-left">
              <el-tag :type="recordTypeTag(record.record_type)" size="small">
                {{ recordTypeLabel(record.record_type) }}
              </el-tag>
              <span class="record-note" v-if="record.notes">{{ record.notes }}</span>
            </div>
            <div class="record-right">
              <template v-if="record.record_type === 'balance'">
                <span class="record-balance">余额：{{ formatAmount(record.reported_balance || 0) }}</span>
                <span :class="['record-earnings', (record.reported_earnings || 0) < 0 ? 'negative' : '']">收益：{{ formatAmount(record.reported_earnings || 0) }}</span>
                <span v-if="record.calculated_transfer && record.calculated_transfer !== 0"
                  :class="['record-transfer', record.calculated_transfer > 0 ? 'transfer-in' : 'transfer-out']">
                  {{ record.calculated_transfer > 0 ? '转入' : '转出' }} {{ formatAmount(Math.abs(record.calculated_transfer)) }}
                </span>
              </template>
              <template v-else-if="record.record_type === 'balance_only'">
                <span class="record-balance">余额：{{ formatAmount(record.reported_balance || 0) }}</span>
              </template>
            <template v-else>
                <span :class="record.record_type === 'transfer_in' ? 'transfer-in' : 'transfer-out'">
                  {{ formatAmount(record.amount || 0) }}
                </span>
              </template>
              <span class="record-time">{{ formatDate(record.created_at) }}</span>
              <el-button
                v-if="authStore.isSuperAdmin"
                text
                size="small"
                type="primary"
                :icon="Edit"
                @click="openEdit(record)"
                class="edit-btn"
              />
            </div>
          </div>
          </template>
        </div>
      </el-card>
    </div>

    <!-- 上报对话框 -->
    <el-dialog v-model="showReportDialog" title="上报资产" :width="isMobile ? '92%' : '480px'" :top="isMobile ? '10px' : '15vh'" class="asset-dialog">
      <el-form :model="reportForm" :label-position="isMobile ? 'top' : 'right'" label-width="80px">
        <el-form-item label="平台">
          <el-select
            v-model="reportForm.platform_name"
            placeholder="选择平台"
            style="width:100%"
            @change="onPlatformChange"
          >
            <el-option
              v-for="name in enabledPlatforms"
              :key="name"
              :label="name"
              :value="name"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="上报类型">
          <el-radio-group v-model="reportForm.record_type" class="report-type-group">
            <el-radio-button value="earnings">仅收益</el-radio-button>
            <el-radio-button value="balance">余额+收益</el-radio-button>
            <el-radio-button value="balance_only">仅余额</el-radio-button>
            <el-radio-button value="transfer_in">转入</el-radio-button>
            <el-radio-button value="transfer_out">转出</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <template v-if="reportForm.record_type === 'balance'">
          <el-form-item label="当前余额">
            <el-input-number
              v-model="reportForm.reported_balance"
              :min="0"
              :precision="2"
              style="width:100%"
            />
          </el-form-item>
          <el-form-item label="当前收益">
            <el-input-number
              v-model="reportForm.reported_earnings"
              :min="-99999999"
              :precision="2"
              style="width:100%"
            />
          </el-form-item>
        </template>

        <template v-else-if="reportForm.record_type === 'earnings'">
          <el-form-item label="本次收益">
            <el-input-number
              v-model="reportForm.amount"
              :min="-99999999"
              :precision="2"
              style="width:100%"
            />
            <div class="form-tip">正数为盈利，负数为亏损。系统会自动更新累计收益和余额</div>
          </el-form-item>
        </template>

        <template v-else-if="reportForm.record_type === 'balance_only'">
          <el-form-item label="当前余额">
            <el-input-number
              v-model="reportForm.reported_balance"
              :min="0"
              :precision="2"
              style="width:100%"
            />
            <div class="form-tip">余额变化后，收益保持不变</div>
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="金额">
            <el-input-number
              v-model="reportForm.amount"
              :min="0.01"
              :precision="2"
              style="width:100%"
              :placeholder="reportForm.record_type === 'transfer_in' ? '转入金额' : '转出金额'"
            />
          </el-form-item>
        </template>

        <el-form-item label="备注">
          <el-input
            v-model="reportForm.notes"
            type="textarea"
            :rows="2"
            placeholder="可选备注"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showReportDialog = false">取消</el-button>
        <el-button type="primary" :loading="reportLoading" @click="submitReport">
          提交
        </el-button>
      </template>
    </el-dialog>

    <!-- 编辑记录对话框（超级管理员） -->
    <el-dialog v-model="showEditDialog" title="编辑资产记录" :width="isMobile ? '92%' : '480px'" :top="isMobile ? '10px' : '15vh'" class="asset-dialog">
      <el-form :model="editForm" :label-position="isMobile ? 'top' : 'right'" label-width="80px">
        <el-form-item label="平台">
          <el-input :value="editingRecord?.platform_name" disabled />
        </el-form-item>
        <el-form-item label="类型">
          <el-tag v-if="editingRecord" :type="recordTypeTag(editingRecord.record_type)" size="small">
            {{ recordTypeLabel(editingRecord.record_type) }}
          </el-tag>
        </el-form-item>

        <template v-if="editingRecord?.record_type === 'balance'">
          <el-form-item label="余额">
            <el-input-number
              v-model="editForm.reported_balance"
              :min="0"
              :precision="2"
              style="width:100%"
            />
          </el-form-item>
          <el-form-item label="收益">
            <el-input-number
              v-model="editForm.reported_earnings"
              :min="-99999999"
              :precision="2"
              style="width:100%"
            />
          </el-form-item>
        </template>
        <template v-else-if="editingRecord?.record_type === 'earnings'">
          <el-form-item label="本次收益">
            <el-input-number
              v-model="editForm.amount"
              :min="-99999999"
              :precision="2"
              style="width:100%"
            />
          </el-form-item>
        </template>
        <template v-else-if="editingRecord?.record_type === 'balance_only'">
          <el-form-item label="余额">
            <el-input-number
              v-model="editForm.reported_balance"
              :min="0"
              :precision="2"
              style="width:100%"
            />
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="金额">
            <el-input-number
              v-model="editForm.amount"
              :min="0.01"
              :precision="2"
              style="width:100%"
            />
          </el-form-item>
        </template>

        <el-form-item label="备注">
          <el-input
            v-model="editForm.notes"
            type="textarea"
            :rows="2"
            placeholder="可选备注"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="submitEdit">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.assets-page {
  padding: 20px;
  max-width: 900px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 22px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.summary-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}

.summary-card {
  text-align: center;
}

.card-label-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.card-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}

.card-value {
  font-size: 28px;
  font-weight: 700;
}

.total-balance .card-value {
  color: #409eff;
}

.earnings-value {
  color: #F56C6C;
}

.earnings-value.negative,
.platform-earnings.negative,
.record-earnings.negative {
  color: #67C23A;
}

.platform-card {
  margin-bottom: 12px;
}

.platform-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.platform-name {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 4px;
}

.platform-balance {
  font-size: 14px;
  color: #606266;
}

.platform-earnings {
  font-size: 14px;
  color: #F56C6C;
  margin-top: 2px;
}

.annualized-return {
  font-size: 12px;
  margin-left: 6px;
  font-weight: 500;
}

.annualized-return.positive {
  color: #F56C6C;
}

.annualized-return.negative {
  color: #67C23A;
}

.platform-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.record-list {
  margin-top: 16px;
  border-top: 1px solid #ebeef5;
  padding-top: 12px;
}

.no-records {
  text-align: center;
  color: #c0c4cc;
  padding: 20px;
  font-size: 14px;
}

.record-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f2f2f2;
}

.record-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.record-note {
  font-size: 13px;
  color: #909399;
}

.record-right {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
}

.record-balance,
.record-earnings {
  color: #F56C6C;
}

.record-transfer {
  font-weight: 500;
}

.transfer-in {
  color: #67c23a;
}

.transfer-out {
  color: #f56c6c;
}

.record-time {
  color: #c0c4cc;
  font-size: 12px;
}

.empty-tip {
  padding: 40px;
}

.edit-btn {
  margin-left: 4px;
  flex-shrink: 0;
}

.trend-card {
  margin-bottom: 20px;
}

.trend-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  color: #303133;
}

.trend-chart {
  margin: 0 -12px;
}

.trend-empty {
  padding: 20px 0;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
}

/* 移动端弹窗适配 */
@media (max-width: 768px) {
  .asset-dialog .el-dialog__body {
    padding: 16px 12px;
  }
  .report-type-group {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  .report-type-group .el-radio-button {
    margin-bottom: 4px;
  }
  .report-type-group .el-radio-button__inner {
    font-size: 12px;
    padding: 6px 10px;
  }
}

/* 赵平飞年度统计表 */
.zpf-summary-header {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
  padding: 8px 0 4px;
}
.zpf-table {
  width: 100%;
}
.zpf-table .transfer-in {
  color: #67c23a;
  font-weight: 500;
}
.zpf-table .transfer-out {
  color: #f56c6c;
  font-weight: 500;
}
.zpf-total {
  margin-top: 12px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 13px;
  color: #606266;
}
.zpf-total strong {
  color: #303133;
  font-size: 14px;
}
.zpf-records-divider {
  margin: 16px 0 12px;
  padding: 4px 0;
  font-size: 13px;
  font-weight: 500;
  color: #909399;
  border-bottom: 1px solid #ebeef5;
}
</style>
