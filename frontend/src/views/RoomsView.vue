<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import type { Room } from '@/types'
import { roomApi } from '@/api/room'
import RoomForm from '@/components/RoomForm.vue'
import type { CreateRoomRequest, UpdateRoomRequest } from '@/types'
import { useAmountVisibility } from '@/composables/useAmountVisibility'

const router = useRouter()
const route = useRoute()
const { formatAmount } = useAmountVisibility()

const rooms = ref<Room[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const editingRoom = ref<Room>()
const searchQuery = ref('')

// Pagination
const currentPage = ref(1)
const pageSize = ref(5)
const total = ref(0)

// Status filters
const statusFilters = ref<string[]>([])

const filteredRooms = computed(() => {
  let result = rooms.value

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(
      (room) =>
        room.room_number.toLowerCase().includes(query) ||
        room.building?.toLowerCase().includes(query) ||
        room.tenant_name?.toLowerCase().includes(query),
    )
  }

  if (statusFilters.value.length > 0) {
    result = result.filter((room) => statusFilters.value.includes(room.status))
  }

  return result
})

const totalMonthlyRent = computed(() => {
  return rooms.value.reduce((sum, room) => sum + Number(room.monthly_rent || 0), 0)
})

const paginatedRooms = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredRooms.value.slice(start, end)
})

const loadRooms = async () => {
  loading.value = true
  try {
    const response = await roomApi.getRooms({
      page: currentPage.value,
      size: 100,
    })
    rooms.value = response.data.items
    total.value = response.data.total
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '加载房间失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  editingRoom.value = undefined
  dialogVisible.value = true
}

const handle编辑 = (room: Room) => {
  // Convert string numbers to actual numbers for form input
  editingRoom.value = {
    ...room,
    area: Number(room.area) || 0,
    monthly_rent: Number(room.monthly_rent) || 0,
    deposit_amount: Number(room.deposit_amount) || 0,
    floor: Number(room.floor) || 0,
    payment_cycle: Number(room.payment_cycle) || 1,
    water_rate: Number(room.water_rate) ?? 5,
    electricity_rate: Number(room.electricity_rate) ?? 1,
  }
  dialogVisible.value = true
}

const handle删除 = async (room: Room) => {
  try {
    await ElMessageBox.confirm(
      `确认要删除房间 ${room.room_number} 吗？`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )

    await roomApi.deleteRoom(room.id)
    ElMessage.success('房间删除成功')
    await loadRooms()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.message || '删除房间失败')
    }
  }
}

// 退租和入住功能
const checkoutDialogVisible = ref(false)
const checkinDialogVisible = ref(false)
const currentRoom = ref<Room>()

// 退租表单
const checkoutForm = ref({
  refund_amount: 0,
  refund_date: new Date().toISOString().split('T')[0],
  refund_reason: '',
  payment_method: '微信支付'
})

// 入住表单
const checkinForm = ref({
  tenant_name: '',
  tenant_phone: '',
  lease_start: '',
  lease_end: '',
  monthly_rent: 0,
  deposit_amount: 0,
  payment_cycle: 1
})

const handle退租 = (room: Room) => {
  currentRoom.value = room
  // 默认退款金额为押金
  checkoutForm.value.refund_amount = Number(room.deposit_amount) || 0
  checkoutDialogVisible.value = true
}

const handle入住 = (room: Room) => {
  currentRoom.value = room
  // 默认付款周期为1
  checkinForm.value.tenant_name = ''
  checkinForm.value.tenant_phone = ''
  checkinForm.value.lease_start = ''
  checkinForm.value.lease_end = ''
  checkinForm.value.payment_cycle = Number(room.payment_cycle) || 1
  checkinForm.value.monthly_rent = Number(room.monthly_rent) || 0
  checkinForm.value.deposit_amount = Number(room.deposit_amount) || 0
  checkinDialogVisible.value = true
}

