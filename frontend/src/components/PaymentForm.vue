<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import type { Payment, CreatePaymentRequest, UpdatePaymentRequest } from '@/types'

interface Props {
  payment?: Payment
  roomId?: number
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
        @change="() => { if (is房租Type) formData.amount = 0 }"
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
        :disabled="is房租Type"
        placeholder="请输入金额"
      />
      <span v-if="is房租Type" class="form-tip">
        金额将根据房间租金自动计算
      </span>
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
