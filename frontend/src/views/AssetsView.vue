<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, ArrowDown, Wallet } from '@element-plus/icons-vue'
import { assetApi } from '@/api/assets'
import { useAmountVisibility } from '@/composables/useAmountVisibility'
import type { AssetSummary, AssetPlatformDetail, AssetRecord } from '@/types'

const { hideAmounts, formatAmount } = useAmountVisibility()

const loading = ref(false)
const summary = ref<AssetSummary | null>(null)

// 对话框
const showPlatformDialog = ref(false)
const platformForm = ref({ name: '', current_balance: 0, total_earnings: 0 })
const platformFormLoading = ref(false)
const isEditingPlatform = ref(false)
const editingPlatformId = ref<number | null>(null)

// 上报对话框
const showReportDialog = ref(false)
const reportForm = ref({ platform_id: 0, record_type: 'balance', reported_balance: 0, reported_earnings: 0, amount: 0, notes: '' })
const reportLoading = ref(false)
const selectedPlatform = ref<AssetPlatformDetail | null>(null)

// 展开记录
const expandedPlatformIds = ref<Set<number>>(new Set())

const loadSummary = async () => {
  loading.value = true
  try {
    summary.value = await assetApi.getSummary()
  } catch (error) {
    ElMessage.error('加载资产数据失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 添加平台
const openAddPlatform = () => {
  isEditingPlatform.value = false
  editingPlatformId.value = null
  platformForm.value = { name: '', current_balance: 0, total_earnings: 0 }
  showPlatformDialog.value = true
}

const openEditPlatform = (p: AssetPlatformDetail) => {
  isEditingPlatform.value = true
  editingPlatformId.value = p.id
  platformForm.value = { name: p.name, current_balance: p.current_balance, total_earnings: p.total_earnings }
  showPlatformDialog.value = true
}

const submitPlatform = async () => {
  if (!platformForm.value.name.trim()) {
    ElMessage.warning('请输入平台名称')
    return
  }
  platformFormLoading.value = true
  try {
    if (isEditingPlatform.value && editingPlatformId.value) {
      await assetApi.updatePlatform(editingPlatformId.value, platformForm.value)
      ElMessage.success('平台已更新')
    } else {
      await assetApi.createPlatform(platformForm.value)
      ElMessage.success('平台已创建')
    }
    showPlatformDialog.value = false
    await loadSummary()
  } catch (error) {
    ElMessage.error('操作失败')
    console.error(error)
  } finally {
    platformFormLoading.value = false
  }
}

// 删除平台
const handleDeletePlatform = async (p: AssetPlatformDetail) => {
  try {
    await ElMessageBox.confirm(`确定删除平台"${p.name}"吗？所有记录将一并删除。`, '删除确认', {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await assetApi.deletePlatform(p.id)
    ElMessage.success('平台已删除')
    await loadSummary()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

// 上报
const openReport = (platform: AssetPlatformDetail) => {
  selectedPlatform.value = platform
  reportForm.value = {
    platform_id: platform.id,
    record_type: 'balance',
    reported_balance: platform.current_balance,
    reported_earnings: platform.total_earnings,
    amount: 0,
    notes: ''
  }
  showReportDialog.value = true
}

const submitReport = async () => {
  if (!reportForm.value.platform_id) return
  reportLoading.value = true
  try {
    const data: any = {
      platform_id: reportForm.value.platform_id,
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

// 切换展开记录
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
      <el-button type="primary" :icon="Plus" @click="openAddPlatform">添加平台</el-button>
    </div>

    <!-- 总资产卡片 -->
    <div v-loading="loading" class="summary-cards">
      <el-card class="summary-card total-balance">
        <div class="card-label">总资产</div>
        <div class="card-value">¥{{ summary ? formatAmount(summary.total_balance) : '-' }}</div>
      </el-card>
      <el-card class="summary-card total-earnings">
        <div class="card-label">累计总收益</div>
        <div class="card-value">¥{{ summary ? formatAmount(summary.total_earnings) : '-' }}</div>
      </el-card>
    </div>

    <!-- 各平台卡片 -->
    <div v-if="summary && summary.platforms.length === 0" class="empty-tip">
      <el-empty description="暂无资产平台，点击上方按钮添加" />
    </div>

    <div v-for="platform in summary?.platforms || []" :key="platform.id" class="platform-card">
      <el-card shadow="hover">
        <div class="platform-header">
          <div class="platform-info">
            <div class="platform-name">{{ platform.name }}</div>
            <div class="platform-balance">
              余额：<strong>¥{{ formatAmount(platform.current_balance) }}</strong>
            </div>
            <div class="platform-earnings">
              收益：<strong>¥{{ formatAmount(platform.total_earnings) }}</strong>
            </div>
          </div>
          <div class="platform-actions">
            <el-button type="primary" size="small" @click="openReport(platform)">上报</el-button>
            <el-dropdown trigger="click">
              <el-button size="small">
                操作<el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click.native="openEditPlatform(platform)">
                    <el-icon><Edit /></el-icon>编辑
                  </el-dropdown-item>
                  <el-dropdown-item @click.native="handleDeletePlatform(platform)" divided>
                    <el-icon><Delete /></el-icon>删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
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
                <span class="record-earnings">收益：¥{{ formatAmount(record.reported_earnings || 0) }}</span>
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
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 添加/编辑平台对话框 -->
    <el-dialog v-model="showPlatformDialog" :title="isEditingPlatform ? '编辑平台' : '添加平台'" width="420px">
      <el-form :model="platformForm" label-width="100px">
        <el-form-item label="平台名称">
          <el-input v-model="platformForm.name" placeholder="支付宝、网商银行..." />
        </el-form-item>
        <el-form-item label="当前余额">
          <el-input-number v-model="platformForm.current_balance" :min="0" :precision="2" style="width:100%" />
        </el-form-item>
        <el-form-item label="累计收益">
          <el-input-number v-model="platformForm.total_earnings" :min="0" :precision="2" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPlatformDialog = false">取消</el-button>
        <el-button type="primary" :loading="platformFormLoading" @click="submitPlatform">确定</el-button>
      </template>
    </el-dialog>

    <!-- 上报对话框 -->
    <el-dialog v-model="showReportDialog" :title="`上报 - ${selectedPlatform?.name || ''}`" width="480px">
      <el-form :model="reportForm" label-width="100px">
        <el-form-item label="上报类型">
          <el-radio-group v-model="reportForm.record_type">
            <el-radio value="balance">余额上报</el-radio>
            <el-radio value="transfer_in">转入</el-radio>
            <el-radio value="transfer_out">转出</el-radio>
          </el-radio-group>
        </el-form-item>

        <template v-if="reportForm.record_type === 'balance'">
          <el-form-item label="当前余额">
            <el-input-number v-model="reportForm.reported_balance" :min="0" :precision="2" style="width:100%" />
          </el-form-item>
          <el-form-item label="累计收益">
            <el-input-number v-model="reportForm.reported_earnings" :min="0" :precision="2" style="width:100%" />
          </el-form-item>
          <div class="form-hint">
            系统将自动计算转入/转出净额
          </div>
        </template>

        <template v-else>
          <el-form-item label="金额">
            <el-input-number v-model="reportForm.amount" :min="0.01" :precision="2" style="width:100%" />
          </el-form-item>
          <div class="form-hint">
            系统将自动更新当前余额
          </div>
        </template>

        <el-form-item label="备注">
          <el-input v-model="reportForm.notes" placeholder="可选：房租转账、零花钱等" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReportDialog = false">取消</el-button>
        <el-button type="primary" :loading="reportLoading" @click="submitReport">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.assets-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.page-header h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.summary-cards {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
}

.summary-card {
  flex: 1;
  text-align: center;
}

.summary-card .card-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}

.summary-card .card-value {
  font-size: 28px;
  font-weight: 700;
}

.total-balance .card-value {
  color: #409eff;
}

.total-earnings .card-value {
  color: #67c23a;
}

.platform-card {
  margin-bottom: 16px;
}

.platform-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.platform-info {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.platform-name {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  min-width: 100px;
}

.platform-balance {
  font-size: 14px;
  color: #606266;
}

.platform-balance strong {
  color: #409eff;
  font-size: 16px;
}

.platform-earnings {
  font-size: 14px;
  color: #606266;
}

.platform-earnings strong {
  color: #67c23a;
  font-size: 16px;
}

.platform-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  align-items: center;
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
  gap: 12px;
}

.record-item:last-child {
  border-bottom: none;
}

.record-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.record-note {
  font-size: 13px;
  color: #909399;
}

.record-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.record-balance,
.record-earnings {
  font-size: 13px;
  color: #606266;
}

.record-transfer {
  font-size: 13px;
  font-weight: 500;
}

.transfer-in {
  color: #67c23a;
}

.transfer-out {
  color: #e6a23c;
}

.record-time {
  font-size: 12px;
  color: #c0c4cc;
  white-space: nowrap;
}

.form-hint {
  font-size: 12px;
  color: #909399;
  margin: -8px 0 8px 100px;
}

.empty-tip {
  margin-top: 40px;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .assets-page {
    padding: 12px;
  }

  .summary-cards {
    flex-direction: column;
  }

  .platform-header {
    flex-direction: column;
    gap: 12px;
  }

  .platform-info {
    flex-wrap: wrap;
    gap: 8px;
  }

  .platform-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .record-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }

  .record-right {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
