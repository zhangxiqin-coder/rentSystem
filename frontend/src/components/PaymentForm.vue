<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import type { Payment, CreatePaymentRequest, UpdatePaymentRequest } from '@/types'
import { getCoveragePeriod } from '@/utils/paymentCycle'

interface Props {
  payment?: Payment
  roomId?: number
  monthlyRent?: number
  paymentCycle?: number
  leaseStart?: string
  /** 本房间全部付款记录（推算覆盖周期用，网格需要完整付款史） */
  rentPayments?: Payment[]
  loading?: boolean
}

interface Emits {
  (e: 'submit', data: CreatePaymentRequest | UpdatePaymentRequest): void
  (e: 'cancel'): void
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
})

const emit = defineEmits<Emits>()

const formRef = ref<FormInstance>()
const formData = ref<CreatePaymentRequest>({
  room_id: props.roomId || 0,
  amount: 0,
  payment_type: 'rent',
  payment_date: new Date().toISOString().split('T')[0],
  due_date: '',
  status: 'pending',
  payment_method: '',
  description: '',
})

const rules: FormRules<CreatePaymentRequest> = {
  room_id: [
    { required: true, message: '请选择房间', trigger: 'blur' },
  ],
  payment_type: [
    { required: true, message: '请选择付款类型', trigger: 'change' },
  ],
  amount: [
    { required: true, message: '请输入金额', trigger: 'blur' },
    { type: 'number', min: 0.01, message: '金额必须大于0', trigger: 'blur' },
  ],
  payment_date: [
    { required: true, message: '请选择缴费日期', trigger: 'change' },
  ],
  status: [
    { required: true, message: '请选择状态', trigger: 'change' },
  ],
}

const is房租Type = computed(() => formData.value.payment_type === 'rent')

const expectedRent = computed(() => {
  const rent = Number(props.monthlyRent || 0)
  const cycle = Math.max(1, Number(props.paymentCycle || 1))
  return rent * cycle
})

const autoFillRent = () => {
  if (is房租Type.value) {
    formData.value.amount = expectedRent.value
    autoFillPeriod()
  }
}

const autoFillPeriod = () => {
  if (!props.leaseStart) return
  // 覆盖周期 = 下一个未付期（预收口径，v5 起租日网格）。
  // 修复前 bug：从起租日推网格停在"今天所在期"且不看付款记录——
  // 租客已预付到 10-09 时仍显示 09-10~10-09（已收过的期）。
  // 另修 toISOString() UTC 偏移隐患（东八区 0-8 点会得到昨天）。
  const coverage = getCoveragePeriod(
    {
      room_id: props.roomId,
      payment_cycle: props.paymentCycle,
      lease_start: props.leaseStart,
    },
    (props.rentPayments || []).filter(p => p && p.payment_date)
  )
  if (coverage) {
    formData.value.period_start = coverage.start
    formData.value.period_end = coverage.end
  }
}

// Watch for payment prop changes to populate form
watch(
  () => props.payment,
  (newPayment) => {
    if (newPayment) {
      formData.value = {
        room_id: newPayment.room_id,
        amount: newPayment.amount,
        payment_type: newPayment.payment_type,
        payment_date: newPayment.payment_date.split('T')[0],
        due_date: newPayment.due_date ? newPayment.due_date.split('T')[0] : '',
        status: newPayment.status,
        payment_method: newPayment.payment_method || '',
        description: newPayment.description || '',
      }
    }
  },
  { immediate: true },
)

watch(
  () => props.roomId,
  (newRoomId) => {
    if (newRoomId && !props.payment) {
      formData.value.room_id = newRoomId
    }
  },
  { immediate: true },
)

watch(
  [() => props.monthlyRent, () => props.paymentCycle, () => props.leaseStart, () => props.rentPayments],
  () => {
    if (!props.payment && is房租Type.value) {
      autoFillRent()
    }
  },
  { immediate: true, deep: true },
)

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate((valid) => {
    if (valid) {
      emit('submit', formData.value)
    } else {
      ElMessage.error('请先修正表单中的错误')
    }
  })
}

