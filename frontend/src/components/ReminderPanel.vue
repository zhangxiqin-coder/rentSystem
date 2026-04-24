<template>
  <div class="reminder-panel">
    <el-card class="summary-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="title">📋 提醒事项</span>
          <el-button type="primary" size="small" @click="sendNotifications" :loading="sending">
            发送微信通知
          </el-button>
        </div>
      </template>

      <!-- 加载中 -->
      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="3" animated />
      </div>

      <!-- 无提醒 -->
      <el-empty
        v-else-if="!loading && summary.total_reminders === 0"
        description="暂无提醒事项"
        :image-size="100"
      />

      <!-- 有提醒 -->
      <div v-else>
        <!-- 提醒摘要 -->
        <div class="summary-section">
          <el-row :gutter="16">
            <el-col :span="8">
              <el-statistic title="今日应付" :value="summary.payment_due.today">
                <template #suffix>间</template>
              </el-statistic>
            </el-col>
            <el-col :span="8">
              <el-statistic title="7天内到期" :value="summary.lease_expiry.next_7_days + summary.payment_due.next_7_days">
                <template #suffix>间</template>
              </el-statistic>
            </el-col>
            <el-col :span="8">
              <el-statistic title="已逾期" :value="summary.payment_due.overdue + summary.lease_expiry.overdue">
                <template #suffix>间</template>
              </el-statistic>
            </el-col>
          </el-row>
        </div>

        <el-divider />

        <!-- 提醒列表 -->
        <div class="reminder-list">
          <div
            v-for="reminder in reminders"
            :key="`${reminder.room_id}-${reminder.reminder_type}`"
            class="reminder-item"
            :class="getReminderClass(reminder)"
          >
            <div class="reminder-header">
              <el-tag
                :type="getReminderTagType(reminder.reminder_type)"
                size="small"
                effect="plain"
              >
                {{ getReminderTypeLabel(reminder.reminder_type) }}
              </el-tag>
              <span class="room-number">{{ reminder.room_number }}</span>
              <span class="days-badge">{{ getDaysText(reminder.days_left) }}</span>
            </div>
            <div class="reminder-content">
              <p class="message">{{ reminder.message }}</p>
              <div v-if="reminder.breakdown" class="breakdown">
                <span>房租: ¥{{ reminder.breakdown.rent.toFixed(2) }}</span>
                <span>水费: ¥{{ reminder.breakdown.water.toFixed(2) }}</span>
                <span>电费: ¥{{ reminder.breakdown.electricity.toFixed(2) }}</span>
              </div>
              <p v-if="reminder.tenant_name" class="tenant">租户: {{ reminder.tenant_name }}</p>
            </div>
            <div class="reminder-actions">
              <el-button
                v-if="reminder.reminder_type.includes('payment')"
                type="primary"
                size="small"
                @click="goToPayment(reminder)"
              >
                去收租
              </el-button>
              <el-button
                v-if="reminder.reminder_type.includes('lease')"
                type="warning"
                size="small"
                @click="goToRoom(reminder)"
              >
                查看租约
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import { useRouter } from 'vue-router'

interface SummaryItem {
  next_7_days: number
  next_30_days: number
  overdue: number
}

interface Summary {
  lease_expiry: SummaryItem
  payment_due: {
    today: number
    next_7_days: number
    overdue: number
  }
  total_reminders: number
}

interface Reminder {
  room_id: number
  room_number: string
  reminder_type: string
  reminder_date: string
  days_left: number
  amount: number
  tenant_name?: string
  breakdown?: {
    rent: number
    water: number
    electricity: number
  }
  message: string
}

const router = useRouter()

const loading = ref(false)
const sending = ref(false)
const summary = ref<Summary>({
  lease_expiry: { next_7_days: 0, next_30_days: 0, overdue: 0 },
  payment_due: { today: 0, next_7_days: 0, overdue: 0 },
  total_reminders: 0
})
const reminders = ref<Reminder[]>([])

