<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ChatDotRound, CircleCheck, Delete } from '@element-plus/icons-vue'
import type { MergedReading } from '@/composables/useMergedReadings'
import type { Room } from '@/types'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const props = defineProps<{
  loading: boolean
  data: MergedReading[]
  roomMap: Map<number, Room>
  hideAmounts: boolean
  formatAmount: (value: number, currency?: string) => string
  maskedAmount: (value: number) => string
  getRoomNumber: (roomId: number) => string
  getRoomInfo: (roomId: number) => Room | undefined
}>()

// 是否显示删除按钮（仅超级管理员可见）
const showDeleteButton = computed(() => authStore.isSuperAdmin)

const emit = defineEmits<{
  'show-reminder': [row: MergedReading]
  'show-payment': [row: MergedReading]
  'edit': [row: MergedReading]
  'delete': [row: MergedReading]
  'selection-change': [selection: MergedReading[]]
}>()

const tableRef = defineModel<object>('tableRef')

// 展开的行，默认展开所有行
const expandedRows = ref<string[]>([])

// 监听数据变化，只展开未收租的行
watch(() => props.data, (newData) => {
  // 使用 room_id + reading_date 作为唯一标识，只展开未收租的记录
  expandedRows.value = newData
    .filter(item => !item.is_paid)
    .map(item => `${item.room_id}-${item.reading_date}`)
}, { immediate: true })

const handleReminder = (row: MergedReading) => {
  emit('show-reminder', row)
}

const handlePayment = (row: MergedReading) => {
  emit('show-payment', row)
}

const handleDelete = (row: MergedReading) => {
  emit('delete', row)
}
</script>

<template>
  <el-table
    ref="tableRef"
    v-loading="loading"
    :data="data"
    stripe
    class="utility-table"
    :expand-row-keys="expandedRows"
    :row-key="(row: any) => `${row.room_id}-${row.reading_date}`"
    @selection-change="(sel: any[]) => emit('selection-change', sel)"
  >
    <el-table-column type="selection" width="55" />
    <el-table-column type="expand" width="1">
      <template #default="{ row }">
        <!-- 只有未收租才显示操作按钮 -->
        <div v-if="!row.is_paid" class="action-row">
          <div class="action-buttons">
            <el-button
              type="primary"
              size="small"
              :icon="ChatDotRound"
              class="action-btn"
              @click="handleReminder(row)"
            >
              <span class="btn-text-full">催租消息</span>
              <span class="btn-text-short">催租</span>
            </el-button>
            <el-button
              type="success"
              size="small"
              :icon="CircleCheck"
              class="action-btn"
              :disabled="row.is_paid"
              @click="handlePayment(row)"
            >
              <span class="btn-text-full">{{ row.is_paid ? '已收租' : '标记已收' }}</span>
              <span class="btn-text-short">{{ row.is_paid ? '已收' : '标记' }}</span>
            </el-button>
            <el-button
              v-if="showDeleteButton"
              type="danger"
              size="small"
              :icon="Delete"
              class="action-btn"
              @click="handleDelete(row)"
            >
              <span class="btn-text-full">删除</span>
              <span class="btn-text-short">删除</span>
            </el-button>
          </div>
        </div>
      </template>
    </el-table-column>

    <el-table-column prop="reading_date" label="抄表日期" width="120">
      <template #default="{ row }">
        {{ new Date(row.reading_date).toLocaleDateString('zh-CN') }}
      </template>
    </el-table-column>

    <el-table-column prop="room_id" label="房间号" width="120">
      <template #default="{ row }">
        {{ getRoomNumber(row.room_id) }}
      </template>
    </el-table-column>

    <el-table-column label="💰 月租金" width="110">
      <template #default="{ row }">
        <span class="rent-amount">{{ formatAmount(getRoomInfo(row.room_id)?.monthly_rent || 0) }}</span>
      </template>
    </el-table-column>

    <el-table-column label="💧 水表" width="200">
      <template #default="{ row }">
        <div v-if="row.water_reading" class="reading-cell">
          <div v-if="row.water_reading.amount === 0 || row.water_reading.amount === '0'" class="no-data">
            无水电费
          </div>
          <div v-else>
            <div class="reading-row">
              <span class="label">上次:</span>
              <span>{{ row.water_reading.previous_reading }}</span>
            </div>
            <div class="reading-row">
              <span class="label">本次:</span>
              <span>{{ row.water_reading.reading }}</span>
            </div>
            <div class="reading-row highlight">
              <span class="label">用量:</span>
              <span>{{ row.water_reading.usage }}</span>
            </div>
          </div>
        </div>
        <span v-else class="no-data">未录入</span>
      </template>
    </el-table-column>

    <el-table-column label="⚡ 电表" width="200">
      <template #default="{ row }">
        <div v-if="row.electricity_reading" class="reading-cell">
          <div v-if="row.electricity_reading.amount === 0 || row.electricity_reading.amount === '0'" class="no-data">
            无水电费
          </div>
          <div v-else>
            <div class="reading-row">
              <span class="label">上次:</span>
              <span>{{ row.electricity_reading.previous_reading }}</span>
            </div>
            <div class="reading-row">
              <span class="label">本次:</span>
              <span>{{ row.electricity_reading.reading }}</span>
            </div>
            <div class="reading-row highlight">
              <span class="label">用量:</span>
              <span>{{ row.electricity_reading.usage }}</span>
            </div>
          </div>
        </div>
        <span v-else class="no-data">未录入</span>
      </template>
    </el-table-column>

    <el-table-column label="费用" width="150">
      <template #default="{ row }">
        <div class="amount-cell">
          <div v-if="row.water_reading" class="amount-row">
            <span class="amount-label">水费:</span>
            <span class="amount">{{ formatAmount(Number(row.water_reading.amount || 0)) }}</span>
          </div>
          <div v-if="row.electricity_reading" class="amount-row">
            <span class="amount-label">电费:</span>
            <span class="amount">{{ formatAmount(Number(row.electricity_reading.amount || 0)) }}</span>
          </div>
          <div class="total-amount">
            <span class="amount-label">总计:</span>
            <span class="amount total">{{ formatAmount(Number(row.total_amount || 0)) }}</span>
            <span v-if="row.is_paid" class="paid-badge">已收租</span>
          </div>
        </div>
      </template>
    </el-table-column>

    <el-table-column prop="notes" label="备注" min-width="150" show-overflow-tooltip />
  </el-table>
