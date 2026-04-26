<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { roomApi } from '@/api/room'
import { utilityApi } from '@/api/utility'
import type { Room } from '@/types'

const props = defineProps<{
  roomId?: number
}>()

const emit = defineEmits<{
  success: [result: any]
  cancel: []
}>()

// 表单数据
const formData = ref({
  room_id: props.roomId || 0,
  reading_date: new Date().toISOString().split('T')[0],
  water_reading: 0,
  electric_reading: 0,
  manual_previous_water: null as number | null,
  manual_previous_electric: null as number | null,
  use_manual_water: false,
  use_manual_electric: false,
  notes: '',
})

// 加载状态
const loading = ref(false)
const roomsLoading = ref(false)
const loadingHistory = ref(false)

// 数据
const rooms = ref<Room[]>([])
const previousReadings = ref<{
  water: number | null
  electric: number | null
}>({
  water: null,
  electric: null,
})

// 当前选中房间
const selectedRoom = computed(() => {
  if (!formData.value.room_id) return null
  return rooms.value.find(r => r.id === formData.value.room_id) || null
})

// 检查房间是否支持水电费率（2501系列房间费率可为0或None）
const isZeroRateRoom = computed(() => {
  const room = selectedRoom.value
  if (!room) return false
  const waterRate = room.water_rate === null || room.water_rate === 0
  const electricRate = room.electricity_rate === null || room.electricity_rate === 0
  return waterRate || electricRate
})

// 计算结果
const calculations = ref<{
  water: { usage: number; amount: number; rate: number } | null
  electric: { usage: number; amount: number; rate: number } | null
}>({
  water: null,
  electric: null,
})

// 计算下次付款天数
const getNextPaymentDays = (room: Room): number => {
  if (!room.last_payment_date && !room.lease_start) return 999

  const lastPayment = room.last_payment_date
    ? new Date(room.last_payment_date)
    : room.lease_start ? new Date(room.lease_start) : new Date()

  // 使用租约开始日的日期作为付款日
  const paymentDay = room.lease_start ? new Date(room.lease_start).getDate() : 1
  const now = new Date()
  const currentMonth = now.getMonth()
  const currentYear = now.getFullYear()

  // 计算本月付款日期
  let nextPayment = new Date(currentYear, currentMonth, paymentDay)

  // 如果本月付款日期已过，则使用下个月
  if (nextPayment <= lastPayment) {
    nextPayment = new Date(currentYear, currentMonth + 1, paymentDay)
  }

  // 如果计算出的付款日期还在今天之前，说明是下个月的
  if (nextPayment < now) {
    nextPayment = new Date(currentYear, currentMonth + 1, paymentDay)
  }

  const diffTime = nextPayment.getTime() - now.getTime()
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
  return diffDays
}

// 检查房间本月是否已有水电记录
const hasThisMonthReading = async (roomId: number): Promise<boolean> => {
  try {
    const now = new Date()
    const year = now.getFullYear()
    const month = now.getMonth() + 1
    const monthStart = `${year}-${String(month).padStart(2, '0')}-01`
    const monthEnd = `${year}-${String(month).padStart(2, '0')}-31`

    // 检查水和电是否都有本月记录
    const [waterRes, electricRes] = await Promise.allSettled([
      utilityApi.getReadingsByRoom(roomId, { page: 1, size: 1, utility_type: 'water', start_date: monthStart, end_date: monthEnd }),
      utilityApi.getReadingsByRoom(roomId, { page: 1, size: 1, utility_type: 'electricity', start_date: monthStart, end_date: monthEnd })
    ])

    // 如果水和电都有记录，说明本月已录入
    const hasWater = waterRes.status === 'fulfilled' && waterRes.value.data.items.length > 0
    const hasElectric = electricRes.status === 'fulfilled' && electricRes.value.data.items.length > 0

    return hasWater || hasElectric // 至少有其一就算已录入
  } catch {
    return false
  }
}

// 房间本月是否已有记录的缓存
const roomReadingStatus = ref<Record<number, boolean>>({})

// 房间列表（按房号字母序排序）
const activeRooms = computed(() => {
  // 所有房间都是活跃的（软删除的房间不会从API返回）
  const active = rooms.value

  // 按房号字母序排序
  return active.sort((a, b) => {
    const numA = a.room_number
    const numB = b.room_number
    return numA.localeCompare(numB, 'zh-CN')
  })
})

