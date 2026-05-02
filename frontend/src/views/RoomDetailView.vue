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
  if (!Number.isFinite(roomId.value) || roomId.value <= 0) {
    ElMessage.error('房间ID无效')
    router.push('/rooms')
    return
  }

  loading.value = true
  try {
    const response = await roomApi.getRoom(roomId.value)
    room.value = response.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || error.response?.data?.message || '加载房间失败')
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
    ElMessage.error(error.response?.data?.message || '加载缴费记录失败')
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
    ElMessage.error(error.response?.data?.message || '加载水电记录失败')
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
      `确认要删除这条缴费记录吗？`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )

    await paymentApi.deletePayment(payment.id)
    ElMessage.success('缴费记录删除成功')
    await loadPayments()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.message || '删除缴费记录失败')
    }
  }
}

const handleSubmitPayment = async (data: any) => {
  paymentSubmitting.value = true
  try {
    if (editingPayment.value) {
      await paymentApi.updatePayment(editingPayment.value.id, data)
      ElMessage.success('缴费记录更新成功')
    } else {
      await paymentApi.createPayment({ ...data, room_id: roomId.value })
      ElMessage.success('缴费记录创建成功')
    }
    paymentDialogVisible.value = false
    await loadPayments()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '保存缴费记录失败')
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
      `确认要删除这条抄表记录吗？`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )

    await utilityApi.deleteReading(reading.id)
    ElMessage.success('抄表记录删除成功')
    await loadUtilityReadings()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.message || '删除抄表记录失败')
    }
  }
}

const handleSubmitUtilityReading = async (data: any) => {
  utilitySubmitting.value = true
  try {
    if (editingUtilityReading.value) {
      await utilityApi.updateReading(editingUtilityReading.value.id, data)
      ElMessage.success('抄表记录更新成功')
    } else {
      await utilityApi.createReading({ ...data, room_id: roomId.value })
      ElMessage.success('抄表记录创建成功')
    }
    utilityDialogVisible.value = false
    await loadUtilityReadings()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '保存抄表记录失败')
  } finally {
    utilitySubmitting.value = false
  }
}

const get状态Type = (status: string) => {
  const types: Record<string, any> = {
    pending: 'warning',
    completed: 'success',
    overdue: 'danger',
    cancelled: 'info',
  }
  return types[status] || 'info'
}

const get状态Label = (status: string) => {
  const labels: Record<string, string> = {
    available: '空置',
    occupied: '已出租',
    maintenance: '维修中',
    pending: '待处理',
    completed: '已完成',
    overdue: '逾期',
    cancelled: '已取消',
  }
  return labels[status] || status
}

const getPaymentTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    rent: '房租',
    deposit: '押金',
    utility: '水电费',
    other: '其他',
  }
  return labels[type] || type
}

const getUtilityTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    water: '水',
    electricity: '电',
    gas: '燃气',
  }
  return labels[type] || type
}

const getPaymentMethodLabel = (method?: string | null) => {
  const labels: Record<string, string> = {
    cash: '现金',
    bank_transfer: '银行转账',
    credit_card: '信用卡',
    wechat_pay: '微信支付',
    alipay: '支付宝',
    other: '其他',
  }
  if (!method) return '-'
  return labels[method] || method
}

