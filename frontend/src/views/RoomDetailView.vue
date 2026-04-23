<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Room, Payment, UtilityReading } from '@/types'
import { roomApi } from '@/api/room'
import { paymentApi } from '@/api/payment'
import { utilityApi } from '@/api/utility'
import PaymentForm from '@/components/PaymentForm.vue'
import UtilityReadingForm from '@/components/UtilityReadingForm.vue'

const router = useRouter()
const route = useRoute()

const roomId = computed(() => Number(route.params.id))
const room = ref<Room>()
const loading = ref(false)

// Payments
const payments = ref<Payment[]>([])
const paymentsLoading = ref(false)
const paymentDialogVisible = ref(false)
const paymentSubmitting = ref(false)
const editingPayment = ref<Payment>()

// Utility Readings
const utilityReadings = ref<UtilityReading[]>([])
const utilityLoading = ref(false)
const utilityDialogVisible = ref(false)
const utilitySubmitting = ref(false)
const editingUtilityReading = ref<UtilityReading>()

// Tabs
const activeTab = ref('details')

const loadRoom = async () => {
  loading.value = true
  try {
    const response = await roomApi.getRoom(roomId.value)
    room.value = response.data.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || 'Failed to load room')
    router.push('/rooms')
  } finally {
    loading.value = false
  }
}

const loadPayments = async () => {
  paymentsLoading.value = true
  try {
    const response = await paymentApi.getPaymentsByRoom(roomId.value, {
      page: 1,
      size: 50,
    })
    payments.value = response.data.items
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || 'Failed to load payments')
  } finally {
    paymentsLoading.value = false
  }
}

const loadUtilityReadings = async () => {
  utilityLoading.value = true
  try {
    const response = await utilityApi.getReadingsByRoom(roomId.value, {
      page: 1,
      size: 50,
    })
    utilityReadings.value = response.data.items
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || 'Failed to load utility readings')
  } finally {
    utilityLoading.value = false
  }
}

const handleCreatePayment = () => {
  editingPayment.value = undefined
  paymentDialogVisible.value = true
}

const handleEditPayment = (payment: Payment) => {
  editingPayment.value = payment
  paymentDialogVisible.value = true
}

const handleDeletePayment = async (payment: Payment) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete this payment?`,
      'Confirm Delete',
      {
        confirmButtonText: 'Delete',
        cancelButtonText: 'Cancel',
        type: 'warning',
      },
    )

    await paymentApi.deletePayment(payment.id)
    ElMessage.success('Payment deleted successfully')
    await loadPayments()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.message || 'Failed to delete payment')
    }
  }
}

const handleSubmitPayment = async (data: any) => {
  paymentSubmitting.value = true
  try {
    if (editingPayment.value) {
      await paymentApi.updatePayment(editingPayment.value.id, data)
      ElMessage.success('Payment updated successfully')
    } else {
      await paymentApi.createPayment({ ...data, room_id: roomId.value })
      ElMessage.success('Payment created successfully')
    }
    paymentDialogVisible.value = false
    await loadPayments()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || 'Failed to save payment')
  } finally {
    paymentSubmitting.value = false
  }
}

const handleCreateUtilityReading = () => {
  editingUtilityReading.value = undefined
  utilityDialogVisible.value = true
}

const handleEditUtilityReading = (reading: UtilityReading) => {
  editingUtilityReading.value = reading
  utilityDialogVisible.value = true
}

const handleDeleteUtilityReading = async (reading: UtilityReading) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete this reading?`,
      'Confirm Delete',
      {
        confirmButtonText: 'Delete',
        cancelButtonText: 'Cancel',
        type: 'warning',
      },
    )

    await utilityApi.deleteReading(reading.id)
    ElMessage.success('Reading deleted successfully')
    await loadUtilityReadings()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.message || 'Failed to delete reading')
    }
  }
}