// 总费用
const totalAmount = computed(() => {
  let total = 0
  if (calculations.value.water) total += calculations.value.water.amount
  if (calculations.value.electric) total += calculations.value.electric.amount
  return total.toFixed(2)
})

// 显示的上次水表读数（优先使用手动输入，否则使用历史记录）
const displayedPreviousWater = computed(() => {
  if (formData.value.use_manual_water) {
    return formData.value.manual_previous_water
  }
  return previousReadings.value.water
})

// 显示的上次电表读数（优先使用手动输入，否则使用历史记录）
const displayedPreviousElectric = computed(() => {
  if (formData.value.use_manual_electric) {
    return formData.value.manual_previous_electric
  }
  return previousReadings.value.electric
})

// 加载房间列表
const loadRooms = async () => {
  roomsLoading.value = true
  try {
    // 后端API限制size最大为100，需要分页加载
    let allRooms: Room[] = []
    let page = 1
    let hasMore = true

    while (hasMore) {
      const res = await roomApi.getRooms({ page, size: 100 })
      const items = res.data.items || []
      allRooms = [...allRooms, ...items]

      // 如果返回的数据少于100条，说明没有更多数据了
      hasMore = items.length === 100
      page++
    }

    rooms.value = allRooms

    // 检查每个房间本月是否已有水电记录
    const statusPromises = allRooms.map(async (room) => {
      const hasReading = await hasThisMonthReading(room.id)
      return { roomId: room.id, hasReading }
    })

    const statuses = await Promise.all(statusPromises)
    roomReadingStatus.value = Object.fromEntries(
      statuses.map(s => [s.roomId, s.hasReading])
    )
  } catch (error) {
    console.error('Failed to load rooms:', error)
    ElMessage.error('加载房间列表失败')
  } finally {
    roomsLoading.value = false
  }
}

// 加载上次读数
const loadPreviousReadings = async (roomId: number) => {
  if (!roomId) return

  loadingHistory.value = true
  try {
    // 分别获取水和电的最后一条记录
    const [waterRes, electricRes] = await Promise.allSettled([
      utilityApi.getReadingsByRoom(roomId, { page: 1, size: 1, utility_type: 'water' }),
      utilityApi.getReadingsByRoom(roomId, { page: 1, size: 1, utility_type: 'electricity' }),
    ])

    if (waterRes.status === 'fulfilled' && waterRes.value.data.items.length > 0) {
      const lastWater = waterRes.value.data.items[0]
      previousReadings.value.water = lastWater.reading
    } else {
      previousReadings.value.water = null
    }

    if (electricRes.status === 'fulfilled' && electricRes.value.data.items.length > 0) {
      const lastElectric = electricRes.value.data.items[0]
      previousReadings.value.electric = lastElectric.reading
    } else {
      previousReadings.value.electric = null
    }

    // 触发计算
    calculateCosts()
  } catch (error) {
    console.error('Failed to load previous readings:', error)
  } finally {
    loadingHistory.value = false
  }
}

// 实时计算用量和费用
const calculateCosts = () => {
  const roomId = formData.value.room_id
  if (!roomId) return

  const room = selectedRoom.value
  if (!room) return

  // 水费计算
  const prevWater = displayedPreviousWater.value
  if (prevWater !== null && formData.value.water_reading >= 0) {
    const usage = formData.value.water_reading - prevWater
    // 优先使用房间费率，如果费率为0或null（2501系列房间），则使用0
    // 只有当费率为null且不是0费率房间时，才使用默认费率
    const rate = room.water_rate !== null && room.water_rate !== undefined
      ? Number(room.water_rate)
      : (isZeroRateRoom.value ? 0 : 5) // 默认5元/吨
    calculations.value.water = {
      usage: Math.max(0, usage),
      amount: Math.max(0, usage) * rate,
      rate,
    }
  } else {
    calculations.value.water = null
  }

  // 电费计算
  const prevElectric = displayedPreviousElectric.value
  if (prevElectric !== null && formData.value.electric_reading >= 0) {
    const usage = formData.value.electric_reading - prevElectric
    // 优先使用房间费率，如果费率为0或null（2501系列房间），则使用0
    // 只有当费率为null且不是0费率房间时，才使用默认费率
    const rate = room.electricity_rate !== null && room.electricity_rate !== undefined
      ? Number(room.electricity_rate)
      : (isZeroRateRoom.value ? 0 : 1) // 默认1元/度
    calculations.value.electric = {
      usage: Math.max(0, usage),
      amount: Math.max(0, usage) * rate,
      rate,
    }
  } else {
    calculations.value.electric = null
  }
}

