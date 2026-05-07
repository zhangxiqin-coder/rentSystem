<script setup lang="ts">
import type { MergedReading } from '@/composables/useMergedReadings'
import type { Room } from '@/types'

defineProps<{
  loading: boolean
  data: MergedReading[]
  roomMap: Map<number, Room>
  hideAmounts: boolean
  formatAmount: (value: number, currency?: string) => string
  maskedAmount: (value: number) => string
  getRoomNumber: (roomId: number) => string
  getRoomInfo: (roomId: number) => Room | undefined
}>()

const emit = defineEmits<{
  'show-reminder': [row: MergedReading]
  'show-payment': [row: MergedReading]
  'edit': [row: MergedReading]
  'delete': [row: MergedReading]
  'selection-change': [selection: MergedReading[]]
}>()

const tableRef = defineModel<object>('tableRef')
</script>

<template>
  <el-table
    ref="tableRef"
    v-loading="loading"
    :data="data"
    stripe
    class="utility-table"
    @selection-change="(sel: any[]) => emit('selection-change', sel)"
  >
    <el-table-column type="selection" width="55" />

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
          </div>
        </div>
      </template>
    </el-table-column>

    <el-table-column prop="notes" label="备注" min-width="150" show-overflow-tooltip />

    <el-table-column label="操作" width="250" fixed="right">
      <template #default="{ row }">
        <el-button
          type="info"
          size="small"
          @click="emit('show-reminder', row)"
        >
          催租消息
        </el-button>
        <el-button
          type="success"
          size="small"
          :disabled="row.is_paid"
          @click="emit('show-payment', row)"
        >
          {{ row.is_paid ? '已收租' : '标记已收' }}
        </el-button>
        <el-button
          type="danger"
          size="small"
          @click="emit('delete', row)"
        >
          删除
        </el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<style scoped>
.utility-table {
  margin-bottom: 20px;
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
</style>
