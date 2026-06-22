<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Wallet, Edit } from '@element-plus/icons-vue'
import { assetApi } from '@/api/assets'
import { useAmountVisibility } from '@/composables/useAmountVisibility'
import { useAuthStore } from '@/stores/auth'
import type { AssetSummary, AssetPlatformDetail, AssetRecord } from '@/types'

const authStore = useAuthStore()
const { hideAmounts, formatAmount } = useAmountVisibility()

const loading = ref(false)
const summary = ref<AssetSummary | null>(null)

// 预设平台列表
const ALL_PLATFORMS = [
  '支付宝', '且慢', '网商银行', '腾讯理财通',
  '雪球', '京东金融', '平安证券',
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
  record_type: 'balance' as 'balance' | 'transfer_in' | 'transfer_out',
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

// 展开/收起记录
const toggleRecords = (platformId: number) => {
  const s = new Set(expandedPlatformIds.value)
  if (s.has(platformId)) {
    s.delete(platformId)
  } else {
    s.add(platformId)
  }
  expandedPlatformIds.value = s
}

const formatDate = (d: string) => {
  const date = new Date(d)
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

const recordTypeLabel = (type: string) => {
  switch (type) {
    case 'balance': return '余额上报'
    case 'transfer_in': return '转入'
    case 'transfer_out': return '转出'
    default: return type
  }
}

const recordTypeTag = (type: string) => {
  switch (type) {
    case 'balance': return 'primary'
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

onMounted(() => {
  loadSummary()
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
        <div class="card-value">¥{{ summary ? formatAmount(summary.total_balance) : '-' }}</div>
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
          ¥{{ summary ? formatAmount(displayEarnings) : '-' }}
        </div>
      </el-card>
    </div>

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
              余额：<strong>¥{{ formatAmount(platform.current_balance) }}</strong>
            </div>
            <div :class="['platform-earnings', platform.total_earnings < 0 ? 'negative' : '']">
              {{ platform.current_year }}年收益：<strong>¥{{ formatAmount(platform.total_earnings) }}</strong>
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
                <span class="record-balance">余额：¥{{ formatAmount(record.reported_balance || 0) }}</span>
                <span :class="['record-earnings', (record.reported_earnings || 0) < 0 ? 'negative' : '']">收益：¥{{ formatAmount(record.reported_earnings || 0) }}</span>
                <span v-if="record.calculated_transfer && record.calculated_transfer !== 0"
                  :class="['record-transfer', record.calculated_transfer > 0 ? 'transfer-in' : 'transfer-out']">
                  {{ record.calculated_transfer > 0 ? '转入' : '转出' }} ¥{{ formatAmount(Math.abs(record.calculated_transfer)) }}
                </span>
              </template>
              <template v-else>
                <span :class="record.record_type === 'transfer_in' ? 'transfer-in' : 'transfer-out'">
                  ¥{{ formatAmount(record.amount || 0) }}
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
        </div>
      </el-card>
    </div>

    <!-- 上报对话框 -->
    <el-dialog v-model="showReportDialog" title="上报资产" width="480px">
      <el-form :model="reportForm" label-width="100px">
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
          <el-radio-group v-model="reportForm.record_type">
            <el-radio value="balance">余额+收益</el-radio>
            <el-radio value="transfer_in">转入</el-radio>
            <el-radio value="transfer_out">转出</el-radio>
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
    <el-dialog v-model="showEditDialog" title="编辑资产记录" width="480px">
      <el-form :model="editForm" label-width="100px">
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
  color: #67c23a;
}

.earnings-value.negative,
.platform-earnings.negative,
.record-earnings.negative {
  color: #f56c6c;
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
  color: #67c23a;
  margin-top: 2px;
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
  color: #606266;
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
</style>
