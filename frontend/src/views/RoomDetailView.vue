<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Room, Payment, UtilityReading, RoomOccupant, Tenant } from '@/types'
import { roomApi } from '@/api/room'
import { paymentApi } from '@/api/payment'
import { utilityApi } from '@/api/utility'
import { roomOccupantsApi } from '@/api/roomOccupants'
import { tenantsApi } from '@/api/tenants'
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

// Date Range Filter (默认最近2个月)
const dateRange = ref<[Date, Date]>([
  new Date(Date.now() - 60 * 24 * 60 * 60 * 1000), // 2个月前
  new Date()
])

// 续租相关
const renewDialogVisible = ref(false)
const renewSubmitting = ref(false)
const renewForm = ref({
  months: 12,
  monthly_rent: null as number | null,
  notes: ''
})

// ===== 居住人（多租客）=====
const occupants = ref<RoomOccupant[]>([])
const occupantsLoading = ref(false)
const occupantDialogVisible = ref(false)
const occupantSubmitting = ref(false)
const occupantEditMode = ref<'add' | 'edit'>('add')
const editingOccupant = ref<RoomOccupant | null>(null)
const occupantForm = ref({
  tenant_id: undefined as number | undefined,
  role: 'secondary' as 'primary' | 'secondary',
  relation: '',
  is_active: true
})
// 可选的租客列表（排除已在房间的）
const availableTenants = ref<Tenant[]>([])
const tenantsLoading = ref(false)

const loadOccupants = async () => {
  if (!room.value) return
  occupantsLoading.value = true
  try {
    occupants.value = await roomOccupantsApi.listByRoom(roomId.value)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载居住人列表失败')
  } finally {
    occupantsLoading.value = false
  }
}

const loadAvailableTenants = async () => {
  tenantsLoading.value = true
  try {
    // 查全部active租客（不传status=active，因为后端会进一步过滤"有活跃租约"的，
    // 新建的租客可能还没租约，需要在添加居住人时也能看到）
    const all = await tenantsApi.list({})
    // 只排除已搬离的，排除已在居住人列表中的租客
    const existingIds = new Set(occupants.value.map(o => o.tenant_id))
    availableTenants.value = all.filter(t => !existingIds.has(t.id) && t.status !== 'inactive')
  } catch (error) {
    console.error('获取租客列表失败:', error)
  } finally {
    tenantsLoading.value = false
  }
}

const openAddOccupantDialog = () => {
  occupantEditMode.value = 'add'
  editingOccupant.value = null
  occupantForm.value = {
    tenant_id: undefined,
    role: 'secondary',
    relation: '',
    is_active: true
  }
  loadAvailableTenants()
  occupantDialogVisible.value = true
}

const openEditOccupantDialog = (occ: RoomOccupant) => {
  occupantEditMode.value = 'edit'
  editingOccupant.value = occ
  occupantForm.value = {
    tenant_id: occ.tenant_id,
    role: occ.role,
    relation: occ.relation || '',
    is_active: occ.is_active
  }
  occupantDialogVisible.value = true
}

const handleSubmitOccupant = async () => {
  if (!occupantForm.value.tenant_id) {
    ElMessage.warning('请选择租客')
    return
  }
  occupantSubmitting.value = true
  try {
    const data = {
      tenant_id: occupantForm.value.tenant_id,
      role: occupantForm.value.role,
      relation: occupantForm.value.relation || undefined,
      is_active: occupantForm.value.is_active
    }
    if (occupantEditMode.value === 'add') {
      await roomOccupantsApi.add(roomId.value, data)
      ElMessage.success('添加居住人成功')
    } else if (editingOccupant.value) {
      await roomOccupantsApi.update(editingOccupant.value.id, {
        role: data.role,
        relation: data.relation,
        is_active: data.is_active
      })
      ElMessage.success('更新居住人成功')
    }
    occupantDialogVisible.value = false
    await loadOccupants()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally {
    occupantSubmitting.value = false
  }
}

const handleRemoveOccupant = async (occ: RoomOccupant) => {
  try {
    await ElMessageBox.confirm(
      `确定要将「${occ.tenant_name}」从居住人列表中移除吗？（不会删除该租客本身）`,
      '移除确认',
      { confirmButtonText: '移除', cancelButtonText: '取消', type: 'warning' }
    )
    await roomOccupantsApi.remove(occ.id)
    ElMessage.success('移除成功')
    await loadOccupants()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '移除失败')
    }
  }
}