const confirm退租 = async () => {
  if (!currentRoom.value) return
  
  try {
    submitting.value = true
    await roomApi.checkoutRoom(currentRoom.value.id, {
      refund_amount: checkoutForm.value.refund_amount,
      refund_date: checkoutForm.value.refund_date,
      refund_reason: checkoutForm.value.refund_reason,
      payment_method: checkoutForm.value.payment_method
    })
    ElMessage.success('退租成功')
    checkoutDialogVisible.value = false
    await loadRooms()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '退租失败')
  } finally {
    submitting.value = false
  }
}

const confirm入住 = async () => {
  if (!currentRoom.value) return

  try {
    submitting.value = true

    // 验证日期
    if (!checkinForm.value.lease_start || !checkinForm.value.lease_end) {
      ElMessage.error('请选择租约开始和结束日期')
      return
    }

    // Convert Date objects to YYYY-MM-DD format strings
    const formatDate = (date: Date | string): string => {
      if (!date) return ''
      const d = new Date(date)
      const year = d.getFullYear()
      const month = String(d.getMonth() + 1).padStart(2, '0')
      const day = String(d.getDate()).padStart(2, '0')
      return `${year}-${month}-${day}`
    }

    const startDateStr = formatDate(checkinForm.value.lease_start)
    const endDateStr = formatDate(checkinForm.value.lease_end)

    // 验证结束日期必须大于开始日期
    if (endDateStr <= startDateStr) {
      ElMessage.error('租约结束日期必须大于开始日期')
      return
    }

    const submitData = {
      ...checkinForm.value,
      tenant_name: checkinForm.value.tenant_name?.trim() || undefined,
      tenant_phone: checkinForm.value.tenant_phone?.trim() || undefined,
      monthly_rent: Number(checkinForm.value.monthly_rent) > 0 ? Number(checkinForm.value.monthly_rent) : undefined,
      lease_start: startDateStr,
      lease_end: endDateStr
    }
    
    console.log('📤 Checkin form data (raw):', JSON.stringify(checkinForm.value, null, 2))
    console.log('📤 Checkin submit data (formatted):', JSON.stringify(submitData, null, 2))
    
    await roomApi.checkinRoom(currentRoom.value.id, submitData)
    ElMessage.success('入住成功')
    checkinDialogVisible.value = false
    await loadRooms()
  } catch (error: any) {
    console.error('❌ Checkin error:', error)
    const errorData = error?.response?.data || error
    console.error('❌ Error data:', errorData)
    const validationMessage = Array.isArray(errorData?.errors) && errorData.errors.length > 0
      ? errorData.errors.map((e: any) => e?.msg || JSON.stringify(e)).join('；')
      : ''
    ElMessage.error(validationMessage || errorData?.detail || errorData?.message || '入住失败')
  } finally {
    submitting.value = false
  }
}

const handleSubmit = async (data: CreateRoomRequest | UpdateRoomRequest) => {
  submitting.value = true
  try {
    // Clean up empty strings to null for optional fields
    const cleanedData: any = { ...data }
    const optionalStringFields = ['tenant_name', 'tenant_phone', 'building', 'description']
    optionalStringFields.forEach(field => {
      if (cleanedData[field] === '') {
        cleanedData[field] = null
      }
    })

    console.log('📤 Submitting room data:', JSON.stringify(cleanedData, null, 2))

    if (editingRoom.value) {
      console.log('📝 Updating room ID:', editingRoom.value.id)
      // Remove room_number from update data as it's not allowed in RoomUpdate schema
      const { room_number, ...updateData } = cleanedData
      console.log('📝 Update data without room_number:', JSON.stringify(updateData, null, 2))
      await roomApi.updateRoom(editingRoom.value.id, updateData)
      ElMessage.success('房间更新成功')
    } else {
      await roomApi.createRoom(cleanedData as CreateRoomRequest)
      ElMessage.success('房间创建成功')
    }
    dialogVisible.value = false
    await loadRooms()
  } catch (error: any) {
    console.error('❌ Save error:', error)
    console.error('❌ Error response:', error.response)
    console.error('❌ Error data:', error.response?.data)
    ElMessage.error(error.response?.data?.detail || error.response?.data?.message || '保存房间失败')
  } finally {
    submitting.value = false
  }
}

const handleDialogClose = () => {
  dialogVisible.value = false
  editingRoom.value = undefined
}