const getPaymentCycleLabel = (cycle: number | null | undefined) => {
  if (!cycle) return '1个月'
  const cycleNum = Number(cycle)
  if (cycleNum === 1) return '1个月'
  if (cycleNum === 3) return '3个月（季付）'
  if (cycleNum === 6) return '6个月（半年）'
  if (cycleNum === 12) return '12个月（年付）'
  return `${cycleNum}个月`
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
        <span class="title">{{ room?.room_number }}（编号：{{ room?.id ?? roomId }}）- 房间详情</span>
      </template>
      <template #extra>
        <el-button type="primary" @click="() => router.push(`/rooms/${roomId}/edit`)">
          编辑房间
        </el-button>
      </template>
    </el-page-header>

    <el-tabs v-model="activeTab" class="room-tabs">
      <!-- Details Tab -->
      <el-tab-pane label="基本信息" name="details">
        <el-card>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="房间号">
              {{ room?.room_number }}
            </el-descriptions-item>
            <el-descriptions-item label="楼栋">
              {{ room?.building || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="楼层">
              {{ room?.floor || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="面积">
              {{ room?.area || '-' }} ㎡
            </el-descriptions-item>
            <el-descriptions-item label="月租金">
              ${{ Number(room?.monthly_rent || 0).toFixed(2) }}
            </el-descriptions-item>
            <el-descriptions-item label="押金">
              ${{ Number(room?.deposit_amount || 0).toFixed(2) }}
            </el-descriptions-item>
            <el-descriptions-item label="付款周期">
              {{ getPaymentCycleLabel(room?.payment_cycle) }}
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="room?.status === 'available' ? 'success' : room?.status === 'occupied' ? 'warning' : 'danger'">
                {{ get状态Label(room?.status || '') }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="租客姓名">
              {{ room?.tenant_name || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="租客电话">
              {{ room?.tenant_phone || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="租期开始">
              {{ room?.lease_start ? room.lease_start.split('T')[0] : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="租期结束">
              {{ room?.lease_end ? room.lease_end.split('T')[0] : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="描述" :span="2">
              {{ room?.description || '-' }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-tab-pane>

      <!-- Payments Tab -->
      <el-tab-pane label="缴费记录" name="payments">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>缴费记录</span>
              <el-button type="primary" @click="handleCreatePayment">
                新增缴费
              </el-button>
            </div>
          </template>

          <el-table :data="payments" v-loading="paymentsLoading" stripe>
            <el-table-column prop="payment_date" label="日期" width="120">
              <template #default="{ row }">
                {{ row.payment_date.split('T')[0] }}
              </template>
            </el-table-column>
            <el-table-column prop="payment_type" label="类型" width="100">
              <template #default="{ row }">
                {{ getPaymentTypeLabel(row.payment_type) }}
              </template>
            </el-table-column>
            <el-table-column prop="amount" label="金额" width="120">
              <template #default="{ row }">
                ${{ Number(row.amount || 0).toFixed(2) }}
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="get状态Type(row.status)">
                  {{ get状态Label(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="payment_method" label="支付方式" width="120">
              <template #default="{ row }">
                {{ getPaymentMethodLabel(row.payment_method) }}
              </template>
            </el-table-column>
            <el-table-column prop="description" label="备注" show-overflow-tooltip />
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-button size="small" @click="handleEditPayment(row)">
                  编辑
                </el-button>
                <el-button
                  type="danger"
                  size="small"
                  @click="handleDeletePayment(row)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- Utility Readings Tab -->
      <el-tab-pane label="水电抄表" name="utility">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>水电抄表</span>
              <el-button type="primary" @click="handleCreateUtilityReading">
                新增抄表
              </el-button>
            </div>
          </template>

          <el-table :data="utilityReadings" v-loading="utilityLoading" stripe>
            <el-table-column prop="reading_date" label="日期" width="120">
              <template #default="{ row }">
                {{ row.reading_date.split('T')[0] }}
              </template>
            </el-table-column>
            <el-table-column prop="utility_type" label="类型" width="100">
              <template #default="{ row }">
                {{ getUtilityTypeLabel(row.utility_type) }}
              </template>
            </el-table-column>
            <el-table-column prop="reading" label="本次读数" width="120" />
            <el-table-column prop="previous_reading" label="上次读数" width="120">
              <template #default="{ row }">
                {{ row.previous_reading || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="usage" label="用量" width="100" />
            <el-table-column prop="amount" label="金额" width="120">
              <template #default="{ row }">
                ${{ Number(row.amount || 0).toFixed(2) }}
              </template>
            </el-table-column>
            <el-table-column prop="notes" label="备注" show-overflow-tooltip />
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-button size="small" @click="handleEditUtilityReading(row)">
                  编辑
                </el-button>
                <el-button
                  type="danger"
                  size="small"
                  @click="handleDeleteUtilityReading(row)"
                >
                  删除
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
      :title="editingPayment ? '编辑缴费' : '新增缴费'"
      width="600px"
    >
      <PaymentForm
        :payment="editingPayment"
        :room-id="roomId"
        :monthly-rent="room?.monthly_rent"
        :payment-cycle="room?.payment_cycle"
        :lease-start="room?.lease_start"
        :loading="paymentSubmitting"
        @submit="handleSubmitPayment"
        @cancel="paymentDialogVisible = false"
      />
    </el-dialog>

    <!-- Utility Reading Form Dialog -->
    <el-dialog
      v-model="utilityDialogVisible"
      :title="editingUtilityReading ? '编辑抄表' : '新增抄表'"
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