const handleSetPrimary = async (occ: RoomOccupant) => {
  try {
    await roomOccupantsApi.update(occ.id, { role: 'primary' })
    ElMessage.success(`已将「${occ.tenant_name}」设为主租客`)
    await loadOccupants()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '设置失败')
  }
}

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
    // 格式化日期为 YYYY-MM-DD
    const formatDate = (date: Date) => {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      return `${year}-${month}-${day}`
    }

    const response = await paymentApi.getPaymentsByRoom(roomId.value, {
      page: 1,
      size: 50,
      start_date: formatDate(dateRange.value[0]),
      end_date: formatDate(dateRange.value[1])
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
    // 格式化日期为 YYYY-MM-DD
    const formatDate = (date: Date) => {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      return `${year}-${month}-${day}`
    }

    const response = await utilityApi.getReadingsByRoom(roomId.value, {
      page: 1,
      size: 50,
      start_date: formatDate(dateRange.value[0]),
      end_date: formatDate(dateRange.value[1])
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

// 续租相关函数
const handleRenewLease = () => {
  // 重置表单，默认续租12个月
  renewForm.value = {
    months: 12,
    monthly_rent: null,
    notes: ''
  }
  renewDialogVisible.value = true
}

const handleSubmitRenewLease = async () => {
  if (!room.value) return
  
  renewSubmitting.value = true
  try {
    const response = await roomApi.renewLease(roomId.value, {
      months: renewForm.value.months,
      monthly_rent: renewForm.value.monthly_rent || undefined,
      notes: renewForm.value.notes || undefined
    })
    
    ElMessage.success(response.data.message || '续租成功')
    renewDialogVisible.value = false
    await loadRoom() // 重新加载房间信息
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || error.response?.data?.message || '续租失败')
  } finally {
    renewSubmitting.value = false
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

const handleDateRangeChange = () => {
  loadPayments()
  loadUtilityReadings()
}

onMounted(async () => {
  await loadRoom()
  if (room.value) {
    await loadPayments()
    await loadUtilityReadings()
    await loadOccupants()
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
              <div style="display: flex; align-items: center; gap: 8px;">
                {{ room?.lease_end ? room.lease_end.split('T')[0] : '-' }}
                <el-button
                  v-if="room?.status === 'occupied' && room?.lease_end"
                  type="primary"
                  size="small"
                  @click="handleRenewLease"
                >
                  续租
                </el-button>
              </div>
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
              <div style="display: flex; gap: 12px; align-items: center;">
                <el-date-picker
                  v-model="dateRange"
                  type="daterange"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  size="small"
                  @change="handleDateRangeChange"
                />
                <el-button type="primary" @click="handleCreatePayment">
                  新增缴费
                </el-button>
              </div>
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
              <div style="display: flex; gap: 12px; align-items: center;">
                <el-date-picker
                  v-model="dateRange"
                  type="daterange"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  size="small"
                  @change="handleDateRangeChange"
                />
                <el-button type="primary" @click="handleCreateUtilityReading">
                  新增抄表
                </el-button>
              </div>
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

      <!-- Occupants Tab -->
      <el-tab-pane name="occupants">
        <template #label>
          居住人
          <el-badge v-if="occupants.length" :value="occupants.length" type="info" style="margin-left: 4px;" />
        </template>
        <el-card>
          <template #header>
            <div class="card-header">
              <span>居住人（主租客 + 亲友）</span>
              <el-button type="primary" @click="openAddOccupantDialog">
                添加居住人
              </el-button>
            </div>
          </template>

          <el-table :data="occupants" v-loading="occupantsLoading" stripe style="width: 100%">
            <el-table-column label="姓名" min-width="120">
              <template #default="{ row }">
                <span style="font-weight: 600;">{{ row.tenant_name || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="角色" width="120">
              <template #default="{ row }">
                <el-tag v-if="row.role === 'primary'" type="danger" size="small">主租客</el-tag>
                <el-tag v-else type="info" size="small">亲友</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="relation" label="关系" width="100">
              <template #default="{ row }">
                {{ row.relation || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="tenant_phone" label="电话" width="150">
              <template #default="{ row }">
                {{ row.tenant_phone || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="tenant_id_card" label="身份证号" min-width="160">
              <template #default="{ row }">
                {{ row.tenant_id_card || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.is_active" type="success" size="small">在住</el-tag>
                <el-tag v-else type="info" size="small">已搬出</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.role !== 'primary'"
                  size="small"
                  type="warning"
                  @click="handleSetPrimary(row)"
                >
                  设为主租客
                </el-button>
                <el-button size="small" @click="openEditOccupantDialog(row)">编辑</el-button>
                <el-button type="danger" size="small" @click="handleRemoveOccupant(row)">移除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!occupantsLoading && occupants.length === 0" description="暂无居住人，点击「添加居住人」来关联主租客和亲友" />
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

    <!-- 续租对话框 -->
    <el-dialog
      v-model="renewDialogVisible"
      title="续租房间"
      width="500px"
    >
      <el-form :model="renewForm" label-width="100px">
        <el-form-item label="当前租期结束">
          <span>{{ room?.lease_end ? room.lease_end.split('T')[0] : '-' }}</span>
        </el-form-item>
        <el-form-item label="续租月数" required>
          <el-input-number
            v-model="renewForm.months"
            :min="1"
            :max="120"
            :step="1"
            controls-position="right"
          />
          <span style="margin-left: 8px; color: #909399;">
            （{{ renewForm.months >= 12 ? (renewForm.months / 12).toFixed(1) + '年' : renewForm.months + '个月' }}）
          </span>
        </el-form-item>
        <el-form-item label="新月租金">
          <el-input-number
            v-model="renewForm.monthly_rent"
            :min="0"
            :step="50"
            controls-position="right"
            placeholder="不修改则保持原租金"
          />
          <span style="margin-left: 8px; color: #909399;">
            原租金：{{ room?.monthly_rent || '-' }}元
          </span>
        </el-form-item>
        <el-form-item label="续租备注">
          <el-input
            v-model="renewForm.notes"
            type="textarea"
            :rows="3"
            placeholder="选填"
          />
        </el-form-item>
        <el-form-item>
          <div style="color: #409EFF; font-size: 13px;">
            <span v-if="room?.lease_end">
              续租后租期将至：
              {{ new Date(new Date(room.lease_end).setMonth(new Date(room.lease_end).getMonth() + renewForm.months)).toISOString().split('T')[0] }}
            </span>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="renewDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="renewSubmitting" @click="handleSubmitRenewLease">
          确认续租
        </el-button>
      </template>
    </el-dialog>

    <!-- 居住人对话框 -->
    <el-dialog
      v-model="occupantDialogVisible"
      :title="occupantEditMode === 'add' ? '添加居住人' : '编辑居住人'"
      width="500px"
    >
      <el-form :model="occupantForm" label-width="100px">
        <el-form-item v-if="occupantEditMode === 'add'" label="选择租客" required>
          <el-select
            v-model="occupantForm.tenant_id"
            placeholder="选择已有租客"
            filterable
            :loading="tenantsLoading"
            style="width: 100%"
          >
            <el-option
              v-for="t in availableTenants"
              :key="t.id"
              :label="`${t.name}（${t.phone}）`"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="租客">
          <span style="font-weight: 600;">
            {{ editingOccupant?.tenant_name }}
          </span>
        </el-form-item>
        <el-form-item label="角色" required>
          <el-radio-group v-model="occupantForm.role">
            <el-radio value="primary">主租客（签合同）</el-radio>
            <el-radio value="secondary">亲友</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="与主租客关系">
          <el-select
            v-model="occupantForm.relation"
            placeholder="选择或输入关系"
            allow-create
            filterable
            clearable
            style="width: 100%"
          >
            <el-option label="配偶" value="配偶" />
            <el-option label="子女" value="子女" />
            <el-option label="父母" value="父母" />
            <el-option label="兄弟姐妹" value="兄弟姐妹" />
            <el-option label="朋友" value="朋友" />
            <el-option label="同事" value="同事" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch
            v-model="occupantForm.is_active"
            active-text="在住"
            inactive-text="已搬出"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="occupantDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="occupantSubmitting" @click="handleSubmitOccupant">
          确认
        </el-button>
      </template>
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

/* 移动端优化 */
@media (max-width: 768px) {
  .room-detail-view {
    padding: 12px;
  }

  .page-header {
    margin-bottom: 12px;
  }

  .title {
    font-size: 16px;
  }

  .room-tabs {
    margin-top: 12px;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .card-header > div {
    width: 100%;
    flex-direction: column;
  }

  /* 表格横向滚动 */
  :deep(.el-card__body) {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  :deep(.el-table) {
    min-width: 600px;
  }
}
</style>
