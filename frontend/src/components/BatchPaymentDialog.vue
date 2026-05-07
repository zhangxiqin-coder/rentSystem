<script setup lang="ts">
defineProps<{
  modelValue: boolean
  batchPayments: Array<{
    room_id: number
    reading_date: string
    rent_original: number
    rent_amount: number
    water_original: number
    water_amount: number
    electricity_original: number
    electricity_amount: number
    payment_method: string
    notes: string
  }>
  batchPaymentLoading: boolean
  formatAmount: (value: number, currency?: string) => string
  getRoomNumber: (roomId: number) => string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'submit': []
}>()
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="批量收租"
    width="900px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-table :data="batchPayments" max-height="400">
      <el-table-column prop="room_id" label="房间" width="100">
        <template #default="{ row }">
          {{ getRoomNumber(row.room_id) }}
        </template>
      </el-table-column>

      <el-table-column label="房租" width="150">
        <template #default="{ row }">
          <el-input-number
            v-model="row.rent_amount"
            :min="0"
            :max="row.rent_original"
            :precision="2"
            :step="10"
            size="small"
          />
        </template>
      </el-table-column>

      <el-table-column label="水费" width="150">
        <template #default="{ row }">
          <el-input-number
            v-model="row.water_amount"
            :min="0"
            :max="row.water_original"
            :precision="2"
            :step="1"
            size="small"
            :disabled="row.water_original === 0"
          />
        </template>
      </el-table-column>

      <el-table-column label="电费" width="150">
        <template #default="{ row }">
          <el-input-number
            v-model="row.electricity_amount"
            :min="0"
            :max="row.electricity_original"
            :precision="2"
            :step="1"
            size="small"
            :disabled="row.electricity_original === 0"
          />
        </template>
      </el-table-column>

      <el-table-column label="收款方式" width="130">
        <template #default="{ row }">
          <el-select v-model="row.payment_method" size="small">
            <el-option label="现金" value="现金" />
            <el-option label="微信支付" value="微信支付" />
            <el-option label="支付宝" value="支付宝" />
            <el-option label="银行转账" value="银行转账" />
          </el-select>
        </template>
      </el-table-column>

      <el-table-column label="备注" min-width="150">
        <template #default="{ row }">
          <el-input v-model="row.notes" size="small" placeholder="备注" />
        </template>
      </el-table-column>
    </el-table>

    <el-divider />

    <div class="batch-summary">
      <div>
        <span>原始总额：</span>
        <span class="amount">{{ formatAmount(batchPayments.reduce((sum, p) => sum + p.rent_original + p.water_original + p.electricity_original, 0)) }}</span>
      </div>
      <div>
        <span>实收总额：</span>
        <span class="amount actual">{{ formatAmount(batchPayments.reduce((sum, p) => sum + p.rent_amount + p.water_amount + p.electricity_amount, 0)) }}</span>
      </div>
    </div>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="batchPaymentLoading" @click="emit('submit')">
        确认批量收款
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.batch-summary {
  display: flex;
  justify-content: space-around;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 16px;
}

.batch-summary > div {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.batch-summary .amount {
  font-size: 20px;
  font-weight: 700;
  color: #303133;
}

.batch-summary .amount.actual {
  font-size: 24px;
  color: #67c23a;
}
</style>
