<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Wallet, Edit, TrendCharts, Download, Coin, PieChart as PieIcon, Loading, HomeFilled } from '@element-plus/icons-vue'
import { assetApi } from '@/api/assets'
import { useAmountVisibility } from '@/composables/useAmountVisibility'
import { useAuthStore } from '@/stores/auth'
import type { AssetSummary, AssetPlatformDetail, AssetRecord, AssetTrend, AssetItem, PortfolioSummary, PlatformGroup, PlatformItemsResponse, FixedAsset } from '@/types'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'

use([
  CanvasRenderer,
  LineChart,
  PieChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

const authStore = useAuthStore()
const { hideAmounts, formatAmount } = useAmountVisibility()

// ==================== 持仓明细相关 ====================

const items = ref<AssetItem[]>([])
const portfolioSummary = ref<PortfolioSummary | null>(null)
const itemsLoading = ref(false)

// 平台持仓数据（含比例）
const platformItemsData = ref<PlatformGroup[]>([])
const platformItemsLoading = ref(false)
const expandedPlatformItemIds = ref<Set<number>>(new Set())

const togglePlatformItems = (platformId: number) => {
  const s = new Set(expandedPlatformItemIds.value)
  if (s.has(platformId)) { s.delete(platformId) } else { s.add(platformId) }
  expandedPlatformItemIds.value = s
}

const loadItems = async () => {
  itemsLoading.value = true
  try {
    const [itemList, summary] = await Promise.all([
      assetApi.listItems(),
      assetApi.getPortfolioSummary()
    ])
    items.value = itemList
    portfolioSummary.value = summary
  } catch (error) {
    console.error('加载持仓数据失败', error)
  } finally {
    itemsLoading.value = false
  }
}

const loadPlatformItems = async () => {
  platformItemsLoading.value = true
  try {
    const resp = await assetApi.getPlatformItems()
    platformItemsData.value = resp.platforms
  } catch (error) {
    console.error('加载平台持仓数据失败', error)
  } finally {
    platformItemsLoading.value = false
  }
}

// 固定资产
const fixedAssets = ref<FixedAsset[]>([])
const fixedAssetsLoading = ref(false)
const fixedAssetsTotal = computed(() => {
  return fixedAssets.value.reduce((s, a) => s + Number(a.estimated_value), 0)
})

// 2026年租金概算
const currentRent = 38220
const estimatedRent = 36000
const rentalIncome = computed(() => [
  { period: '1月', rent: estimatedRent },
  { period: '2月', rent: estimatedRent },
  { period: '3月', rent: estimatedRent },
  { period: '4月', rent: currentRent },
  { period: '5月', rent: currentRent },
  { period: '6月', rent: currentRent },
])
const rentalYtd = computed(() => rentalIncome.value.reduce((s, m) => s + m.rent, 0))
const rentalProjected = computed(() => currentRent * 6)
const rentalFullYear = computed(() => rentalYtd.value + rentalProjected.value)

const loadFixedAssets = async () => {
  fixedAssetsLoading.value = true
  try {
    fixedAssets.value = await assetApi.listFixedAssets()
  } catch (error) {
    console.error('加载固定资产失败', error)
  } finally {
    fixedAssetsLoading.value = false
  }
}

const loading = ref(false)
const summary = ref<AssetSummary | null>(null)

// 图表相关
const activeChartTab = ref('trend')
const expandedTrendCharts = ref('balance')
const expandedAssetCharts = ref('distribution')

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

// 资产分布饼图
const distributionOption = computed(() => {
  if (!summary.value || summary.value.platforms.length === 0) return null
  const data = summary.value.platforms
    .filter(p => p.current_balance > 0)
    .map(p => ({
      name: p.name,
      value: Number(p.current_balance)
    }))
    .sort((a, b) => b.value - a.value)
  if (data.length === 0) return null
  return {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: ¥{c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 20,
      textStyle: { fontSize: 12 }
    },
    series: [{
      name: '资产分布',
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['35%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: {
        borderRadius: 10,
        borderColor: '#fff',
        borderWidth: 2
      },
      label: {
        show: true,
        formatter: '{b}: {d}%',
        fontSize: 12
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 14,
          fontWeight: 'bold'
        }
      },
      data: data
    }]
  }
})

// 平台收益对比柱状图
const platformCompareOption = computed(() => {
  if (!summary.value || summary.value.platforms.length === 0) return null
  const platforms = summary.value.platforms
    .map(p => ({
      name: p.name,
      earnings: Number(p.total_earnings),
      returnRate: p.annualized_return !== null ? Number(p.annualized_return) : null
    }))
    .filter(p => p.earnings !== 0)
  if (platforms.length === 0) return null
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any[]) => {
        const platform = params[0].name
        const p = platforms.find(x => x.name === platform)
        let html = `<strong>${platform}</strong><br/>`
        for (const item of params) {
          if (item.seriesName === '当年收益') {
            html += `${item.marker} ${item.seriesName}: ¥${item.value.toLocaleString()}<br/>`
          } else if (item.seriesName === '年化收益率' && p?.returnRate !== null) {
            html += `${item.marker} ${item.seriesName}: ${item.value}%<br/>`
          }
        }
        return html
      }
    },
    legend: { data: ['当年收益', '年化收益率'], top: 0, right: 20, textStyle: { fontSize: 12 } },
    grid: { left: 80, right: 60, top: 30, bottom: 40 },
    xAxis: { type: 'value', axisLabel: { formatter: (v: number) => v >= 10000 ? (v / 10000).toFixed(0) + '万' : v.toFixed(0) } },
    yAxis: { type: 'category', data: platforms.map(p => p.name), inverse: false },
    series: [
      {
        name: '当年收益',
        type: 'bar',
        data: platforms.map(p => p.earnings),
        itemStyle: {
          color: (params: any) => {
            const val = params.value
            return val >= 0 ? '#67C23A' : '#F56C6C'
          }
        },
        label: {
          show: true,
          position: 'right',
          formatter: (params: any) => {
            const val = params.value
            return val >= 0 ? `+${(val / 10000).toFixed(2)}万` : `${(val / 10000).toFixed(2)}万`
          }
        }
      },
      {
        name: '年化收益率',
        type: 'bar',
        data: platforms.map(p => p.returnRate),
        itemStyle: {
          color: (params: any) => {
            const val = params.value
            if (val === null) return '#909399'
            return val >= 0 ? '#409EFF' : '#F56C6C'
          }
        },
        label: {
          show: true,
          position: 'right',
          formatter: (params: any) => {
            const val = params.value
            if (val === null) return '-'
            return val >= 0 ? `+${val}%` : `${val}%`
          }
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
  record_type: 'balance' as 'balance' | 'earnings' | 'balance_only' | 'transfer_in' | 'transfer_out',
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
    record_type: 'balance',
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
    } else if (editingRecord.value.record_type === 'transfer_in' || editingRecord.value.record_type === 'transfer_out') {
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

// 导出资产数据
const exportAssets = async () => {
  try {
    ElMessage.info('正在导出，请稍候...')

    // 使用和资产API相同的认证方法
    const token = (() => {
      try {
        const encrypted = localStorage.getItem('access_token')
        if (!encrypted) return null
        const decoded = atob(encrypted)
        const key = import.meta.env.VITE_ENCRYPTION_KEY || 'dev-only-rent-system-encryption-key-2026'
        let result = ''
        for (let i = 0; i < decoded.length; i++) {
          result += String.fromCharCode(decoded.charCodeAt(i) ^ key.charCodeAt(i % key.length))
        }
        const parts = result.split('|')
        return parts.length === 4 ? parts[3] : null
      } catch {
        return null
      }
    })()

    if (!token) {
      ElMessage.error('请先登录')
      return
    }

    const response = await fetch('/api/v1/assets/export', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })

    if (!response.ok) {
      throw new Error('导出失败')
    }

    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url

    // 从响应头获取文件名
    const contentDisposition = response.headers.get('Content-Disposition')
    let filename = '资产记录.xlsx'
    if (contentDisposition) {
      const match = contentDisposition.match(/filename\*?=['"]?(?:UTF-\d['"]*)?([^;'"()\s]*)['"]?;?/)
      if (match) {
        filename = decodeURIComponent(match[1])
      }
    }

    a.download = filename
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)

    ElMessage.success('导出成功')
  } catch (error: any) {
    console.error(error)
    ElMessage.error('导出失败: ' + (error.message || '未知错误'))
  }
}

// 移动端响应式检测

// 持仓组合
const portfolioOption = computed(() => {
  if (!portfolioSummary.value || portfolioSummary.value.total_amount === 0) return null
  const s = portfolioSummary.value
  const data = [
    { name: '股基', value: Number(s.stock_amount), itemStyle: { color: '#F56C6C' } },
    { name: '债券', value: Number(s.bond_amount), itemStyle: { color: '#409EFF' } },
    { name: '现金', value: Number(s.cash_amount), itemStyle: { color: '#67C23A' } },
    { name: '商品', value: Number(s.commodity_amount), itemStyle: { color: '#E6A23C' } },
    { name: '固收', value: Number(s.fixed_income_amount), itemStyle: { color: '#9B59B6' } },
    { name: '其他', value: Number(s.other_amount), itemStyle: { color: '#909399' } },
  ].filter(d => d.value > 0)
  if (data.length === 0) return null
  return {
    tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
    series: [{ type: 'pie', radius: ['45%', '70%'], center: ['50%', '50%'], avoidLabelOverlap: true,
      itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: (p: any) => `${p.percent.toFixed(1)}%`, fontSize: 12 }, data }]
  }
})

// 颜色和标签映射
const typeColors: Record<string, string> = {
  stock_pct: '#F56C6C', bond_pct: '#409EFF', cash_pct: '#67C23A',
  commodity_pct: '#E6A23C', fixed_income_pct: '#9B59B6', other_pct: '#909399'
}
const typeLabels: Record<string, string> = {
  stock_pct: '股基', bond_pct: '债券', cash_pct: '现金',
  commodity_pct: '商品', fixed_income_pct: '固收', other_pct: '其他'
}

// 添加持仓
const showAddItemDialog = ref(false)
const addItemLoading = ref(false)
const addItemForm = ref({ name: '', code: '', amount: 0, stock_pct: 0, bond_pct: 0, cash_pct: 0, commodity_pct: 0, fixed_income_pct: 0, other_pct: 0, platform_id: null as number | null })
const platforms = ref<{ id: number; name: string }[]>([])

const openAddItem = async () => {
  addItemForm.value = { name: '', code: '', amount: 0, stock_pct: 0, bond_pct: 0, cash_pct: 0, commodity_pct: 0, fixed_income_pct: 0, other_pct: 0, platform_id: null }
  try { platforms.value = await assetApi.listPlatforms() } catch { platforms.value = [] }
  showAddItemDialog.value = true
}

const totalPct = computed(() => {
  const f = addItemForm.value
  return Number(f.stock_pct) + Number(f.bond_pct) + Number(f.cash_pct) + Number(f.commodity_pct) + Number(f.fixed_income_pct) + Number(f.other_pct)
})

const submitAddItem = async () => {
  const f = addItemForm.value
  if (!f.name) { ElMessage.warning('请输入资产名称'); return }
  if (Number(f.amount) <= 0) { ElMessage.warning('请输入持仓金额'); return }
  if (Number(totalPct.value) !== 100) { ElMessage.warning(`各类型占比之和必须为100，当前${totalPct.value}`); return }
  addItemLoading.value = true
  try {
    await assetApi.createItem({
      name: f.name, code: f.code || null, amount: Number(f.amount),
      stock_pct: Number(f.stock_pct), bond_pct: Number(f.bond_pct), cash_pct: Number(f.cash_pct),
      commodity_pct: Number(f.commodity_pct), fixed_income_pct: Number(f.fixed_income_pct), other_pct: Number(f.other_pct),
      platform_id: f.platform_id
    })
    ElMessage.success('持仓添加成功')
    showAddItemDialog.value = false
    await loadItems()
    await loadPlatformItems()
  } catch (error: any) { ElMessage.error(error.response?.data?.detail || '添加失败') }
  finally { addItemLoading.value = false }
}

const deleteItem = async (id: number, name: string) => {
  try {
    await ElMessageBox.confirm(`确定删除「${name}」？`, '确认删除')
    await assetApi.deleteItem(id)
    ElMessage.success('已删除')
    await loadItems()
    await loadPlatformItems()
  } catch { /* cancelled */ }
}

// 编辑持仓
const showEditItemDialog = ref(false)
const editingItem = ref<AssetItem | null>(null)
const editItemLoading = ref(false)
const editItemForm = ref({ name: '', code: '', amount: 0, stock_pct: 0, bond_pct: 0, cash_pct: 0, commodity_pct: 0, fixed_income_pct: 0, other_pct: 0, platform_id: null as number | null })

const openEditItem = async (item: AssetItem) => {
  editingItem.value = item
  editItemForm.value = {
    name: item.name, code: item.code || '', amount: item.amount,
    stock_pct: item.stock_pct, bond_pct: item.bond_pct, cash_pct: item.cash_pct,
    commodity_pct: item.commodity_pct, fixed_income_pct: item.fixed_income_pct, other_pct: item.other_pct,
    platform_id: item.platform_id
  }
  try { platforms.value = await assetApi.listPlatforms() } catch { platforms.value = [] }
  showEditItemDialog.value = true
}

const editItemTotalPct = computed(() => {
  const f = editItemForm.value
  return Number(f.stock_pct) + Number(f.bond_pct) + Number(f.cash_pct) + Number(f.commodity_pct) + Number(f.fixed_income_pct) + Number(f.other_pct)
})

const submitEditItem = async () => {
  if (!editingItem.value) return
  const f = editItemForm.value
  if (!f.name) { ElMessage.warning('请输入资产名称'); return }
  if (Number(f.amount) <= 0) { ElMessage.warning('请输入持仓金额'); return }
  if (Number(editItemTotalPct.value) !== 100) { ElMessage.warning(`各类型占比之和必须为100，当前${editItemTotalPct.value}`); return }
  editItemLoading.value = true
  try {
    await assetApi.updateItem(editingItem.value.id, {
      name: f.name, code: f.code || null, amount: Number(f.amount),
      stock_pct: Number(f.stock_pct), bond_pct: Number(f.bond_pct), cash_pct: Number(f.cash_pct),
      commodity_pct: Number(f.commodity_pct), fixed_income_pct: Number(f.fixed_income_pct), other_pct: Number(f.other_pct),
      platform_id: f.platform_id
    })
    ElMessage.success('持仓编辑成功')
    showEditItemDialog.value = false
    await loadItems()
    await loadPlatformItems()
  } catch (error: any) { ElMessage.error(error.response?.data?.detail || '编辑失败') }
  finally { editItemLoading.value = false }
}

const isMobile = ref(window.innerWidth < 768)
const checkMobile = () => { isMobile.value = window.innerWidth < 768 }
window.addEventListener('resize', checkMobile)

onMounted(() => {
  loadSummary()
  loadTrend()
  loadItems()
  loadPlatformItems()
  loadFixedAssets()
  window.addEventListener('resize', checkMobile)
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
        <el-button type="default" :icon="Download" @click="exportAssets">导出Excel</el-button>
        <el-button type="default" @click="loadSummary">刷新</el-button>
      </div>
    </div>

    <!-- 总资产概览 -->
    <div class="summary-cards">
      <el-card class="summary-card total-card">
        <div class="card-label">💰 总资产</div>
        <div class="card-value total-value">{{ summary && fixedAssets.length ? formatAmount(Number(summary.total_balance) + fixedAssetsTotal) : '-' }}</div>
        <div class="total-earnings-row">
          <span :class="displayEarnings < 0 ? 'negative' : 'positive'">权益 {{ summary ? formatAmount(displayEarnings) : '-' }}</span>
          <span class="total-earnings-rent positive">+ 房租 {{ formatAmount(rentalYtd) }}</span>
          <span class="total-earnings-divider">=</span>
          <span :class="[Number(displayEarnings || 0) + rentalYtd >= 0 ? 'positive' : 'negative', 'total-earnings-sum']">
            {{ summary ? formatAmount(Number(displayEarnings || 0) + rentalYtd) : '-' }}
          </span>
        </div>
      </el-card>
      <el-card class="summary-card equity-card">
        <div class="card-label-row">
          <div class="card-label">📈 权益类</div>
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
        <div class="card-value">{{ summary ? formatAmount(summary.total_balance) : '-' }}</div>
        <div :class="['card-sub', displayEarnings < 0 ? 'negative' : 'positive']">收益 {{ summary ? formatAmount(displayEarnings) : '-' }}</div>
      </el-card>
      <el-card class="summary-card fixed-card">
        <div class="card-label">🏠 固定资产</div>
        <div class="card-value">{{ fixedAssets.length ? formatAmount(fixedAssetsTotal) : '-' }}</div>
        <div class="card-sub positive">租金收入 {{ formatAmount(rentalYtd) }} <span class="card-sub-hint">(全年预估 {{ formatAmount(rentalFullYear) }})</span></div>
      </el-card>
    </div>

    <!-- 持仓组合 -->
    <el-card v-loading="itemsLoading" class="portfolio-card">
      <div class="portfolio-header">
        <h3><el-icon :size="20"><PieIcon /></el-icon> 持仓组合</h3>
        <el-button type="primary" size="small" :icon="Plus" @click="openAddItem">添加持仓</el-button>
      </div>

      <template v-if="portfolioSummary && portfolioSummary.total_amount > 0">
        <div class="portfolio-summary">
          <div class="portfolio-total">持仓总金额：<strong>{{ formatAmount(portfolioSummary.total_amount) }}</strong></div>
          <div class="portfolio-pct-row">
            <span v-for="(pct, key) in { stock_pct: '股基', bond_pct: '债券', cash_pct: '现金', commodity_pct: '商品', fixed_income_pct: '固收', other_pct: '其他' }" :key="key"
              class="portfolio-pct-item" :style="{ color: (typeColors as any)[key] }">
              {{ pct }} <strong>{{ portfolioSummary ? formatAmount((portfolioSummary as any)[key.replace('_pct', '_amount')]) : 0 }}</strong>
              <span class="pct-badge" :style="{ background: (typeColors as any)[key] }">{{ portfolioSummary ? Number((portfolioSummary as any)[key]).toFixed(1) + '%' : '0%' }}</span>
            </span>
          </div>
        </div>

        <div class="portfolio-content">
          <div v-if="portfolioOption" class="portfolio-chart">
            <VChart :option="portfolioOption" autoresize style="width:100%;height:260px" />
          </div>
          <div class="portfolio-items">
            <div v-for="item in items" :key="item.id" class="portfolio-item">
              <div class="item-header">
                <span class="item-name">{{ item.name }}</span>
                <span v-if="item.code" class="item-code">#{{ item.code }}</span>
                <span v-for="(pct, key) in { stock_pct: item.stock_pct, bond_pct: item.bond_pct, cash_pct: item.cash_pct, commodity_pct: item.commodity_pct, fixed_income_pct: item.fixed_income_pct, other_pct: item.other_pct }" :key="key">
                  <el-tag v-if="Number(pct) > 0" size="small" :color="typeColors[key]" effect="dark" style="color:#fff;border:0">
                    {{ typeLabels[key] }} {{ Number(pct).toFixed(0) }}%
                  </el-tag>
                </span>
                <el-tag v-if="item.platform_name" size="small" type="info">{{ item.platform_name }}</el-tag>
                <el-button text size="small" type="primary" @click="openEditItem(item)">编辑</el-button>
                <el-button text size="small" type="danger" @click="deleteItem(item.id, item.name)">删除</el-button>
              </div>
              <div class="item-amount">{{ formatAmount(item.amount) }}</div>
            </div>
          </div>
        </div>
      </template>
      <el-empty v-else description="暂无持仓数据，点击「添加持仓」开始录入" :image-size="80" />
    </el-card>
    <!-- 固定资产 -->
    <el-card v-loading="fixedAssetsLoading" class="fixed-assets-card">
      <div class="portfolio-header">
        <h3><el-icon :size="20"><HomeFilled /></el-icon> 固定资产</h3>
        <span class="fixed-assets-total">估值总计 <strong>{{ formatAmount(fixedAssetsTotal) }}</strong></span>
      </div>
      <template v-if="fixedAssets.length > 0">
        <div class="fixed-assets-list">
          <div v-for="asset in fixedAssets" :key="asset.id" class="fixed-asset-row">
            <div class="fixed-asset-info">
              <span class="fixed-asset-name">{{ asset.name }}</span>
              <span class="fixed-asset-role">{{ asset.role }}</span>
            </div>
            <div class="fixed-asset-value">
              <span class="fixed-asset-estimate">{{ formatAmount(asset.estimated_value) }}</span>
              <span v-if="asset.monthly_rent && asset.monthly_rent > 0" class="fixed-asset-rent">月租金 {{ formatAmount(asset.monthly_rent) }}</span>
            </div>
          </div>
        </div>
        <!-- 2026年租金概算 -->
        <div class="rental-income-section">
          <div class="rental-income-title"><el-icon :size="16"><Coin /></el-icon> 2026年租金收入概算</div>
          <div class="rental-income-summary">
            <span>1-3月(评估): <strong>{{ formatAmount(estimatedRent * 3) }}</strong></span>
            <span>4-6月(实际): <strong>{{ formatAmount(currentRent * 3) }}</strong></span>
            <span>已收合计: <strong>{{ formatAmount(rentalYtd) }}</strong></span>
          </div>
          <div class="rental-income-summary" style="margin-top:4px">
            <span>7-12月预估: <strong>{{ formatAmount(rentalProjected) }}</strong></span>
            <span>全年预估: <strong>{{ formatAmount(rentalFullYear) }}</strong></span>
          </div>
          <div class="rental-income-note">1-3月按评估¥36,000/月，4月起按实际¥38,220/月</div>
        </div>
        <!-- 租金来源说明 -->
        <div class="fixed-assets-note">
          <div class="note-item"><span class="note-dot" style="background:#409EFF" /><strong>新湖果岭</strong> 月租金 ¥5,750 = 2-2501系列5间+车位</div>
          <div class="note-item"><span class="note-dot" style="background:#E6A23C" /><strong>4套无证房</strong> 月租金 ¥32,470 = 其他23间房的租金合计</div>
          <div class="note-item note-valuation"><span class="note-dot" style="background:#67C23A" /><strong>无证房估值说明</strong>：年租金¥389,640 ÷ 5% ≈ ¥779万，保守取整 <strong>¥700万</strong></div>
        </div>
      </template>
      <el-empty v-else description="暂无固定资产数据" :image-size="60" />
    </el-card>

    <!-- 图表分析 -->
    <el-card class="trend-card">
      <el-tabs v-model="activeChartTab">
        <!-- 趋势分析 -->
        <el-tab-pane label="趋势分析" name="trend">
          <el-collapse v-model="expandedTrendCharts" accordion>
            <!-- 总资产趋势图 -->
            <el-collapse-item title="总资产趋势" name="balance">
              <div v-if="balanceTrendOption" class="trend-chart">
                <VChart :option="balanceTrendOption" autoresize style="width:100%;height:320px" />
              </div>
              <div v-else class="trend-empty">
                <el-empty description="暂无趋势数据，上报余额后自动生成" :image-size="80" />
              </div>
            </el-collapse-item>
            <!-- 2026年趋势图 -->
            <el-collapse-item title="2026年趋势" name="earnings">
              <div v-if="earningsTrendOption" class="trend-chart">
                <VChart :option="earningsTrendOption" autoresize style="width:100%;height:260px" />
              </div>
              <div v-else class="trend-empty">
                <el-empty description="暂无当年收益数据" :image-size="80" />
              </div>
            </el-collapse-item>
          </el-collapse>
        </el-tab-pane>

        <!-- 资产分析 -->
        <el-tab-pane label="资产分析" name="assets">
          <el-collapse v-model="expandedAssetCharts" accordion>
            <!-- 资产分布饼图 -->
            <el-collapse-item title="资产分布" name="distribution">
              <div v-if="distributionOption" class="trend-chart">
                <VChart :option="distributionOption" autoresize style="width:100%;height:320px" />
              </div>
              <div v-else class="trend-empty">
                <el-empty description="暂无资产数据" :image-size="80" />
              </div>
            </el-collapse-item>
            <!-- 平台收益对比柱状图 -->
            <el-collapse-item title="平台收益对比" name="platform">
              <div v-if="platformCompareOption" class="trend-chart">
                <VChart :option="platformCompareOption" autoresize style="width:100%;height:400px" />
              </div>
              <div v-else class="trend-empty">
                <el-empty description="暂无收益数据" :image-size="80" />
              </div>
            </el-collapse-item>
          </el-collapse>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 各平台概览 -->
    <el-card class="platform-table-card">
      <div class="portfolio-header">
        <h3><el-icon :size="20"><Coin /></el-icon> 各平台概览</h3>
        <div class="header-actions">
          <el-button size="small" @click="loadSummary">刷新</el-button>
        </div>
      </div>
      <el-table :data="summary?.platforms || []" stripe size="small" style="width:100%">
        <el-table-column label="平台" min-width="100">
          <template #default="{ row }">
            <span class="platform-name-cell">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="余额" min-width="110" align="right">
          <template #default="{ row }">
            <strong>{{ formatAmount(row.current_balance) }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="当年收益" min-width="130" align="right">
          <template #default="{ row }">
            <span :class="row.total_earnings >= 0 ? 'positive' : 'negative'">{{ formatAmount(row.total_earnings) }}</span>
            <span v-if="row.annualized_return !== null" :class="['annualized-tag', row.annualized_return >= 0 ? 'positive' : 'negative']">
              {{ row.annualized_return >= 0 ? '+' : '' }}{{ row.annualized_return }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="120">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="openReport(row.name)">上报</el-button>
            <el-button size="small" @click="toggleRecords(row.id)">
              {{ expandedPlatformIds.has(row.id) ? '收起' : '记录' }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column type="expand">
          <template #default="{ row }">
            <div v-if="expandedPlatformIds.has(row.id)" class="platform-detail">
              <!-- 平台持仓明细 -->
              <template v-for="pg in platformItemsData.filter(p => p.platform_id === row.id)" :key="pg.platform_id">
                <div v-if="pg.items.length > 0" class="platform-detail-items">
                  <div class="platform-detail-label">📊 持仓明细</div>
                  <div v-for="item in pg.items" :key="item.id" class="platform-detail-item">
                    <span class="pdi-name">{{ item.name }}</span>
                    <span v-if="item.code" class="pdi-code">#{{ item.code }}</span>
                    <span class="pdi-types">
                      <span v-for="(label, key) in typeLabels" :key="key" v-if="item[key] > 0" class="pdi-type">{{ label }}</span>
                    </span>
                    <span class="pdi-amount">{{ formatAmount(item.amount) }}</span>
                    <span class="pdi-pct">{{ item.pct_of_platform.toFixed(1) }}%</span>
                  </div>
                </div>
              </template>
              <!-- 变动记录 -->
              <div v-if="row.records.length === 0" class="no-records">暂无变动记录</div>
              <div v-for="record in row.records" :key="record.id" class="platform-record-row">
                <el-tag :type="recordTypeTag(record.record_type)" size="small">{{ recordTypeLabel(record.record_type) }}</el-tag>
                <span v-if="record.notes" class="record-note">{{ record.notes }}</span>
                <span v-if="record.record_type === 'balance'">余额 {{ formatAmount(record.reported_balance || 0) }} / 收益 {{ formatAmount(record.reported_earnings || 0) }}</span>
                <span v-else-if="record.record_type === 'balance_only'">余额 {{ formatAmount(record.reported_balance || 0) }}</span>
                <span v-else :class="record.record_type === 'transfer_in' ? 'positive' : 'negative'">{{ formatAmount(record.amount || 0) }}</span>
                <span class="record-time">{{ formatDate(record.created_at) }}</span>
                <el-button v-if="authStore.isSuperAdmin" text size="small" type="primary" :icon="Edit" @click="openEdit(record)" class="edit-btn" />
              </div>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>    <!-- 上报对话框 -->
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

    
    <!-- 添加持仓对话框 -->
    <el-dialog v-model="showAddItemDialog" title="添加持仓" :width="isMobile ? '92%' : '520px'" :top="isMobile ? '10px' : '15vh'">
      <el-form :model="addItemForm" :label-position="isMobile ? 'top' : 'right'" label-width="100px">
        <el-form-item label="资产名称"><el-input v-model="addItemForm.name" placeholder="如 易方达蓝筹精选、沪深300ETF" /></el-form-item>
        <el-form-item label="编号"><el-input v-model="addItemForm.code" placeholder="如 001、002（选填）" style="width:100%" /></el-form-item>
        <el-form-item label="持仓金额"><el-input-number v-model="addItemForm.amount" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="所属平台">
          <el-select v-model="addItemForm.platform_id" placeholder="选填" clearable style="width:100%">
            <el-option v-for="p in platforms" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-divider>资产类型占比（总和：{{ totalPct }}%）</el-divider>
        <div class="pct-inputs">
          <div v-for="(label, key) in typeLabels" :key="key" class="pct-field">
            <div class="pct-label" :style="{ color: (typeColors as any)[key] }">{{ label }}</div>
            <el-input-number v-model="(addItemForm as any)[key]" :min="0" :max="100" :step="5" :precision="0" size="small" controls-position="right" style="width:140px" />
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="showAddItemDialog = false">取消</el-button>
        <el-button type="primary" :loading="addItemLoading" @click="submitAddItem">添加</el-button>
      </template>
    </el-dialog>

    <!-- 编辑持仓对话框 -->
    <el-dialog v-model="showEditItemDialog" title="编辑持仓" :width="isMobile ? '92%' : '520px'" :top="isMobile ? '10px' : '15vh'">
      <el-form :model="editItemForm" :label-position="isMobile ? 'top' : 'right'" label-width="100px">
        <el-form-item label="资产名称"><el-input v-model="editItemForm.name" placeholder="如 易方达蓝筹精选、沪深300ETF" /></el-form-item>
        <el-form-item label="编号"><el-input v-model="editItemForm.code" placeholder="如 001、002（选填）" style="width:100%" /></el-form-item>
        <el-form-item label="持仓金额"><el-input-number v-model="editItemForm.amount" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="所属平台">
          <el-select v-model="editItemForm.platform_id" placeholder="选填" clearable style="width:100%">
            <el-option v-for="p in platforms" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-divider>资产类型占比（总和：{{ editItemTotalPct }}%）</el-divider>
        <div class="pct-inputs">
          <div v-for="(label, key) in typeLabels" :key="key" class="pct-field">
            <div class="pct-label" :style="{ color: (typeColors as any)[key] }">{{ label }}</div>
            <el-input-number v-model="(editItemForm as any)[key]" :min="0" :max="100" :step="5" :precision="0" size="small" controls-position="right" style="width:140px" />
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="showEditItemDialog = false">取消</el-button>
        <el-button type="primary" :loading="editItemLoading" @click="submitEditItem">保存</el-button>
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

/* 总资产三列 */
.summary-cards {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}
.summary-card { text-align: center; }
.card-label { font-size: 14px; color: #909399; margin-bottom: 8px; }
.card-label-row { display: flex; align-items: center; justify-content: center; gap: 8px; }
.card-value { font-size: 28px; font-weight: 700; }
.card-sub { font-size: 13px; margin-top: 4px; }
.card-sub.positive { color: #67C23A; }
.card-sub.negative { color: #F56C6C; }
.card-sub-hint { font-size: 11px; color: #909399; }
.total-card .card-value { color: #303133; font-size: 32px; }
.equity-card .card-value { color: #409eff; }
.fixed-card .card-value { color: #E6A23C; }
.total-earnings-row { margin-top: 8px; font-size: 13px; display: flex; align-items: center; justify-content: center; gap: 6px; flex-wrap: wrap; }
.total-earnings-row .positive { color: #67C23A; }
.total-earnings-row .negative { color: #F56C6C; }
.total-earnings-rent { font-weight: 500; }
.total-earnings-divider { color: #c0c4cc; font-weight: 700; }
.total-earnings-sum { font-weight: 700; font-size: 15px; }

/* 固定资产 */
.fixed-assets-card { margin-bottom: 16px; }
.fixed-assets-list { display: flex; flex-direction: column; }
.fixed-asset-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #f0f0f0; }
.fixed-asset-row:last-child { border-bottom: none; }
.fixed-asset-info { display: flex; flex-direction: column; gap: 2px; }
.fixed-asset-name { font-size: 14px; font-weight: 600; color: #303133; }
.fixed-asset-role { font-size: 12px; color: #909399; }
.fixed-asset-value { display: flex; align-items: center; gap: 8px; }
.fixed-asset-estimate { font-size: 14px; font-weight: 600; color: #409EFF; }
.fixed-asset-rent { font-size: 12px; color: #67C23A; }
.fixed-assets-total { font-size: 13px; color: #606266; }
.fixed-assets-total strong { color: #409EFF; font-size: 15px; }

/* 租金概算 */
.rental-income-section { margin-top: 14px; padding: 12px; background: #f8f9fb; border-radius: 8px; border: 1px solid #ebeef5; }
.rental-income-title { font-size: 13px; font-weight: 600; color: #303133; margin-bottom: 10px; display: flex; align-items: center; gap: 4px; }
.rental-income-summary { display: flex; gap: 16px; font-size: 12px; color: #606266; flex-wrap: wrap; }
.rental-income-summary strong { color: #303133; font-size: 14px; }
.rental-income-note { margin-top: 6px; font-size: 11px; color: #909399; }

/* 固定资产备注 */
.fixed-assets-note { margin-top: 12px; padding: 10px 12px; background: #fafafa; border-radius: 6px; font-size: 12px; line-height: 1.6; }
.note-item { display: flex; align-items: flex-start; gap: 6px; margin-bottom: 6px; color: #606266; }
.note-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-top: 5px; flex-shrink: 0; }
.note-valuation { color: #67C23A; font-weight: 500; }

/* 平台展开 */
.platform-detail-items { padding: 8px 0; }
.platform-detail-label { font-size: 13px; font-weight: 600; color: #909399; margin-bottom: 6px; }
.platform-detail-item { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 12px; border-bottom: 1px dashed #f0f0f0; }
.platform-detail-item:last-child { border-bottom: none; }
.pdi-name { font-weight: 500; color: #303133; min-width: 160px; }
.pdi-code { color: #909399; font-size: 11px; }
.pdi-types { display: flex; gap: 2px; flex:1; flex-wrap:wrap; }
.pdi-type { color: #909399; font-size: 11px; }
.pdi-amount { color: #606266; min-width: 80px; text-align: right; }
.pdi-pct { color: #409EFF; font-weight: 600; min-width: 50px; text-align: right; }
.platform-record-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 12px; flex-wrap: wrap; }
.platform-record-row .positive { color: #67C23A; }
.platform-record-row .negative { color: #F56C6C; }
.no-records { padding: 12px; text-align: center; color: #c0c4cc; font-size: 13px; }
.platform-name-cell { font-weight: 600; }
.annualized-tag { font-size: 11px; margin-left: 4px; }
.positive { color: #67C23A; }
.negative { color: #F56C6C; }
.pct-inputs { display: flex; flex-direction: column; gap: 12px; }
.pct-field { display: flex; align-items: center; justify-content: space-between; padding: 2px 4px; }
.pct-label { font-size: 13px; font-weight: 500; }

.record-time { color: #c0c4cc; font-size: 11px; margin-left: auto; }
.edit-btn { margin-left: 4px; }


/* 持仓组合 */
.portfolio-card { margin-bottom: 16px; }
.portfolio-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.portfolio-header h3 { margin: 0; display: flex; align-items: center; gap: 6px; }
.portfolio-summary { margin-bottom: 16px; }
.portfolio-total { font-size: 15px; margin-bottom: 8px; }
.portfolio-total strong { color: #409EFF; font-size: 18px; }
.portfolio-pct-row { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 12px; }
.portfolio-pct-item { font-size: 13px; color: #606266; display: flex; align-items: center; gap: 4px; }
.portfolio-pct-item strong { font-weight: 700; font-size: 14px; }
.pct-badge { font-size: 11px; color: #fff; padding: 1px 6px; border-radius: 8px; margin-left: 2px; }
.portfolio-content { display: flex; gap: 20px; }
.portfolio-chart { width: 280px; flex-shrink: 0; }
.portfolio-items { flex: 1; display: flex; flex-direction: column; gap: 12px; }
.portfolio-item { border: 1px solid #f0f0f0; border-radius: 8px; padding: 10px 12px; }
.item-header { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.item-name { font-size: 14px; font-weight: 600; color: #303133; }
.item-code { font-size: 11px; color: #909399; background: #f5f7fa; padding: 1px 5px; border-radius: 3px; }
.item-amount { font-size: 13px; color: #409EFF; font-weight: 600; margin-top: 4px; }
.item-types { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.type-tag { font-size: 11px; font-weight: 500; background: #f0f0f0; padding: 1px 6px; border-radius: 8px; }
.header-actions { display: flex; gap: 8px; }
@media (max-width: 768px) {
  .portfolio-content { flex-direction: column; }
  .portfolio-chart { width: 100%; }
}

</style>
