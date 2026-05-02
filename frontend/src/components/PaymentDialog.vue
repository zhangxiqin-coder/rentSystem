<script setup lang="ts">
defineProps<{
  modelValue: boolean
  paymentForm: {
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
    period_start: string
    period_end: string
  }
  paymentLoading: boolean
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
    title="💰 标记已收（支持打折）"
    width="500px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form :model="paymentForm" label-width="100px">
      <el-form-item label="房间号">
        <span>{{ getRoomNumber(paymentForm.room_id) }}</span>
      </el-form-item>

      <el-form-item label="抄表日期">
        <span>{{ paymentForm.reading_date }}</span>
      </el-form-item>

      <el-divider content-position="left">🏠 房租</el-divider>

      <el-form-item v-if="paymentForm.period_start" label="覆盖周期">
        <span style="font-weight: 500;">{{ paymentForm.period_start }} 至 {{ paymentForm.period_end }}</span>
      </el-form-item>

      <el-form-item label="原始房租">
        <span class="original-amount">{{ formatAmount(Number(paymentForm.rent_original || 0)) }}</span>
      </el-form-item>

      <el-form-item label="实收房租">
        <el-input-number
          v-model="paymentForm.rent_amount"
          :min="0"
          :max="Number(paymentForm.rent_original || 0)"
          :precision="2"
          :step="10"
        />
        <span v-if="Number(paymentForm.rent_amount || 0) < Number(paymentForm.rent_original || 0)" class="discount-hint">
          打折：{{ formatAmount(Number(paymentForm.rent_original || 0) - Number(paymentForm.rent_amount || 0)) }}
        </span>
      </el-form-item>

      <el-divider content-position="left">💧 水费</el-divider>

      <el-form-item label="原始水费">
        <span class="original-amount">{{ formatAmount(Number(paymentForm.water_original || 0)) }}</span>
      </el-form-item>

      <el-form-item label="实收水费">
        <el-input-number
          v-model="paymentForm.water_amount"
          :min="0"
          :max="Number(paymentForm.water_original || 0)"
          :precision="2"
          :step="1"
        />
        <span v-if="Number(paymentForm.water_amount || 0) < Number(paymentForm.water_original || 0)" class="discount-hint">
          打折：{{ formatAmount(Number(paymentForm.water_original || 0) - Number(paymentForm.water_amount || 0)) }}
        </span>
      </el-form-item>

      <el-divider content-position="left">⚡ 电费</el-divider>

      <el-form-item label="原始电费">
        <span class="original-amount">{{ formatAmount(Number(paymentForm.electricity_original || 0)) }}</span>
      </el-form-item>

      <el-form-item label="实收电费">
        <el-input-number
          v-model="paymentForm.electricity_amount"
          :min="0"
          :max="Number(paymentForm.electricity_original || 0)"
          :precision="2"
          :step="1"
        />
        <span v-if="Number(paymentForm.electricity_amount || 0) < Number(paymentForm.electricity_original || 0)" class="discount-hint">
          打折：{{ formatAmount(Number(paymentForm.electricity_original || 0) - Number(paymentForm.electricity_amount || 0)) }}
        </span>
      </el-form-item>

      <el-divider />

      <el-form-item label="总计">
        <div class="total-summary">
          <div>原始总额：{{ formatAmount(Number(paymentForm.rent_original || 0) + Number(paymentForm.water_original || 0) + Number(paymentForm.electricity_original || 0)) }}</div>
          <div class="actual-total">实收总额：{{ formatAmount(Number(paymentForm.rent_amount || 0) + Number(paymentForm.water_amount || 0) + Number(paymentForm.electricity_amount || 0)) }}</div>
          <div v-if="(Number(paymentForm.rent_amount || 0) + Number(paymentForm.water_amount || 0) + Number(paymentForm.electricity_amount || 0)) < (Number(paymentForm.rent_original || 0) + Number(paymentForm.water_original || 0) + Number(paymentForm.electricity_original || 0))" class="total-discount">
            总折扣：{{ formatAmount((Number(paymentForm.rent_original || 0) + Number(paymentForm.water_original || 0) + Number(paymentForm.electricity_original || 0)) - (Number(paymentForm.rent_amount || 0) + Number(paymentForm.water_amount || 0) + Number(paymentForm.electricity_amount || 0))) }}
          </div>
        </div>
      </el-form-item>

      <el-form-item label="收款方式">
        <el-select v-model="paymentForm.payment_method">
          <el-option label="现金" value="现金" />
          <el-option label="微信支付" value="微信支付" />
          <el-option label="支付宝" value="支付宝" />
          <el-option label="银行转账" value="银行转账" />
        </el-select>
      </el-form-item>

      <el-form-item label="备注">
        <el-input
          v-model="paymentForm.notes"
          type="textarea"
          :rows="2"
          placeholder="可选，如：提前付款、部分付款等"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="paymentLoading" @click="emit('submit')">
        确认收款
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.original-amount {
  font-size: 16px;
  color: #909399;
  text-decoration: line-through;
}

.discount-hint {
  margin-left: 10px;
  font-size: 13px;
  color: #e6a23c;
  font-weight: 500;
}

.total-summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.total-summary > div {
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 14px;
}

.actual-total {
  font-size: 18px !important;
  font-weight: 700;
  color: #67c23a !important;
  background: #f0f9ff !important;
}

.total-discount {
  color: #e6a23c;
  font-weight: 600;
  background: #fff7e6 !important;
}
</style>
