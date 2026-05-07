<script setup lang="ts">
defineProps<{
  modelValue: boolean
  editForm: {
    water_reading_id: number | null
    electricity_reading_id: number | null
    water_reading: number
    electricity_reading: number
    notes: string
  }
  editLoading: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'submit': []
}>()
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="编辑水电记录"
    width="600px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form label-width="120px">
      <el-alert
        title="编辑提示"
        type="info"
        :closable="false"
        style="margin-bottom: 20px"
      >
        修改读数会自动重新计算用量和费用
      </el-alert>

      <template v-if="editForm.water_reading_id !== null">
        <el-divider content-position="left">💧 水表</el-divider>
        <el-form-item label="水表读数（吨）">
          <el-input-number
            v-model="editForm.water_reading"
            :min="0"
            :precision="1"
            :step="1"
            style="width: 200px"
          />
        </el-form-item>
      </template>

      <template v-if="editForm.electricity_reading_id !== null">
        <el-divider content-position="left">⚡ 电表</el-divider>
        <el-form-item label="电表读数（度）">
          <el-input-number
            v-model="editForm.electricity_reading"
            :min="0"
            :precision="0"
            :step="1"
            style="width: 200px"
          />
        </el-form-item>
      </template>

      <el-divider content-position="left">📝 备注</el-divider>
      <el-form-item label="备注">
        <el-input
          v-model="editForm.notes"
          type="textarea"
          :rows="3"
          placeholder="请输入备注信息"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="editLoading" @click="emit('submit')">
        保存
      </el-button>
    </template>
  </el-dialog>
</template>
