<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useOverdueConfig } from '@/composables/useOverdueConfig'
import { authApi } from '@/api/auth'

const authStore = useAuthStore()
const {
  overdueCutoffDate, setOverdueCutoffDate,
  advanceRentDays, setAdvanceRentDays,
  expiringDays, setExpiringDays,
  recentPaymentDays, setRecentPaymentDays,
  recentReadingDays, setRecentReadingDays,
  lookbackMonths, setLookbackMonths,
  resetDefaults, defaults,
} = useOverdueConfig()

const tempCutoffDate = ref(overdueCutoffDate.value)
const tempAdvanceRentDays = ref(advanceRentDays.value)
const tempExpiringDays = ref(expiringDays.value)
const tempRecentPaymentDays = ref(recentPaymentDays.value)
const tempRecentReadingDays = ref(recentReadingDays.value)
const tempLookbackMonths = ref(lookbackMonths.value)

const tempDisplayName = ref(authStore.user?.full_name || '')
const savingName = ref(false)

const handleSave = async () => {
  setOverdueCutoffDate(tempCutoffDate.value)
  setAdvanceRentDays(tempAdvanceRentDays.value)
  setExpiringDays(tempExpiringDays.value)
  setRecentPaymentDays(tempRecentPaymentDays.value)
  setRecentReadingDays(tempRecentReadingDays.value)
  setLookbackMonths(tempLookbackMonths.value)
  ElMessage.success('保存成功，刷新页面后生效')
}

const handleSaveName = async () => {
  if (!authStore.user) return
  savingName.value = true
  try {
    await authApi.updateProfile(authStore.user.id, { full_name: tempDisplayName.value })
    await authStore.getCurrentUser()
    ElMessage.success('显示名称已更新')
  } catch {
    ElMessage.error('更新失败')
  } finally {
    savingName.value = false
  }
}

const handleReset = async () => {
  try {
    await ElMessageBox.confirm('确定恢复所有设置到默认值？', '恢复默认', { type: 'warning' })
    resetDefaults()
    tempCutoffDate.value = defaults.overdueCutoffDate as string
    tempAdvanceRentDays.value = defaults.advanceRentDays as number
    tempExpiringDays.value = defaults.expiringDays as number
    tempRecentPaymentDays.value = defaults.recentPaymentDays as number
    tempRecentReadingDays.value = defaults.recentReadingDays as number
    tempLookbackMonths.value = defaults.lookbackMonths as number
    ElMessage.success('已恢复默认值，刷新页面后生效')
  } catch {}
}
</script>

<template>
  <div class="settings-view">
    <div class="page-header">
      <h1>系统设置</h1>
    </div>

    <el-card>
      <template #header>
        <div class="card-header">
          <span class="card-title">收租提醒设置</span>
          <el-button size="small" @click="handleReset">恢复默认</el-button>
        </div>
      </template>

      <div class="setting-item">
        <div class="setting-info">
          <div class="setting-label">豁免截止日期</div>
          <div class="setting-desc">此日期之前的应交房租视为已收清，不再计入未收租提醒</div>
        </div>
        <el-date-picker
          v-model="tempCutoffDate"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
          style="width: 180px"
        />
      </div>

      <el-divider />

      <div class="setting-item">
        <div class="setting-info">
          <div class="setting-label">提前收租天数</div>
          <div class="setting-desc">应交日前几天开始计入欠租管理（默认 {{ defaults.advanceRentDays }} 天）</div>
        </div>
        <el-input-number v-model="tempAdvanceRentDays" :min="0" :max="10" style="width: 150px" />
      </div>

      <el-divider />

      <div class="setting-item">
        <div class="setting-info">
          <div class="setting-label">到期提醒天数</div>
          <div class="setting-desc">提前多少天显示即将到期提醒（默认 {{ defaults.expiringDays }} 天）</div>
        </div>
        <el-input-number v-model="tempExpiringDays" :min="1" :max="30" style="width: 150px" />
      </div>

      <el-divider />

      <div class="setting-item">
        <div class="setting-info">
          <div class="setting-label">近期缴费天数</div>
          <div class="setting-desc">多少天内有过缴费记录视为"近期已收"，不重复提醒（默认 {{ defaults.recentPaymentDays }} 天）</div>
        </div>
        <el-input-number v-model="tempRecentPaymentDays" :min="1" :max="30" style="width: 150px" />
      </div>

      <el-divider />

      <div class="setting-item">
        <div class="setting-info">
          <div class="setting-label">近期抄表天数</div>
          <div class="setting-desc">到期提醒中，多少天内的水电记录允许"标记已收"（默认 {{ defaults.recentReadingDays }} 天）</div>
        </div>
        <el-input-number v-model="tempRecentReadingDays" :min="1" :max="30" style="width: 150px" />
      </div>

      <el-divider />

      <div class="setting-item">
        <div class="setting-info">
          <div class="setting-label">缴费页回溯月数</div>
          <div class="setting-desc">缴费记录页收租概况显示最近几个月的数据（默认 {{ defaults.lookbackMonths }} 个月，即当月和上月）</div>
        </div>
        <el-input-number v-model="tempLookbackMonths" :min="1" :max="12" style="width: 150px" />
      </div>

      <div style="margin-top: 20px; text-align: right;">
        <el-button type="primary" @click="handleSave">保存设置</el-button>
      </div>
    </el-card>

    <el-card style="margin-top: 20px;">
      <template #header>
        <span class="card-title">账户信息</span>
      </template>
      <div class="account-info">
        <div class="info-row">
          <span class="info-label">用户名</span>
          <span class="info-value">{{ authStore.user?.username }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">角色</span>
          <span class="info-value">{{ authStore.user?.role }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">显示名称</span>
          <div class="name-edit">
            <el-input v-model="tempDisplayName" placeholder="请输入显示名称" style="width: 200px" />
            <el-button type="primary" size="small" :loading="savingName" @click="handleSaveName">保存</el-button>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.settings-view {
  padding: 20px;
  max-width: 800px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-weight: 600;
  font-size: 16px;
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
}

.setting-info {
  flex: 1;
}

.setting-label {
  font-weight: 500;
  font-size: 14px;
  color: #303133;
  margin-bottom: 4px;
}

.setting-desc {
  font-size: 13px;
  color: #909399;
}

.account-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.info-label {
  min-width: 80px;
  color: #909399;
  font-size: 14px;
}

.info-value {
  color: #303133;
  font-size: 14px;
}

.name-edit {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