// 提交表单
const submitForm = async () => {
  // 验证必填字段
  if (!formData.value.room_id) {
    ElMessage.error('请选择房间')
    return
  }
  if (!formData.value.reading_date) {
    ElMessage.error('请选择抄表日期')
    return
  }

  // 2501系列房间（费率为0或null）不需要验证水电表，直接创建0读数记录
  // 其他房间至少需要录入水表或电表读数
  if (!isZeroRateRoom.value) {
    if (formData.value.water_reading === 0 && formData.value.electric_reading === 0) {
      ElMessage.error('请至少录入水表或电表读数')
      return
    }
  }

  // 2501系列房间跳过水电表读数验证
  if (!isZeroRateRoom.value) {
    // 验证水表读数
    const prevWater = displayedPreviousWater.value
    if (prevWater !== null && formData.value.water_reading > 0) {
      if (formData.value.water_reading < prevWater) {
        ElMessage.error('水表读数不能小于上次读数')
        return
      }
    }

    // 验证电表读数
    const prevElectric = displayedPreviousElectric.value
    if (prevElectric !== null && formData.value.electric_reading > 0) {
      if (formData.value.electric_reading < prevElectric) {
        ElMessage.error('电表读数不能小于上次读数')
        return
      }
    }
  }

  loading.value = true
  try {
    // 顺序创建水和电的记录，确保第二次录入时能触发催收消息
    const results: any[] = []

    // 2501系列房间：总是创建0读数记录（用于记录房租）
    // 其他房间：只有读数>0时才创建记录
    if (isZeroRateRoom.value) {
      // 2501系列房间，创建水和电的0读数记录
      results.push(await utilityApi.createReading({
          room_id: formData.value.room_id,
          utility_type: 'water',
          reading: 0,
          reading_date: formData.value.reading_date,
          previous_reading: 0,
          notes: formData.value.notes || '2501系列房间，无水电费',
        }),
      )
      results.push(await utilityApi.createReading({
        room_id: formData.value.room_id,
        utility_type: 'electricity',
        reading: 0,
        reading_date: formData.value.reading_date,
        previous_reading: 0,
        notes: formData.value.notes || '2501系列房间，无水电费',
      }),)
    } else {
      // 其他房间，按读数创建记录
      if (formData.value.water_reading > 0) {
        results.push(await utilityApi.createReading({
          room_id: formData.value.room_id,
          utility_type: 'water',
          reading: formData.value.water_reading,
          reading_date: formData.value.reading_date,
          previous_reading: displayedPreviousWater.value || undefined,
          notes: formData.value.notes,
        }),)
      }

      if (formData.value.electric_reading > 0) {
        results.push(await utilityApi.createReading({
          room_id: formData.value.room_id,
          utility_type: 'electricity',
          reading: formData.value.electric_reading,
          reading_date: formData.value.reading_date,
          previous_reading: displayedPreviousElectric.value || undefined,
          notes: formData.value.notes,
        }),)
      }
    }

    ElMessage.success('水电录入成功')

    // 更新该房间的录入状态
    roomReadingStatus.value[formData.value.room_id] = true

    // 返回创建的记录信息，以便父组件发送微信通知
    const result = {
      room_id: formData.value.room_id,
      reading_date: formData.value.reading_date,
      water_reading: formData.value.water_reading,
      electric_reading: formData.value.electric_reading,
      notes: formData.value.notes,
    }
    emit('success', result)
  } catch (error: any) {
    console.error('Failed to create utility readings:', error)
    const errorMsg = error.response?.data?.detail || '录入失败，请重试'
    ElMessage.error(errorMsg)
  } finally {
    loading.value = false
  }
}

// 重置表单
const resetForm = () => {
  formData.value = {
    room_id: props.roomId || 0,
    reading_date: new Date().toISOString().split('T')[0],
    water_reading: 0,
    electric_reading: 0,
    manual_previous_water: null,
    manual_previous_electric: null,
    use_manual_water: false,
    use_manual_electric: false,
    notes: '',
  }
  previousReadings.value = {
    water: null,
    electric: null,
  }
  calculations.value = {
    water: null,
    electric: null,
  }
}

