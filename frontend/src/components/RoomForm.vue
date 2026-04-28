<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import type { Room, CreateRoomRequest, UpdateRoomRequest } from '@/types'

interface Props {
  room?: Room
  loading?: boolean
}

interface Emits {
  (e: 'submit', data: CreateRoomRequest | UpdateRoomRequest): void
  (e: 'cancel'): void
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
})

const emit = defineEmits<Emits>()

const formRef = ref<FormInstance>()
const formData = ref<CreateRoomRequest>({
  room_number: '',
  building: '',
  floor: undefined,
  area: undefined,
  monthly_rent: 0,
  deposit_amount: 0,
  payment_cycle: 1,
  water_rate: 5.00,
  electricity_rate: 1.00,
  status: 'available',
  tenant_name: '',
  tenant_phone: '',
  lease_start: '',
  lease_end: '',
  description: '',
})

const rules: FormRules<CreateRoomRequest> = {
  room_number: [
    { required: true, message: '请输入房间号', trigger: 'blur' },
  ],
  monthly_rent: [
    { required: true, message: '请输入租金', trigger: 'blur' },
    { type: 'number', min: 0, message: '租金必须大于等于0', trigger: 'blur' },
  ],
  payment_cycle: [
    { required: true, message: '请输入付款周期', trigger: 'blur' },
    { type: 'number', min: 1, message: '付款周期至少为1', trigger: 'blur' },
  ],
  status: [
    { required: true, message: '请选择状态', trigger: 'change' },
  ],
}

// Watch for room prop changes to populate form
watch(
  () => props.room,
  (newRoom) => {
    if (newRoom) {
      formData.value = {
        room_number: newRoom.room_number,
        building: newRoom.building || '',
        floor: newRoom.floor,
        area: newRoom.area,
        monthly_rent: newRoom.monthly_rent,
        deposit_amount: newRoom.deposit_amount || 0,
        payment_cycle: newRoom.payment_cycle,
        water_rate: newRoom.water_rate || 5.00,
        electricity_rate: newRoom.electricity_rate || 1.00,
        status: newRoom.status,
        tenant_name: newRoom.tenant_name || '',
        tenant_phone: newRoom.tenant_phone || '',
        lease_start: newRoom.lease_start || '',
        lease_end: newRoom.lease_end || '',
        description: newRoom.description || '',
      }
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

    <el-form-item label="房间号" prop="room_number">
      <el-input v-model="formData.room_number" placeholder="例如：A101" />
    </el-form-item>

    <el-form-item label="楼栋" prop="building">
      <el-input v-model="formData.building" placeholder="例如：A栋" />
    </el-form-item>

    <el-form-item label="楼层" prop="floor">
      <el-input-number
        v-model="formData.floor"
        :min="1"
        :max="100"
        placeholder="请输入楼层"
      />
    </el-form-item>

    <el-form-item label="面积（㎡）" prop="area">
      <el-input-number
        v-model="formData.area"
        :min="1"
        :precision="2"
        placeholder="请输入面积"
      />
    </el-form-item>

    <el-divider content-position="left">费用信息</el-divider>

    <el-form-item label="租金" prop="monthly_rent">
      <el-input-number
        v-model="formData.monthly_rent"
        :min="0"
        :precision="2"
        placeholder="请输入租金"
      />
    </el-form-item>

    <el-form-item label="押金" prop="deposit_amount">
      <el-input-number
        v-model="formData.deposit_amount"
        :min="0"
        :precision="2"
        placeholder="请输入押金"
      />
    </el-form-item>

    <el-form-item label="付款周期" prop="payment_cycle">
      <el-select v-model="formData.payment_cycle" placeholder="请选择付款周期">
        <el-option label="月付" :value="1" />
        <el-option label="季付" :value="3" />
        <el-option label="半年付" :value="6" />
        <el-option label="年付" :value="12" />
      </el-select>
    </el-form-item>

    <el-divider content-position="left">水电费率</el-divider>

    <el-form-item label="水费率 (元/吨)" prop="water_rate">
      <el-input-number
        v-model="formData.water_rate"
        :min="0"
        :precision="2"
        :step="0.5"
        placeholder="默认5元/吨"
      />
      <span style="margin-left: 10px; color: #909399;">默认 5.00 元/吨</span>
    </el-form-item>

    <el-form-item label="电费率 (元/度)" prop="electricity_rate">
      <el-input-number
        v-model="formData.electricity_rate"
        :min="0"
        :precision="2"
        :step="0.1"
        placeholder="默认1元/度"
      />
      <span style="margin-left: 10px; color: #909399;">默认 1.00 元/度</span>
    </el-form-item>

    <el-divider content-position="left">状态与租客</el-divider>

    <el-form-item label="状态" prop="status">
      <el-select v-model="formData.status" placeholder="请选择状态">
        <el-option label="空置" value="available" />
        <el-option label="已出租" value="occupied" />
        <el-option label="维修中" value="maintenance" />
      </el-select>
    </el-form-item>

    <el-form-item label="租客姓名" prop="tenant_name">
      <el-input v-model="formData.tenant_name" placeholder="租客姓名" />
    </el-form-item>

    <el-form-item label="租客电话" prop="tenant_phone">
      <el-input v-model="formData.tenant_phone" placeholder="租客电话" />
    </el-form-item>

    <el-form-item label="租约开始" prop="lease_start">
      <el-date-picker
        v-model="formData.lease_start"
        type="date"
        placeholder="请选择开始日期"
        value-format="YYYY-MM-DD"
      />
    </el-form-item>

    <el-form-item label="租约结束" prop="lease_end">
      <el-date-picker
        v-model="formData.lease_end"
        type="date"
        placeholder="请选择结束日期"
        value-format="YYYY-MM-DD"
      />
    </el-form-item>

    <el-divider content-position="left">补充信息</el-divider>

    <el-form-item label="描述" prop="description">
      <el-input
        v-model="formData.description"
        type="textarea"
        :rows="3"
        placeholder="请输入房间描述"
      />
    </el-form-item>

    <el-form-item>
      <el-button type="primary" :loading="loading" @click="handleSubmit">
        {{ room ? '更新房间' : '创建房间' }}
      </el-button>
      <el-button @click="handle取消">取消</el-button>
      <el-button v-if="!room" @click="resetForm">重置</el-button>
    </el-form-item>
  </el-form>
</template>

<style scoped>
.el-divider {
  margin: 20px 0;
}
</style>