</template>

<style scoped>
.utility-table {
  margin-bottom: 20px;
}

.action-row {
  padding: 12px 16px;
  background: #f5f7fa;
  border-top: 1px solid #ebeef5;
}

.action-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end; /* 电脑端右对齐 */
}

.action-buttons .el-button {
  margin: 0;
}

/* 短文字默认隐藏 */
.btn-text-short {
  display: none;
}

/* 完整文字默认显示 */
.btn-text-full {
  display: inline;
}

.reading-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.reading-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}

.reading-row .label {
  color: #909399;
  font-weight: 500;
}

.reading-row.highlight {
  color: #409eff;
  font-weight: 600;
  margin-top: 2px;
}

.no-data {
  color: #c0c4cc;
  font-size: 13px;
}

.amount-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.amount-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}

.amount-label {
  color: #909399;
  font-weight: 500;
}

.amount {
  color: #f56c6c;
  font-weight: 600;
}

.total-amount {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px dashed #dcdfe6;
}

.amount.total {
  color: #f56c6c;
  font-size: 15px;
  font-weight: 700;
}

.paid-badge {
  margin-left: 8px;
  padding: 2px 8px;
  background: #67c23a;
  color: white;
  font-size: 12px;
  border-radius: 4px;
  font-weight: 500;
}

/* 移动端优化 */
@media (max-width: 768px) {
  /* 调整表格列宽 */
  :deep(.el-table__body-wrapper) {
    overflow-x: auto !important;
  }

  /* 表格整体横向滚动 */
  .utility-table {
    overflow-x: auto;
  }

  :deep(.el-table__body) {
    width: 100% !important;
  }

  /* 操作按钮移动端优化：左对齐，缩短宽度 */
  .action-buttons {
    flex-direction: row; /* 横向排列 */
    justify-content: flex-start; /* 左对齐 */
    gap: 6px;
  }

  .action-buttons .el-button {
    width: auto; /* 自动宽度 */
    min-width: 80px; /* 最小宽度 */
    max-width: 120px; /* 最大宽度与抄表日期列差不多 */
  }

  /* 显示短文字，隐藏完整文字 */
  .btn-text-short {
    display: inline;
  }

  .btn-text-full {
    display: none;
  }
}

/* 小屏幕手机进一步优化 */
@media (max-width: 375px) {
  /* 表格支持横向滚动 */
  :deep(.el-table) {
    display: block;
    overflow-x: auto;
  }

  :deep(.el-table__body-wrapper) {
    overflow-x: auto !important;
  }

  /* 操作按钮更紧凑 */
  .action-buttons .el-button {
    font-size: 11px;
    padding: 4px 6px;
    min-width: 70px;
    max-width: 110px;
  }

  .action-row {
    padding: 8px 12px;
  }
}
</style>