const handleSubmitUtilityReading = async (data: any) => {
  utilitySubmitting.value = true
  try {
    if (editingUtilityReading.value) {
      await utilityApi.updateReading(editingUtilityReading.value.id, data)
      ElMessage.success('Reading updated successfully')
    } else {
      await utilityApi.createReading({ ...data, room_id: roomId.value })
      ElMessage.success('Reading created successfully')
    }
    utilityDialogVisible.value = false
    await loadUtilityReadings()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || 'Failed to save reading')
  } finally {
    utilitySubmitting.value = false
  }
}

const getStatusType = (status: string) => {
  const types: Record<string, any> = {
    pending: 'warning',
    completed: 'success',
    overdue: 'danger',
    cancelled: 'info',
  }
  return types[status] || 'info'
}

const getPaymentTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    rent: 'Rent',
    deposit: 'Deposit',
    utility: 'Utility',
    other: 'Other',
  }
  return labels[type] || type
}

const getUtilityTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    water: 'Water',
    electricity: 'Electricity',
    gas: 'Gas',
  }
  return labels[type] || type
}

onMounted(async () => {
  await loadRoom()
  if (room.value) {
    await loadPayments()
    await loadUtilityReadings()
  }
})
</script>

<template>
  <div class="room-detail-view" v-loading="loading">
    <el-page-header @back="router.back()" class="page-header">
      <template #content>
        <span class="title">{{ room?.room_number }} - Room Details</span>
      </template>
      <template #extra>
        <el-button type="primary" @click="() => router.push(`/rooms/${roomId}/edit`)">
          Edit Room
        </el-button>
      </template>
    </el-page-header>

    <el-tabs v-model="activeTab" class="room-tabs">
      <!-- Details Tab -->
      <el-tab-pane label="Details" name="details">
        <el-card>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="Room Number">
              {{ room?.room_number }}
            </el-descriptions-item>
            <el-descriptions-item label="Building">
              {{ room?.building || 'N/A' }}
            </el-descriptions-item>
            <el-descriptions-item label="Floor">
              {{ room?.floor || 'N/A' }}
            </el-descriptions-item>
            <el-descriptions-item label="Area">
              {{ room?.area || 'N/A' }} m²
            </el-descriptions-item>
            <el-descriptions-item label="Monthly Rent">
              ${{ room?.monthly_rent?.toFixed(2) || '0.00' }}
            </el-descriptions-item>
            <el-descriptions-item label="Deposit">
              ${{ room?.deposit_amount?.toFixed(2) || '0.00' }}
            </el-descriptions-item>
            <el-descriptions-item label="Payment Cycle">
              {{ room?.payment_cycle || 1 }} month(s)
            </el-descriptions-item>
            <el-descriptions-item label="Status">
              <el-tag :type="room?.status === 'available' ? 'success' : room?.status === 'occupied' ? 'warning' : 'danger'">
                {{ room?.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Tenant Name">
              {{ room?.tenant_name || 'N/A' }}
            </el-descriptions-item>
            <el-descriptions-item label="Tenant Phone">
              {{ room?.tenant_phone || 'N/A' }}
            </el-descriptions-item>
            <el-descriptions-item label="Lease Start">
              {{ room?.lease_start ? room.lease_start.split('T')[0] : 'N/A' }}
            </el-descriptions-item>
            <el-descriptions-item label="Lease End">
              {{ room?.lease_end ? room.lease_end.split('T')[0] : 'N/A' }}
            </el-descriptions-item>
            <el-descriptions-item label="Description" :span="2">
              {{ room?.description || 'N/A' }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-tab-pane>

      <!-- Payments Tab -->
      <el-tab-pane label="Payments" name="payments">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>Payment Records</span>
              <el-button type="primary" @click="handleCreatePayment">
                Add Payment
              </el-button>
            </div>
          </template>

          <el-table :data="payments" v-loading="paymentsLoading" stripe>
            <el-table-column prop="payment_date" label="Date" width="120">
              <template #default="{ row }">
                {{ row.payment_date.split('T')[0] }}
              </template>
            </el-table-column>
            <el-table-column prop="payment_type" label="Type" width="100">
              <template #default="{ row }">
                {{ getPaymentTypeLabel(row.payment_type) }}
              </template>
            </el-table-column>
            <el-table-column prop="amount" label="Amount" width="120">
              <template #default="{ row }">
                ${{ row.amount.toFixed(2) }}
              </template>
            </el-table-column>
            <el-table-column prop="status" label="Status" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="payment_method" label="Method" width="120">
              <template #default="{ row }">
                {{ row.payment_method || 'N/A' }}
              </template>
            </el-table-column>
            <el-table-column prop="description" label="Description" show-overflow-tooltip />
            <el-table-column label="Actions" width="180">
              <template #default="{ row }">
                <el-button size="small" @click="handleEditPayment(row)">
                  Edit
                </el-button>
                <el-button
                  type="danger"
                  size="small"
                  @click="handleDeletePayment(row)"
                >
                  Delete
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- Utility Readings Tab -->
      <el-tab-pane label="Utility Readings" name="utility">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>Utility Readings</span>
              <el-button type="primary" @click="handleCreateUtilityReading">
                Add Reading
              </el-button>
            </div>
          </template>

          <el-table :data="utilityReadings" v-loading="utilityLoading" stripe>
            <el-table-column prop="reading_date" label="Date" width="120">
              <template #default="{ row }">
                {{ row.reading_date.split('T')[0] }}
              </template>
            </el-table-column>
            <el-table-column prop="utility_type" label="Type" width="100">
              <template #default="{ row }">
                {{ getUtilityTypeLabel(row.utility_type) }}
              </template>
            </el-table-column>
            <el-table-column prop="reading" label="Reading" width="120" />
            <el-table-column prop="previous_reading" label="Previous" width="120">
              <template #default="{ row }">
                {{ row.previous_reading || 'N/A' }}
              </template>
            </el-table-column>
            <el-table-column prop="usage" label="Usage" width="100" />
            <el-table-column prop="amount" label="Amount" width="120">
              <template #default="{ row }">
                ${{ row.amount?.toFixed(2) || '0.00' }}
              </template>
            </el-table-column>
            <el-table-column prop="notes" label="Notes" show-overflow-tooltip />
            <el-table-column label="Actions" width="180">
              <template #default="{ row }">
                <el-button size="small" @click="handleEditUtilityReading(row)">
                  Edit
                </el-button>
                <el-button
                  type="danger"
                  size="small"
                  @click="handleDeleteUtilityReading(row)"
                >
                  Delete
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- Payment Form Dialog -->
    <el-dialog
      v-model="paymentDialogVisible"
      :title="editingPayment ? 'Edit Payment' : 'Create Payment'"
      width="600px"
    >
      <PaymentForm
        :payment="editingPayment"
        :room-id="roomId"
        :loading="paymentSubmitting"
        @submit="handleSubmitPayment"
        @cancel="paymentDialogVisible = false"
      />
    </el-dialog>

    <!-- Utility Reading Form Dialog -->
    <el-dialog
      v-model="utilityDialogVisible"
      :title="editingUtilityReading ? 'Edit Reading' : 'Record Reading'"
      width="600px"
    >
      <UtilityReadingForm
        :reading="editingUtilityReading"
        :room-id="roomId"
        :loading="utilitySubmitting"
        @submit="handleSubmitUtilityReading"
        @cancel="utilityDialogVisible = false"
      />
    </el-dialog>
  </div>
</template>

<style scoped>
.room-detail-view {
  padding: 20px;
  min-height: 100vh;
  background-color: #f5f7fa;
}

.page-header {
  margin-bottom: 20px;
}

.title {
  font-size: 20px;
  font-weight: 500;
}

.room-tabs {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