const viewRoomDetail = (roomId: number) => {
  router.push(`/rooms/${roomId}`)
}

const getStatusType = (status: string) => {
  const types: Record<string, any> = {
    available: 'success',
    occupied: 'warning',
    maintenance: 'danger',
  }
  return types[status] || 'info'
}

const getStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    available: '空置',
    occupied: '已出租',
    maintenance: '维修中',
  }
  return labels[status] || status
}

const getPaymentCycleLabel = (cycle: number | null | undefined) => {
  if (!cycle) return '-'
  const cycleNum = Number(cycle)
  if (cycleNum === 1) return '1个月'
  if (cycleNum === 3) return '3个月（季付）'
  if (cycleNum === 6) return '6个月（半年）'
  if (cycleNum === 12) return '12个月（年付）'
  return `${cycleNum}个月`
}

onMounted(() => {
  const init = async () => {
    await loadRooms()

    // 支持从详情页跳转到 /rooms/:id/edit 并自动打开编辑弹窗
    if (route.path.endsWith('/edit')) {
      const id = Number(route.params.id)
      if (!Number.isNaN(id) && id > 0) {
        try {
          const response = await roomApi.getRoom(id)
          handle编辑(response.data)
        } catch (error: any) {
          ElMessage.error(error.response?.data?.detail || error.response?.data?.message || '加载房间失败')
        }
      }
    }
  }

  init()
})
</script>

