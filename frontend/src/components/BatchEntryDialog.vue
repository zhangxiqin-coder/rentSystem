<script setup lang="ts">
import type { Room } from '@/types'

defineProps<{
  modelValue: boolean
  allRooms: Room[]
  batchForm: { reading_date: string; utility_type: string; notes: string }
  batchLoading: boolean
  selectedRooms: number[]
  hideAmounts: boolean
  maskedRate: (value: number | string | null | undefined, unit: string) => string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'submit': []
  'select-all': []
  'clear': []
  'select-occupied': []
}>()
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="批量录入水电读数"
    width="800px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form :model="batchForm" label-width="100px">
      <el-form-item label="抄表日期">
        <el-date-picker
          v-model="batchForm.reading_date"
          type="date"
          placeholder="选择日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
        />
      </el-form-item>

      <el-form-item label="水电类型">
        <el-radio-group v-model="batchForm.utility_type">
          <el-radio label="water">仅水费</el-radio>
          <el-radio label="electricity">仅电费</el-radio>
          <el-radio label="both">水电全录</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-divider content-position="left">选择房间并录入读数</el-divider>

      <el-form-item>
        <el-button @click="emit('select-all')" size="small">全选</el-button>
        <el-button @click="emit('clear')" size="small">清空</el-button>
        <el-button @click="emit('select-occupied')" size="small" type="primary">仅选已租</el-button>
      </el-form-item>

      <div class="batch-room-list">
        <el-checkbox-group :model-value="selectedRooms">
          <div
            v-for="room in allRooms"
            :key="room.id"
            class="batch-room-item"
            :class="{ 'selected': selectedRooms.includes(room.id) }"
          >
            <el-checkbox :label="room.id" :model-value="selectedRooms.includes(room.id)" @change="() => {}">
              <span class="room-number">{{ room.room_number }}</span>
              <el-tag size="small" :type="room.status === 'occupied' ? 'success' : 'info'">
                {{ room.status === 'occupied' ? '已租' : '空置' }}
              </el-tag>
              <span class="room-rent">{{ hideAmounts ? '****/月' : `¥${room.monthly_rent || 0}/月` }}</span>
            </el-checkbox>

            <!-- 选中时显示读数输入框 -->
            <div v-if="selectedRooms.includes(room.id)" class="room-readings">
              <div v-if="batchForm.utility_type === 'water' || batchForm.utility_type === 'both'" class="reading-input">
                <span class="label">💧 水表读数:</span>
                <el-input-number
                  v-model="room.water_reading"
                  :min="0"
                  :precision="1"
                  :step="0.1"
                  size="small"
                />
                <span class="rate">费率: {{ maskedRate(room.water_rate || 0, '吨') }}</span>
              </div>
              <div v-if="batchForm.utility_type === 'electricity' || batchForm.utility_type === 'both'" class="reading-input">
                <span class="label">⚡ 电表读数:</span>
                <el-input-number
                  v-model="room.electricity_reading"
                  :min="0"
                  :precision="1"
                  :step="1"
                  size="small"
                />
                <span class="rate">费率: {{ maskedRate(room.electricity_rate || 0, '度') }}</span>
              </div>
            </div>
          </div>
        </el-checkbox-group>
      </div>

      <el-form-item label="统一备注">
        <el-input
          v-model="batchForm.notes"
          type="textarea"
          :rows="2"
          placeholder="可选：填写备注（将应用到所有记录）"
        />
      </el-form-item>

      <div class="batch-summary" v-if="selectedRooms.length > 0">
        <div>已选择: <strong>{{ selectedRooms.length }}</strong> 个房间</div>
        <div>预计录入: <strong>{{ batchForm.utility_type === 'both' ? selectedRooms.length * 2 : selectedRooms.length }}</strong> 条记录</div>
      </div>
    </el-form>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click="emit('update:modelValue', false)">取消</el-button>
        <el-button type="primary" @click="emit('submit')" :loading="batchLoading" :disabled="selectedRooms.length === 0">
          批量录入 ({{ selectedRooms.length }}个房间)
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<style scoped>
.batch-room-list {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 12px;
  background: #f5f7fa;
}

.batch-room-item {
  padding: 12px;
  margin-bottom: 8px;
  background: white;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
  transition: all 0.3s;
}

.batch-room-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.1);
}

.batch-room-item.selected {
  border-color: #409eff;
  background: #ecf5ff;
}

.batch-room-item .room-number {
  font-weight: 600;
  margin-right: 8px;
  font-size: 16px;
}

.batch-room-item .room-rent {
  margin-left: 8px;
  color: #909399;
  font-size: 14px;
}

.room-readings {
  margin-top: 12px;
  padding: 8px;
  background: #f9fafc;
  border-radius: 4px;
}

.reading-input {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.reading-input:last-child {
  margin-bottom: 0;
}

.reading-input .label {
  min-width: 80px;
  font-weight: 500;
  color: #606266;
}

.reading-input .rate {
  margin-left: auto;
  color: #909399;
  font-size: 12px;
}

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
</style>