// 取消
const handleCancel = () => {
  resetForm()
  emit('cancel')
}

// 监听房间变化，自动加载历史记录
watch(
  () => formData.value.room_id,
  (newRoomId) => {
    if (newRoomId) {
      loadPreviousReadings(newRoomId)
    } else {
      previousReadings.value = { water: null, electric: null }
      calculations.value = { water: null, electric: null }
    }
  }
)

// 监听手动输入模式切换，重置计算
watch(
  () => [formData.value.use_manual_water, formData.value.use_manual_electric],
  () => {
    calculateCosts()
  }
)

// 监听props.roomId变化，自动设置room_id并加载历史记录
watch(
  () => props.roomId,
  (newRoomId) => {
    if (newRoomId) {
      formData.value.room_id = newRoomId
      loadPreviousReadings(newRoomId)
    }
  },
  { immediate: true } // 立即执行一次
)

// 初始化 - 始终加载rooms数据
loadRooms()
</script>

<template>
  <div class="utility-reading-form">
    <el-form :model="formData" label-width="140px" @submit.prevent="submitForm">
      <!-- 房间选择 -->
      <el-form-item label="选择房间" required>
        <div v-if="props.roomId" style="padding: 8px 12px; background: #f5f7fa; border-radius: 4px; color: #606266; font-weight: 500;">
          {{ rooms.find(r => r.id === props.roomId)?.room_number || '加载中...' }} - {{ rooms.find(r => r.id === props.roomId)?.tenant_name || '空房' }}
        </div>
        <el-select
          v-else
          v-model="formData.room_id"
          placeholder="请选择房间（支持输入搜索）"
          filterable
          :disabled="!!props.roomId"
          :loading="roomsLoading"
          style="width: 100%"
          @change="loadPreviousReadings"
        >
          <el-option
            v-for="room in activeRooms"
            :key="room.id"
            :value="room.id"
            :label="`${room.room_number} - ${room.tenant_name || '空房'}`"
          >
            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
              <span>{{ room.room_number }} - {{ room.tenant_name || '空房' }}</span>
              <span
                v-if="roomReadingStatus[room.id]"
                style="color: #909399; font-size: 12px;"
              >
                本月已录入
              </span>
              <span
                v-else-if="getNextPaymentDays(room) <= 7"
                style="color: #f56c6c; font-size: 12px; font-weight: bold;"
              >
                {{ getNextPaymentDays(room) <= 0 ? '已逾期' : `${getNextPaymentDays(room)}天后到期` }}
              </span>
            </div>
          </el-option>
        </el-select>
        <div v-if="formData.room_id && !props.roomId" class="room-hint">
          <span
            v-if="roomReadingStatus[formData.room_id]"
            style="color: #909399;"
          >
            ℹ️ 该房间本月已录入过水电记录
          </span>
          <span
            v-else-if="getNextPaymentDays(activeRooms.find(r => r.id === formData.room_id)!) <= 7"
            style="color: #f56c6c;"
          >
            ⚠️ {{ getNextPaymentDays(activeRooms.find(r => r.id === formData.room_id)!) <= 0 ? '该房间已逾期' : `该房间${getNextPaymentDays(activeRooms.find(r => r.id === formData.room_id)!)}天后到期` }}
          </span>
        </div>
      </el-form-item>

      <!-- 抄表日期 -->
      <el-form-item label="抄表日期" required>
        <el-date-picker
          v-model="formData.reading_date"
          type="date"
          placeholder="选择日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          style="width: 100%"
        />
      </el-form-item>

      <!-- 水表读数 -->
      <el-divider content-position="left">💧 水表录入</el-divider>

      <el-form-item label="上次读数来源">
        <el-radio-group v-model="formData.use_manual_water">
          <el-radio :label="false">自动查找历史记录</el-radio>
          <el-radio :label="true">手动输入</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item v-if="!formData.use_manual_water" label="上次水表读数">
        <el-input 
          :value="previousReadings.water !== null ? previousReadings.water : '无历史记录'" 
          disabled
          placeholder="加载中..."
        >
          <template #append>吨</template>
        </el-input>
        <div v-if="previousReadings.water !== null" class="history-hint">
          ✓ 已从历史记录自动加载
        </div>
      </el-form-item>

      <el-form-item v-else label="上次水表读数" required>
        <el-input-number
          v-model="formData.manual_previous_water"
          :min="0"
          :precision="2"
          :step="0.01"
          style="width: 100%"
          controls-position="right"
          placeholder="请输入上次读数"
          @change="calculateCosts"
        />
        <template #append>吨</template>
        <div class="manual-hint">
          ℹ️ 请手动输入上次水表读数
        </div>
      </el-form-item>

      <el-form-item label="本次水表读数" required>
        <el-input-number
          v-model="formData.water_reading"
          :min="0"
          :precision="2"
          :step="0.01"
          style="width: 100%"
          controls-position="right"
          placeholder="请输入本次读数"
          @change="calculateCosts"
        />
      </el-form-item>

      <el-form-item v-if="calculations.water" label="水费计算">
        <div class="calculation-result">
          <span>用量：{{ calculations.water.usage.toFixed(2) }} 吨</span>
          <span>费率：¥{{ calculations.water.rate }}/吨</span>
          <span class="amount">费用：¥{{ calculations.water.amount.toFixed(2) }}</span>
        </div>
      </el-form-item>

      <!-- 电表读数 -->
      <el-divider content-position="left">⚡ 电表录入</el-divider>

      <el-form-item label="上次读数来源">
        <el-radio-group v-model="formData.use_manual_electric">
          <el-radio :label="false">自动查找历史记录</el-radio>
          <el-radio :label="true">手动输入</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item v-if="!formData.use_manual_electric" label="上次电表读数">
        <el-input 
          :value="previousReadings.electric !== null ? previousReadings.electric : '无历史记录'" 
          disabled
          placeholder="加载中..."
        >
          <template #append>度</template>
        </el-input>
        <div v-if="previousReadings.electric !== null" class="history-hint">
          ✓ 已从历史记录自动加载
        </div>
      </el-form-item>

      <el-form-item v-else label="上次电表读数" required>
        <el-input-number
          v-model="formData.manual_previous_electric"
          :min="0"
          :precision="2"
          :step="1"
          style="width: 100%"
          controls-position="right"
          placeholder="请输入上次读数"
          @change="calculateCosts"
        />
        <template #append>度</template>
        <div class="manual-hint">
          ℹ️ 请手动输入上次电表读数
        </div>
      </el-form-item>

      <el-form-item label="本次电表读数" required>
        <el-input-number
          v-model="formData.electric_reading"
          :min="0"
          :precision="2"
          :step="1"
          style="width: 100%"
          controls-position="right"
          placeholder="请输入本次读数"
          @change="calculateCosts"
        />
      </el-form-item>

      <el-form-item v-if="calculations.electric" label="电费计算">
        <div class="calculation-result">
          <span>用量：{{ calculations.electric.usage.toFixed(2) }} 度</span>
          <span>费率：¥{{ calculations.electric.rate }}/度</span>
          <span class="amount">费用：¥{{ calculations.electric.amount.toFixed(2) }}</span>
        </div>
      </el-form-item>

      <!-- 总费用 -->
      <el-divider content-position="left">💰 费用汇总</el-divider>

      <el-form-item label="总费用">
        <div class="total-amount">¥{{ totalAmount }}</div>
      </el-form-item>

      <!-- 备注 -->
      <el-form-item label="备注">
        <el-input
          v-model="formData.notes"
          type="textarea"
          :rows="3"
          placeholder="请输入备注信息（可选）"
        />
      </el-form-item>

      <!-- 操作按钮 -->
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="submitForm">
          保存记录
        </el-button>
        <el-button @click="handleCancel">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.utility-reading-form {
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.calculation-result {
  display: flex;
  gap: 1rem;
  padding: 0.75rem;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 0.9rem;
}

.calculation-result .amount {
  margin-left: auto;
  font-weight: bold;
  color: #e74c3c;
}

.total-amount {
  font-size: 1.5rem;
  font-weight: bold;
  color: #e74c3c;
}

.history-hint {
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: #67c23a;
}

.manual-hint {
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: #909399;
}

.room-hint {
  margin-top: 0.5rem;
  font-size: 0.9rem;
  font-weight: 500;
}
</style>