// 获取提醒摘要
const fetchSummary = async () => {
  try {
    loading.value = true
    const response = await api.get('/reminders/summary')
    summary.value = response.data
  } catch (error: any) {
    console.error('获取提醒摘要失败:', error)
    ElMessage.error(error.response?.data?.detail || '获取提醒摘要失败')
  } finally {
    loading.value = false
  }
}

// 获取提醒列表
const fetchReminders = async (daysAhead: number = 7) => {
  try {
    loading.value = true
    const response = await api.get(`/reminders/upcoming?days_ahead=${daysAhead}&include_overdue=true`)
    reminders.value = response.data.reminders
    await fetchSummary()
  } catch (error: any) {
    console.error('获取提醒列表失败:', error)
    ElMessage.error(error.response?.data?.detail || '获取提醒列表失败')
  } finally {
    loading.value = false
  }
}

// 发送微信通知
const sendNotifications = async () => {
  try {
    sending.value = true
    const response = await api.post('/reminders/send-notifications?days_ahead=7')
    ElMessage.success(`已发送 ${response.data.sent_count} 条提醒通知`)
  } catch (error: any) {
    console.error('发送通知失败:', error)
    ElMessage.error(error.response?.data?.detail || '发送通知失败')
  } finally {
    sending.value = false
  }
}

// 获取提醒类型标签
const getReminderTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    lease_expiry: '租约到期',
    lease_overdue: '租约逾期',
    payment_due: '应付房租',
    payment_overdue: '房租逾期'
  }
  return labels[type] || type
}

// 获取提醒标签类型
const getReminderTagType = (type: string) => {
  if (type.includes('overdue')) return 'danger'
  if (type === 'lease_expiry') return 'warning'
  return 'primary'
}

// 获取提醒样式类
const getReminderClass = (reminder: Reminder) => {
  if (reminder.reminder_type.includes('overdue')) return 'overdue'
  if (reminder.days_left === 0) return 'today'
  if (reminder.days_left <= 3) return 'urgent'
  return ''
}

// 获取天数文本
const getDaysText = (days: number) => {
  if (days === 0) return '今天'
  if (days < 0) return `已逾期${-days}天`
  return `${days}天后`
}

// 跳转到收租页面
const goToPayment = (reminder: Reminder) => {
  router.push('/utility')
}

// 跳转到房间详情
const goToRoom = (reminder: Reminder) => {
  router.push(`/rooms?id=${reminder.room_id}`)
}

onMounted(() => {
  fetchReminders(7)
})

defineExpose({
  refresh: () => fetchReminders(7)
})
</script>

<style scoped>
.reminder-panel {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: 18px;
  font-weight: bold;
}

.loading-container {
  padding: 20px;
}

.summary-section {
  margin-bottom: 20px;
}

.summary-section :deep(.el-statistic) {
  text-align: center;
}

.summary-section :deep(.el-statistic__head) {
  font-size: 14px;
  color: #909399;
}

.summary-section :deep(.el-statistic__content) {
  font-size: 24px;
  font-weight: bold;
}

.reminder-list {
  max-height: 500px;
  overflow-y: auto;
}

.reminder-item {
  padding: 16px;
  margin-bottom: 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  transition: all 0.3s;
}

.reminder-item:hover {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.reminder-item.overdue {
  border-left: 4px solid #f56c6c;
  background-color: #fef0f0;
}

.reminder-item.today {
  border-left: 4px solid #e6a23c;
  background-color: #fdf6ec;
}

.reminder-item.urgent {
  border-left: 4px solid #409eff;
}

.reminder-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.room-number {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

.days-badge {
  margin-left: auto;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  background-color: #f0f2f5;
  color: #606266;
}

.reminder-item.today .days-badge {
  background-color: #e6a23c;
  color: white;
}

.reminder-item.overdue .days-badge {
  background-color: #f56c6c;
  color: white;
}

.reminder-content {
  margin-bottom: 12px;
}

.message {
  font-size: 14px;
  color: #606266;
  margin: 0 0 8px 0;
}

.breakdown {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #909399;
}

.tenant {
  font-size: 12px;
  color: #909399;
  margin: 0;
}

.reminder-actions {
  display: flex;
  gap: 8px;
}
</style>
