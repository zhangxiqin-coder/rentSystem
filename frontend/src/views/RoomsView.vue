<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Room } from '@/types'
import { roomApi } from '@/api/room'
import RoomForm from '@/components/RoomForm.vue'
import type { CreateRoomRequest, UpdateRoomRequest } from '@/types'

const router = useRouter()

const rooms = ref<Room[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const editingRoom = ref<Room>()
const searchQuery = ref('')

// Pagination
const currentPage = ref(1)
const pageSize = ref(10)
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
    ElMessage.error(error.response?.data?.message || 'Failed to load rooms')
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
    water_rate: Number(room.water_rate) || 5,
    electricity_rate: Number(room.electricity_rate) || 1,
  }
  dialogVisible.value = true
}

const handle删除 = async (room: Room) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete room ${room.room_number}?`,
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
      ElMessage.error(error.response?.data?.message || 'Failed to delete room')
    }
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
    ElMessage.error(error.response?.data?.detail || error.response?.data?.message || 'Failed to save room')
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
  loadRooms()
})
</script>

<template>
  <div class="rooms-view">
    <el-card class="header-card">
      <div class="header-content">
        <div class="title-section">
          <h2>房间管理</h2>
          <p>管理您的租赁房间和租客</p>
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
          <el-checkbox label="available">空置</el-checkbox>
          <el-checkbox label="occupied">已出租</el-checkbox>
          <el-checkbox label="maintenance">维修中</el-checkbox>
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
        <el-table-column prop="monthly_rent" label="Monthly Rent" width="120">
          <template #default="{ row }">
            ${{ Number(row.monthly_rent || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="tenant_name" label="Tenant" width="120">
          <template #default="{ row }">
            {{ row.tenant_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="lease_end" label="Lease End" width="120">
          <template #default="{ row }">
            {{ row.lease_end ? row.lease_end.split('T')[0] : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="water_rate" label="水费率 (元/吨)" width="120">
          <template #default="{ row }">
            {{ Number(row.water_rate || 5).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="electricity_rate" label="电费率 (元/度)" width="120">
          <template #default="{ row }">
            {{ Number(row.electricity_rate || 1).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="payment_cycle" label="付款周期" width="120">
          <template #default="{ row }">
            {{ getPaymentCycleLabel(row.payment_cycle) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
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
          :page-sizes="[10, 20, 50, 100]"
          :total="filteredRooms.length"
          layout="total, sizes, prev, pager, next, jumper"
        />
      </div>
    </el-card>

    <!-- Room Form Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingRoom ? '编辑 Room' : 'Create Room'"
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