<template>
  <div class="rooms-view">
    <el-card class="header-card">
      <div class="header-content">
        <div class="title-section">
          <h2>房间管理</h2>
          <p>管理您的租赁房间和租客 · 月租总计 <strong>{{ formatAmount(totalMonthlyRent) }}</strong></p>
        </div>
        <el-button type="primary" size="large" @click="handleCreate">
          <el-icon><Plus /></el-icon>
          添加房间
        </el-button>
      </div>
    </el-card>

    <el-card class="content-card">
      <!-- Filters -->
      <div class="filters">
        <el-input
          v-model="searchQuery"
          placeholder="按房间号、楼栋或租客搜索..."
          clearable
          style="width: 300px"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <el-checkbox-group v-model="statusFilters">
          <el-checkbox value="available">空置</el-checkbox>
          <el-checkbox value="occupied">已出租</el-checkbox>
          <el-checkbox value="maintenance">维修中</el-checkbox>
        </el-checkbox-group>
      </div>

      <!-- Loading State -->
      <div v-if="loading" v-loading="loading" class="loading-container"></div>

      <!-- Rooms Table -->
      <el-table
        v-else
        :data="paginatedRooms"
        stripe
        style="width: 100%"
        @row-click="(row: Room) => viewRoomDetail(row.id)"
      >
        <el-table-column prop="room_number" label="房间号" width="120" />
        <el-table-column prop="building" label="楼栋" width="100" />
        <el-table-column prop="tenant_name" label="租客" width="120">
          <template #default="{ row }">
            {{ row.tenant_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="lease_end" label="租约结束" width="120">
          <template #default="{ row }">
            {{ row.lease_end ? row.lease_end.split('T')[0] : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="monthly_rent" label="租金" width="120">
          <template #default="{ row }">
            {{ formatAmount(Number(row.monthly_rent || 0), '$') }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="water_rate" label="水费率 (元/吨)" width="120">
          <template #default="{ row }">
            {{ Number(row.water_rate ?? 5).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="electricity_rate" label="电费率 (元/度)" width="120">
          <template #default="{ row }">
            {{ Number(row.electricity_rate ?? 1).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="payment_cycle" label="付款周期" width="120">
          <template #default="{ row }">
            {{ getPaymentCycleLabel(row.payment_cycle) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <!-- 已租房间：显示退租按钮 -->
            <el-button
              v-if="row.status === 'occupied'"
              type="warning"
              size="small"
              @click.stop="handle退租(row)"
            >
              退租
            </el-button>
            <!-- 空房：显示入住按钮 -->
            <el-button
              v-if="row.status === 'available'"
              type="success"
              size="small"
              @click.stop="handle入住(row)"
            >
              入住
            </el-button>
            <el-button
              type="primary"
              size="small"
              @click.stop="handle编辑(row)"
            >
              编辑
            </el-button>
            <el-button
              type="danger"
              size="small"
              @click.stop="handle删除(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[5, 10, 20, 50, 100]"
          :total="filteredRooms.length"
          layout="total, sizes, prev, pager, next, jumper"
        />
      </div>
    </el-card>

    <!-- Room Form Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingRoom ? '编辑房间' : '创建房间'"
      width="600px"
      @close="handleDialogClose"
    >
      <RoomForm
        :room="editingRoom"
        :loading="submitting"
        @submit="handleSubmit"
        @cancel="handleDialogClose"
      />
    </el-dialog>

    <!-- 退租对话框 -->
    <el-dialog
      v-model="checkoutDialogVisible"
      title="退租"
      width="500px"
    >
      <el-form :model="checkoutForm" label-width="120px">
        <el-form-item label="房间">
          <span>{{ currentRoom?.room_number }}</span>
        </el-form-item>
        <el-form-item label="租客">
          <span>{{ currentRoom?.tenant_name }}</span>
        </el-form-item>
        <el-form-item label="押金">
          <span>{{ formatAmount(Number(currentRoom?.deposit_amount || 0)) }}</span>
        </el-form-item>
        <el-form-item label="退款金额" required>
          <el-input-number
            v-model="checkoutForm.refund_amount"
            :min="0"
            :precision="2"
            :step="100"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="退款日期">
          <el-date-picker
            v-model="checkoutForm.refund_date"
            type="date"
            placeholder="选择日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="退款原因">
          <el-input
            v-model="checkoutForm.refund_reason"
            type="textarea"
            :rows="3"
            placeholder="选填"
          />
        </el-form-item>
        <el-form-item label="支付方式">
          <el-select v-model="checkoutForm.payment_method" style="width: 100%">
            <el-option label="微信支付" value="微信支付" />
            <el-option label="支付宝" value="支付宝" />
            <el-option label="现金" value="现金" />
            <el-option label="银行转账" value="银行转账" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="checkoutDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="confirm退租">
          确认退租
        </el-button>
      </template>
    </el-dialog>

    <!-- 入住对话框 -->
    <el-dialog
      v-model="checkinDialogVisible"
      title="入住"
      width="500px"
    >
      <el-form :model="checkinForm" label-width="120px">
        <el-form-item label="房间">
          <span>{{ currentRoom?.room_number }}</span>
        </el-form-item>
        <el-form-item label="租客姓名">
          <el-input v-model="checkinForm.tenant_name" placeholder="可为空；为空时自动使用房间号" />
        </el-form-item>
        <el-form-item label="租客电话">
          <el-input v-model="checkinForm.tenant_phone" placeholder="可为空；填写时需为手机号" />
        </el-form-item>
        <el-form-item label="租约开始日期" required>
          <el-date-picker
            v-model="checkinForm.lease_start"
            type="date"
            placeholder="选择开始日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="租约结束日期" required>
          <el-date-picker
            v-model="checkinForm.lease_end"
            type="date"
            placeholder="选择结束日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="月租金">
          <el-input-number
            v-model="checkinForm.monthly_rent"
            :min="0"
            :precision="2"
            :step="100"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="押金">
          <el-input-number
            v-model="checkinForm.deposit_amount"
            :min="0"
            :precision="2"
            :step="100"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="付款周期（月）">
          <el-input-number
            v-model="checkinForm.payment_cycle"
            :min="1"
            :max="12"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="checkinDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="confirm入住">
          确认入住
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.rooms-view {
  padding: 20px;
  min-height: 100vh;
  background-color: #f5f7fa;
}

.header-card {
  margin-bottom: 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-section h2 {
  margin: 0 0 5px 0;
  color: #303133;
}

.title-section p {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.content-card {
  min-height: 600px;
}

.filters {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  align-items: center;
}

.loading-container {
  min-height: 400px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

:deep(.el-table__row) {
  cursor: pointer;
}

:deep(.el-table__row:hover) {
  background-color: #f5f7fa;
}
</style>
