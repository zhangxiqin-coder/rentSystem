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
  status: 'available',
  tenant_name: '',
  tenant_phone: '',
  lease_start: '',
  lease_end: '',
  description: '',
})

const rules: FormRules<CreateRoomRequest> = {
  room_number: [
    { required: true, message: 'Please enter room number', trigger: 'blur' },
  ],
  monthly_rent: [
    { required: true, message: 'Please enter monthly rent', trigger: 'blur' },
    { type: 'number', min: 0, message: 'Rent must be positive', trigger: 'blur' },
  ],
  payment_cycle: [
    { required: true, message: 'Please enter payment cycle', trigger: 'blur' },
    { type: 'number', min: 1, message: 'Payment cycle must be at least 1', trigger: 'blur' },
  ],
  status: [
    { required: true, message: 'Please select status', trigger: 'change' },
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
      ElMessage.error('Please fix the form errors')
    }
  })
}

const handleCancel = () => {
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
    <el-divider content-position="left">Basic Information</el-divider>

    <el-form-item label="Room Number" prop="room_number">
      <el-input v-model="formData.room_number" placeholder="e.g., A101" />
    </el-form-item>

    <el-form-item label="Building" prop="building">
      <el-input v-model="formData.building" placeholder="e.g., Building A" />
    </el-form-item>

    <el-form-item label="Floor" prop="floor">
      <el-input-number
        v-model="formData.floor"
        :min="1"
        :max="100"
        placeholder="Floor number"
      />
    </el-form-item>

    <el-form-item label="Area (sqm)" prop="area">
      <el-input-number
        v-model="formData.area"
        :min="1"
        :precision="2"
        placeholder="Room area"
      />
    </el-form-item>

    <el-divider content-position="left">Financial Information</el-divider>

    <el-form-item label="Monthly Rent" prop="monthly_rent">
      <el-input-number
        v-model="formData.monthly_rent"
        :min="0"
        :precision="2"
        placeholder="Monthly rent amount"
      />
    </el-form-item>

    <el-form-item label="Deposit Amount" prop="deposit_amount">
      <el-input-number
        v-model="formData.deposit_amount"
        :min="0"
        :precision="2"
        placeholder="Deposit amount"
      />
    </el-form-item>

    <el-form-item label="Payment Cycle" prop="payment_cycle">
      <el-select v-model="formData.payment_cycle" placeholder="Select payment cycle">
        <el-option label="Monthly" :value="1" />
        <el-option label="Quarterly" :value="3" />
        <el-option label="Semi-annually" :value="6" />
        <el-option label="Annually" :value="12" />
      </el-select>
    </el-form-item>

    <el-divider content-position="left">Status & Tenant</el-divider>

    <el-form-item label="Status" prop="status">
      <el-select v-model="formData.status" placeholder="Select status">
        <el-option label="Available" value="available" />
        <el-option label="Occupied" value="occupied" />
        <el-option label="Maintenance" value="maintenance" />
      </el-select>
    </el-form-item>

    <el-form-item label="Tenant Name" prop="tenant_name">
      <el-input v-model="formData.tenant_name" placeholder="Tenant name" />
    </el-form-item>

    <el-form-item label="Tenant Phone" prop="tenant_phone">
      <el-input v-model="formData.tenant_phone" placeholder="Tenant phone number" />
    </el-form-item>

    <el-form-item label="Lease Start" prop="lease_start">
      <el-date-picker
        v-model="formData.lease_start"
        type="date"
        placeholder="Select start date"
        value-format="YYYY-MM-DD"
      />
    </el-form-item>

    <el-form-item label="Lease End" prop="lease_end">
      <el-date-picker
        v-model="formData.lease_end"
        type="date"
        placeholder="Select end date"
        value-format="YYYY-MM-DD"
      />
    </el-form-item>

    <el-divider content-position="left">Additional Information</el-divider>

    <el-form-item label="Description" prop="description">
      <el-input
        v-model="formData.description"
        type="textarea"
        :rows="3"
        placeholder="Room description"
      />
    </el-form-item>

    <el-form-item>
      <el-button type="primary" :loading="loading" @click="handleSubmit">
        {{ room ? 'Update' : 'Create' }} Room
      </el-button>
      <el-button @click="handleCancel">Cancel</el-button>
      <el-button v-if="!room" @click="resetForm">Reset</el-button>
    </el-form-item>
  </el-form>
</template>

<style scoped>
.el-divider {
  margin: 20px 0;
}
</style>
