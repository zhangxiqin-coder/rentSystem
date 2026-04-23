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

const handleEdit = (room: Room) => {
  editingRoom.value = room
  dialogVisible.value = true
}

const handleDelete = async (room: Room) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete room ${room.room_number}?`,
      'Confirm Delete',
      {
        confirmButtonText: 'Delete',
        cancelButtonText: 'Cancel',
        type: 'warning',
      },
    )

    await roomApi.deleteRoom(room.id)
    ElMessage.success('Room deleted successfully')
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
    if (editingRoom.value) {
      await roomApi.updateRoom(editingRoom.value.id, data)
      ElMessage.success('Room updated successfully')
    } else {
      await roomApi.createRoom(data as CreateRoomRequest)
      ElMessage.success('Room created successfully')
    }
    dialogVisible.value = false
    await loadRooms()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || 'Failed to save room')
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
    available: 'Available',
    occupied: 'Occupied',
    maintenance: 'Maintenance',
  }
  return labels[status] || status
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
          <h2>Room Management</h2>
          <p>Manage your rental rooms and tenants</p>
        </div>
        <el-button type="primary" size="large" @click="handleCreate">
          <el-icon><Plus /></el-icon>
          Add Room
        </el-button>
      </div>
    </el-card>

    <el-card class="content-card">
      <!-- Filters -->
      <div class="filters">
        <el-input
          v-model="searchQuery"
          placeholder="Search by room number, building, or tenant..."
          clearable
          style="width: 300px"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <el-checkbox-group v-model="statusFilters">
          <el-checkbox label="available">Available</el-checkbox>
          <el-checkbox label="occupied">Occupied</el-checkbox>
          <el-checkbox label="maintenance">Maintenance</el-checkbox>
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
        <el-table-column prop="room_number" label="Room Number" width="120" />
        <el-table-column prop="building" label="Building" width="100" />
        <el-table-column prop="floor" label="Floor" width="80" />
        <el-table-column prop="area" label="Area (m²)" width="100" />
        <el-table-column prop="monthly_rent" label="Monthly Rent" width="120">
          <template #default="{ row }">
            ${{ row.monthly_rent?.toFixed(2) || '0.00' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="Status" width="120">
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
        <el-table-column label="Actions" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              @click.stop="handleEdit(row)"
            >
              Edit
            </el-button>
            <el-button
              type="danger"
              size="small"
              @click.stop="handleDelete(row)"
            >
              Delete
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
      :title="editingRoom ? 'Edit Room' : 'Create Room'"
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