const handle取消 = () => {
  emit('cancel')
}

const resetForm = () => {
  formRef.value?.resetFields()
}
</script>

<template>
  <el-form
    ref="formRef"
    :model="formData"
    :rules="rules"
    label-width="140px"
    label-position="right"
  >
    <el-divider content-position="left">基础信息</el-divider>

    <el-form-item label="付款类型" prop="payment_type">
      <el-select
        v-model="formData.payment_type"
        placeholder="请选择付款类型"
        @change="autoFillRent"
      >
        <el-option label="房租" value="rent" />
        <el-option label="押金" value="deposit" />
        <el-option label="水电费" value="utility" />
        <el-option label="其他" value="other" />
      </el-select>
    </el-form-item>

    <el-form-item label="金额" prop="amount">
      <el-input-number
        v-model="formData.amount"
        :min="0"
        :precision="2"
        placeholder="请输入金额"
      />
      <span v-if="is房租Type && expectedRent > 0" class="form-tip">
        已自动填入：月租 {{ monthlyRent }} × {{ Math.max(1, Number(paymentCycle || 1)) }} 个月
      </span>
    </el-form-item>

    <el-form-item v-if="is房租Type" label="覆盖周期" required>
      <div style="display: flex; align-items: center; gap: 8px;">
        <el-date-picker
          v-model="formData.period_start"
          type="date"
          placeholder="起始日期"
          value-format="YYYY-MM-DD"
          style="width: 150px"
        />
        <span>至</span>
        <el-date-picker
          v-model="formData.period_end"
          type="date"
          placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 150px"
        />
      </div>
    </el-form-item>

    <el-form-item label="交租日期" prop="payment_date">
      <el-date-picker
        v-model="formData.payment_date"
        type="date"
        placeholder="请选择缴费日期"
        value-format="YYYY-MM-DD"
      />
    </el-form-item>

    <el-form-item label="应缴日期" prop="due_date">
      <el-date-picker
        v-model="formData.due_date"
        type="date"
        placeholder="请选择应缴日期"
        value-format="YYYY-MM-DD"
      />
    </el-form-item>

    <el-divider content-position="left">状态与支付方式</el-divider>

    <el-form-item label="状态" prop="status">
      <el-select v-model="formData.status" placeholder="请选择状态">
        <el-option label="待处理" value="pending" />
        <el-option label="已完成" value="completed" />
        <el-option label="逾期" value="overdue" />
        <el-option label="已取消" value="cancelled" />
      </el-select>
    </el-form-item>

    <el-form-item label="支付方式" prop="payment_method">
      <el-select v-model="formData.payment_method" placeholder="请选择支付方式" clearable>
        <el-option label="现金" value="cash" />
        <el-option label="银行转账" value="bank_transfer" />
        <el-option label="信用卡" value="credit_card" />
        <el-option label="微信支付" value="wechat_pay" />
        <el-option label="支付宝" value="alipay" />
        <el-option label="其他" value="other" />
      </el-select>
    </el-form-item>

    <el-divider content-position="left">补充信息</el-divider>

    <el-form-item label="备注" prop="description">
      <el-input
        v-model="formData.description"
        type="textarea"
        :rows="3"
        placeholder="请输入付款备注"
      />
    </el-form-item>

    <el-form-item>
      <el-button type="primary" :loading="loading" @click="handleSubmit">
        {{ payment ? '更新缴费' : '新增缴费' }}
      </el-button>
      <el-button @click="handle取消">取消</el-button>
      <el-button v-if="!payment" @click="resetForm">重置</el-button>
    </el-form-item>
  </el-form>
</template>

<style scoped>
.el-divider {
  margin: 20px 0;
}

.form-tip {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
}
</style>
