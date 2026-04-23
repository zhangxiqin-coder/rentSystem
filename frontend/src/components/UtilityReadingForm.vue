<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import type {
  UtilityReading,
  CreateUtilityReadingRequest,
  UpdateUtilityReadingRequest,
} from '@/types'

interface Props {
  reading?: UtilityReading
  roomId?: number
  previousReading?: number
  loading?: boolean
}

interface Emits {
  (e: 'submit', data: CreateUtilityReadingRequest | UpdateUtilityReadingRequest): void
  (e: 'cancel'): void
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
})

const emit = defineEmits<Emits>()

const formRef = ref<FormInstance>()
const formData = ref<CreateUtilityReadingRequest>({
  room_id: props.roomId || 0,
  utility_type: 'electricity',
  reading: 0,
  reading_date: new Date().toISOString().split('T')[0],
  notes: '',
})

const rules: FormRules<CreateUtilityReadingRequest> = {
  room_id: [
    { required: true, message: 'Room is required', trigger: 'blur' },
  ],
  utility_type: [
    { required: true, message: 'Please select utility type', trigger: 'change' },
  ],
  reading: [
    { required: true, message: 'Please enter reading value', trigger: 'blur' },
    { type: 'number', min: 0, message: 'Reading must be non-negative', trigger: 'blur' },
  ],
  reading_date: [
    { required: true, message: 'Please select reading date', trigger: 'change' },
  ],
}

const estimatedUsage = computed(() => {
  if (props.previousReading !== undefined && formData.value.reading >= props.previousReading) {
    return formData.value.reading - props.previousReading
  }
  return 0
})

const utilityTypeLabel = computed(() => {
  const labels: Record<string, string> = {
    water: 'm³',
    electricity: 'kWh',
    gas: 'm³',
  }
  return labels[formData.value.utility_type] || 'units'
})

// Watch for reading prop changes to populate form
watch(
  () => props.reading,
  (newReading) => {
    if (newReading) {
      formData.value = {
        room_id: newReading.room_id,
        utility_type: newReading.utility_type,
        reading: newReading.reading,
        reading_date: newReading.reading_date.split('T')[0],
        notes: newReading.notes || '',
      }
    }
  },
  { immediate: true },
)

watch(
  () => props.roomId,
  (newRoomId) => {
    if (newRoomId && !props.reading) {
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
    label-width="160px"
    label-position="right"
  >
    <el-divider content-position="left">Reading Information</el-divider>

    <el-form-item label="Utility Type" prop="utility_type">
      <el-select v-model="formData.utility_type" placeholder="Select utility type">
        <el-option label="Water" value="water" />
        <el-option label="Electricity" value="electricity" />
        <el-option label="Gas" value="gas" />
      </el-select>
    </el-form-item>

    <el-form-item label="Current Reading" prop="reading">
      <el-input-number
        v-model="formData.reading"
        :min="0"
        :precision="2"
        placeholder="Enter current reading"
      />
      <span class="unit-label">{{ utilityTypeLabel }}</span>
    </el-form-item>

    <el-form-item v-if="previousReading !== undefined" label="Previous Reading">
      <el-input :value="previousReading" disabled />
      <span class="unit-label">{{ utilityTypeLabel }}</span>
    </el-form-item>

    <el-form-item v-if="previousReading !== undefined" label="Usage">
      <el-input :value="estimatedUsage" disabled />
      <span class="unit-label">{{ utilityTypeLabel }}</span>
    </el-form-item>

    <el-form-item label="Reading Date" prop="reading_date">
      <el-date-picker
        v-model="formData.reading_date"
        type="date"
        placeholder="Select reading date"
        value-format="YYYY-MM-DD"
      />
    </el-form-item>

    <el-divider content-position="left">Additional Information</el-divider>

    <el-form-item label="Notes" prop="notes">
      <el-input
        v-model="formData.notes"
        type="textarea"
        :rows="3"
        placeholder="Additional notes or observations"
      />
    </el-form-item>

    <el-form-item>
      <el-button type="primary" :loading="loading" @click="handleSubmit">
        {{ reading ? 'Update' : 'Record' }} Reading
      </el-button>
      <el-button @click="handleCancel">Cancel</el-button>
      <el-button v-if="!reading" @click="resetForm">Reset</el-button>
    </el-form-item>
  </el-form>
</template>

<style scoped>
.el-divider {
  margin: 20px 0;
}

.unit-label {
  margin-left: 10px;
  color: #909399;
  font-size: 13px;
}
</style>
