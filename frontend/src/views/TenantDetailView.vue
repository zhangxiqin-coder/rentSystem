<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, ArrowDown, Edit, EditPen, Delete, Plus, House, Document, Refresh, CircleClose, Hide, View } from '@element-plus/icons-vue'
import { tenantsApi } from '@/api/tenants'
import { leaseRecordsApi } from '@/api/leaseRecords'
import { roomApi } from '@/api/room'
import { useAuthStore } from '@/stores/auth'
import { usePrivacyMode } from '@/composables/usePrivacyMode'
import type { Tenant, LeaseRecord, Room } from '@/types'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const { privacyMode, togglePrivacyMode, maskName, maskPhone, maskIdCard, maskAmount } = usePrivacyMode()
const tenantId = computed(() => Number(route.params.id))

const loading = ref(false)
const tenant = ref<Tenant | null>(null)
const leaseRecords = ref<LeaseRecord[]>([])
const availableRooms = ref<Room[]>([])

// 入住对话框
const checkInDialogVisible = ref(false)
const checkInForm = ref({
  room_id: undefined as number | undefined,
  initial_electricity_reading: 0,
  initial_water_reading: 0,
  lease_start: '',
  lease_end: '',
  monthly_rent: 0,
  deposit_amount: 0,
  notes: '',
  // 入住首期收款：租客入住当天通常已交首期房租
  first_payment_made: true,
  first_payment_amount: null as number | null
})

// 首期收款金额预览（月租 × 付款周期，付款周期取所选房间的）
const firstPaymentPreview = computed(() => {
  const room = availableRooms.value.find(r => r.id === checkInForm.value.room_id)
  const rent = Number(checkInForm.value.monthly_rent) || 0
  const cycle = Number((room as any)?.payment_cycle) || 1
  return rent * cycle
})

// 编辑租赁记录对话框
const editDialogVisible = ref(false)
const editLoading = ref(false)
const editForm = ref({
  id: 0,
  lease_start: '',
  lease_end: '',
  monthly_rent: 0,
  deposit_amount: 0,
  initial_electricity_reading: 0,
  initial_water_reading: 0,
  notes: ''
})

// 续租对话框
const renewDialogVisible = ref(false)
const renewLoading = ref(false)
const renewForm = ref({
  months: 1,
  monthly_rent: undefined as number | undefined,
  notes: ''
})

// 判断是否有活跃租约（根据时间：status_display为active）
const hasActiveLease = computed(() => leaseRecords.value.some(r => r.status_display === 'active'))

// 获取租客详情
const fetchTenantDetail = async () => {
  loading.value = true
  try {
    tenant.value = await tenantsApi.get(tenantId.value)
  } catch (error) {
    ElMessage.error('获取租客详情失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 获取租赁历史
const fetchLeaseRecords = async () => {
  try {
    const records = await leaseRecordsApi.list({ tenant_id: tenantId.value })
    leaseRecords.value = records
  } catch (error) {
    console.error('获取租赁记录失败:', error)
  }
}

// 获取可入住房间
const fetchAvailableRooms = async () => {
  try {
    const allRooms = await roomApi.list()
    // 过滤出空闲房间
    availableRooms.value = allRooms.filter(room => room.status === 'available')
  } catch (error) {
    console.error('获取房间列表失败:', error)
  }
}

// 打开入住对话框
const openCheckInDialog = () => {
  checkInForm.value = {
    room_id: undefined,
    initial_electricity_reading: 0,
    initial_water_reading: 0,
    lease_start: new Date().toISOString().split('T')[0],
    lease_end: (() => {
      const d = new Date()
      d.setFullYear(d.getFullYear() + 1)
      d.setDate(d.getDate() - 1)
      return d.toISOString().split('T')[0]
    })(),
    monthly_rent: 0,
    deposit_amount: 0,
    notes: '',
    first_payment_made: true,
    first_payment_amount: null
  }
  checkInDialogVisible.value = true
  fetchAvailableRooms()
}

// 选房后预填初始水电读数：优先用房间的初始读数
// （上个租客退租时录入的读数会写进房间，这里自动带出，没抄表就先用它）
const onCheckInRoomChange = (roomId: number | undefined) => {
  if (roomId == null) return
  const room = availableRooms.value.find(r => r.id === roomId)
  if (!room) return
  const prevElec = Number(room.initial_electricity_reading) || 0
  const prevWater = Number(room.initial_water_reading) || 0
  checkInForm.value.initial_electricity_reading = prevElec
  checkInForm.value.initial_water_reading = prevWater
}

// 确认入住
const handleCheckIn = async () => {
  if (!checkInForm.value.room_id) {
    ElMessage.warning('请选择房间')
    return
  }

  if (!checkInForm.value.lease_start || !checkInForm.value.lease_end) {
    ElMessage.warning('请设置租期')
    return
  }

  if (checkInForm.value.monthly_rent <= 0) {
    ElMessage.warning('请填写月租金')
    return
  }

  try {
    await leaseRecordsApi.create({
      tenant_id: tenantId.value,
      room_id: checkInForm.value.room_id,
      initial_electricity_reading: checkInForm.value.initial_electricity_reading > 0 ? checkInForm.value.initial_electricity_reading : undefined,
      initial_water_reading: checkInForm.value.initial_water_reading > 0 ? checkInForm.value.initial_water_reading : undefined,
      lease_start: checkInForm.value.lease_start,
      lease_end: checkInForm.value.lease_end,
      monthly_rent: checkInForm.value.monthly_rent,
      deposit_amount: checkInForm.value.deposit_amount || undefined,
      notes: checkInForm.value.notes,
      first_payment_made: checkInForm.value.first_payment_made,
      first_payment_amount: checkInForm.value.first_payment_made && Number(checkInForm.value.first_payment_amount) > 0
        ? Number(checkInForm.value.first_payment_amount)
        : undefined
    })

    ElMessage.success(
      checkInForm.value.first_payment_made
        ? `入住成功，已记入住收款 ¥${firstPaymentPreview.value}`
        : '入住成功'
    )
    checkInDialogVisible.value = false
    await fetchLeaseRecords()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || error.response?.data?.message || '入住失败')
    console.error(error)
  }
}

// 下载PDF合同
const handle下载PDF = (record: LeaseRecord) => {
  const pdfUrl = `/api/v1/generate-contract-pdf/${record.id}`
  window.open(pdfUrl, '_blank')
}

// 编辑合同（在新标签页打开可编辑的HTML合同）
const handle编辑合同 = (record: LeaseRecord) => {
  const editUrl = `/api/v1/generate-contract/${record.id}?editable=true`
  window.open(editUrl, '_blank')
}

// 退租对话框
const endLeaseDialogVisible = ref(false)
const endLeaseSubmitting = ref(false)
const endLeaseForm = ref({
  record_id: 0,
  room_number: '',
  final_water_reading: undefined as number | undefined,
  final_electricity_reading: undefined as number | undefined,
  utility_paid: true,
  payment_method: '微信支付'
})
// 上次读数+费率（费用预览用）
const endLeaseContext = ref<{
  water: { previous_reading: number | null; rate: number | null }
  electricity: { previous_reading: number | null; rate: number | null }
} | null>(null)

// 水费预览
const waterCostPreview = computed(() => {
  const ctx = endLeaseContext.value
  if (!ctx || endLeaseForm.value.final_water_reading == null) return null
  const prev = Number(ctx.water.previous_reading ?? 0)
  const rate = Number(ctx.water.rate ?? 0)
  const usage = endLeaseForm.value.final_water_reading - prev
  if (usage < 0) return { error: '读数不能小于上次读数' }
  return { usage, amount: usage * rate }
})

// 电费预览
const electricityCostPreview = computed(() => {
  const ctx = endLeaseContext.value
  if (!ctx || endLeaseForm.value.final_electricity_reading == null) return null
  const prev = Number(ctx.electricity.previous_reading ?? 0)
  const rate = Number(ctx.electricity.rate ?? 0)
  const usage = endLeaseForm.value.final_electricity_reading - prev
  if (usage < 0) return { error: '读数不能小于上次读数' }
  return { usage, amount: usage * rate }
})

// 打开退租对话框（拉取上次读数和费率）
const handleEndLease = async (record: LeaseRecord) => {
  endLeaseForm.value = {
    record_id: record.id,
    room_number: record.room?.room_number || '',
    final_water_reading: undefined,
    final_electricity_reading: undefined,
    utility_paid: true,
    payment_method: '微信支付'
  }
  endLeaseContext.value = null
  endLeaseDialogVisible.value = true
  try {
    endLeaseContext.value = await leaseRecordsApi.getFinalReadingContext(record.id)
  } catch (error) {
    console.error('获取退租水电上下文失败:', error)
  }
}

// 确认退租（带水电结算）
const confirmEndLease = async () => {
  const form = endLeaseForm.value
  if (waterCostPreview.value?.error) {
    ElMessage.warning(`水费：${waterCostPreview.value.error}`)
    return
  }
  if (electricityCostPreview.value?.error) {
    ElMessage.warning(`电费：${electricityCostPreview.value.error}`)
    return
  }

  const hasUtility = form.final_water_reading != null || form.final_electricity_reading != null
  const tip = hasUtility
    ? `退租后房间标记为空闲。将按读数生成水电记录${form.utility_paid ? '及已收款缴费单' : '（未收款）'}，退租读数将作为下个租客的初始读数。`
    : '退租后房间将标记为空闲。'

  try {
    await ElMessageBox.confirm(tip, '退租确认', {
      confirmButtonText: '确定退租',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }

  endLeaseSubmitting.value = true
  try {
    const payload: Record<string, unknown> = { utility_paid: form.utility_paid, payment_method: form.payment_method }
    if (form.final_water_reading != null) payload.final_water_reading = form.final_water_reading
    if (form.final_electricity_reading != null) payload.final_electricity_reading = form.final_electricity_reading
    await leaseRecordsApi.endLease(form.record_id, payload)
    ElMessage.success('退租成功')
    endLeaseDialogVisible.value = false
    await fetchLeaseRecords()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '退租失败')
    console.error(error)
  } finally {
    endLeaseSubmitting.value = false
  }
}

// 删除租赁记录
const handleDeleteRecord = async (record: LeaseRecord) => {
  try {
    await ElMessageBox.confirm(
      '确定要删除该租赁记录吗？此操作不可恢复。',
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await leaseRecordsApi.delete(record.id)
    ElMessage.success('删除成功')
    await fetchLeaseRecords()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

// 恢复租赁（恢复入住）
const handleRestore = async (record: LeaseRecord) => {
  try {
    await ElMessageBox.confirm(
      `确定要恢复该租赁记录吗？房间将重新标记为已出租。`,
      '恢复确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await leaseRecordsApi.restore(record.id)
    ElMessage.success('恢复成功')
    await fetchLeaseRecords()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('恢复失败')
      console.error(error)
    }
  }
}

// 编辑租客信息
const handleEdit = () => {
  router.push(`/tenants/${tenantId.value}/edit`)
}

// 打开编辑租赁记录对话框
const openEditDialog = (record: LeaseRecord) => {
  editForm.value = {
    id: record.id,
    lease_start: record.lease_start,
    lease_end: record.lease_end,
    monthly_rent: Number(record.monthly_rent) || 0,
    deposit_amount: Number(record.deposit_amount) || 0,
    initial_electricity_reading: Number(record.initial_electricity_reading) || 0,
    initial_water_reading: Number(record.initial_water_reading) || 0,
    notes: record.notes || ''
  }
  editDialogVisible.value = true
}

// 提交编辑租赁记录
const submitEdit = async () => {
  if (!editForm.value.lease_start || !editForm.value.lease_end) {
    ElMessage.warning('请设置租期')
    return
  }
  editLoading.value = true
  try {
    await leaseRecordsApi.update(editForm.value.id, {
      lease_start: editForm.value.lease_start,
      lease_end: editForm.value.lease_end,
      monthly_rent: editForm.value.monthly_rent,
      deposit_amount: editForm.value.deposit_amount,
      initial_electricity_reading: editForm.value.initial_electricity_reading,
      initial_water_reading: editForm.value.initial_water_reading,
      notes: editForm.value.notes || undefined
    })
    ElMessage.success('修改成功')
    editDialogVisible.value = false
    await fetchLeaseRecords()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '修改失败')
    console.error(error)
  } finally {
    editLoading.value = false
  }
}

// 返回列表
const goBack = () => {
  router.push('/tenants')
}

// 打开续租对话框
const openRenewDialog = () => {
  renewForm.value = {
    months: 1,
    monthly_rent: undefined,
    notes: ''
  }
  renewDialogVisible.value = true
}

// 提交续租
const submitRenew = async () => {
  if (renewForm.value.months <= 0) {
    ElMessage.warning('续租月数必须大于0')
    return
  }
  renewLoading.value = true
  try {
    const data: { months: number; monthly_rent?: number; notes?: string } = {
      months: renewForm.value.months
    }
    if (renewForm.value.monthly_rent) {
      data.monthly_rent = renewForm.value.monthly_rent
    }
    if (renewForm.value.notes.trim()) {
      data.notes = renewForm.value.notes.trim()
    }
    await tenantsApi.renew(tenantId.value, data)
    ElMessage.success('续租成功')
    renewDialogVisible.value = false
    await fetchLeaseRecords()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '续租失败')
    console.error(error)
  } finally {
    renewLoading.value = false
  }
}

onMounted(() => {
  fetchTenantDetail()
  fetchLeaseRecords()
})
</script>

<template>
  <div class="tenant-detail-page">
    <div v-loading="loading" class="page-content">
      <!-- 头部导航 -->
      <div class="page-header">
        <div class="header-left">
          <el-button :icon="ArrowLeft" @click="goBack">返回</el-button>
        </div>
        <div class="header-actions">
          <el-button
            :type="privacyMode ? 'warning' : 'default'"
            :icon="privacyMode ? View : Hide"
            @click="togglePrivacyMode()"
          >
            {{ privacyMode ? '显示信息' : '隐藏信息' }}
          </el-button>
          <el-button
            v-if="hasActiveLease"
            type="success"
            :icon="Refresh"
            @click="openRenewDialog"
          >
            续租
          </el-button>
          <el-button type="primary" :icon="House" @click="openCheckInDialog">
            入住
          </el-button>
          <el-button type="default" :icon="Edit" @click="handleEdit">
            编辑
          </el-button>
        </div>
      </div>

      <!-- 租客基本信息 -->
      <el-card v-if="tenant" class="info-card">
        <template #header>
          <h3>基本信息</h3>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="姓名">{{ privacyMode ? maskName(tenant.name) : tenant.name }}</el-descriptions-item>
          <el-descriptions-item label="电话">{{ privacyMode ? maskPhone(tenant.phone) : tenant.phone }}</el-descriptions-item>
          <el-descriptions-item label="身份证号">{{ privacyMode ? maskIdCard(tenant.id_card) : tenant.id_card }}</el-descriptions-item>
          <el-descriptions-item label="紧急联系人">{{ privacyMode ? maskName(tenant.emergency_contact || '') : (tenant.emergency_contact || '-') }}</el-descriptions-item>
          <el-descriptions-item label="紧急联系电话">{{ privacyMode ? maskPhone(tenant.emergency_phone || '') : (tenant.emergency_phone || '-') }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ new Date(tenant.created_at).toLocaleString('zh-CN') }}
          </el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">
            {{ tenant.notes || '-' }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 租赁历史 -->
      <el-card class="history-card">
        <template #header>
          <h3>租赁历史</h3>
        </template>
        <el-table
          :data="leaseRecords"
          stripe
          style="width: 100%"
        >
          <el-table-column prop="room.room_number" label="房间号" width="100" />
          <el-table-column label="租期" width="250">
            <template #default="{ row }">
              {{ new Date(row.lease_start).toLocaleDateString('zh-CN') }} 至
              {{ new Date(row.lease_end).toLocaleDateString('zh-CN') }}
            </template>
          </el-table-column>
          <el-table-column prop="monthly_rent" label="月租金" width="100">
            <template #default="{ row }">
              {{ privacyMode ? maskAmount(row.monthly_rent) : `¥${row.monthly_rent}` }}
            </template>
          </el-table-column>
          <el-table-column prop="deposit_amount" label="押金" width="100">
            <template #default="{ row }">
              {{ privacyMode ? maskAmount(row.deposit_amount) : (row.deposit_amount ? `¥${row.deposit_amount}` : '-') }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag v-if="row.status_display === 'active'" type="success">已生效</el-tag>
              <el-tag v-else-if="row.status_display === 'pending'" type="warning">待生效</el-tag>
              <el-tag v-else type="info">已结束</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="初始水电" width="160">
            <template #default="{ row }">
              <span class="initial-readings">
                电：{{ row.initial_electricity_reading ? row.initial_electricity_reading : '-' }}
                ｜水：{{ row.initial_water_reading ? row.initial_water_reading : '-' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="notes" label="备注" show-overflow-tooltip />
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-dropdown trigger="click">
                <el-button size="small" type="primary">
                  操作<el-icon class="el-icon--right"><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click.native="openEditDialog(row)">
                      <el-icon><Edit /></el-icon>编辑
                    </el-dropdown-item>
                    <el-dropdown-item @click.native="handle下载PDF(row)">
                      <el-icon><Document /></el-icon>下载合同
                    </el-dropdown-item>
                    <el-dropdown-item @click.native="handle编辑合同(row)">
                      <el-icon><EditPen /></el-icon>编辑合同
                    </el-dropdown-item>
                    <el-dropdown-item
                      v-if="row.status_display === 'active'"
                      @click.native="handleEndLease(row)"
                    >
                      <el-icon><CircleClose /></el-icon>退租
                    </el-dropdown-item>
                    <el-dropdown-item
                      v-if="row.status_display === 'expired'"
                      @click.native="handleRestore(row)"
                    >
                      <el-icon><Refresh /></el-icon>恢复
                    </el-dropdown-item>
                    <el-dropdown-item
                      v-if="row.status_display === 'pending'"
                      @click.native="handleDeleteRecord(row)"
                      divided
                    >
                      <el-icon><Delete /></el-icon>删除
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- 入住对话框 -->
    <el-dialog
      v-model="checkInDialogVisible"
      title="办理入住"
      width="500px"
    >
      <el-form :model="checkInForm" label-width="120px">
        <el-form-item label="选择房间">
          <el-select
            v-model="checkInForm.room_id"
            placeholder="请选择房间"
            style="width: 100%"
            @change="onCheckInRoomChange"
          >
            <el-option
              v-for="room in availableRooms"
              :key="room.id"
              :label="`${room.room_number} - ¥${room.monthly_rent}/月`"
              :value="room.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="初始电表读数">
          <el-input-number
            v-model="checkInForm.initial_electricity_reading"
            :min="0"
            :precision="2"
            :step="10"
            placeholder="入住时电表读数"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="初始水表读数">
          <el-input-number
            v-model="checkInForm.initial_water_reading"
            :min="0"
            :precision="2"
            :step="1"
            placeholder="入住时水表读数"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="租期开始">
          <el-date-picker
            v-model="checkInForm.lease_start"
            type="date"
            placeholder="选择开始日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="租期结束">
          <el-date-picker
            v-model="checkInForm.lease_end"
            type="date"
            placeholder="选择结束日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="月租金">
          <el-input-number
            v-model="checkInForm.monthly_rent"
            :min="0"
            :precision="2"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="押金">
          <el-input-number
            v-model="checkInForm.deposit_amount"
            :min="0"
            :precision="2"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="入住收款">
          <el-switch v-model="checkInForm.first_payment_made" />
        </el-form-item>
        <el-form-item v-if="checkInForm.first_payment_made" label="收款金额">
          <el-input-number
            v-model="checkInForm.first_payment_amount"
            :min="0"
            :precision="2"
            :step="100"
            :placeholder="`默认 ${firstPaymentPreview}`"
            style="width: 100%"
          />
          <div style="font-size: 12px; color: #909399; line-height: 1.5; margin-top: 4px;">
            不填默认 {{ firstPaymentPreview }} 元（月租×付款周期），入住当天自动记一笔房租收款
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="checkInForm.notes"
            type="textarea"
            :rows="3"
            placeholder="选填"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="checkInDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCheckIn">确定</el-button>
      </template>
    </el-dialog>

    <!-- 编辑租赁记录对话框 -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑租赁记录"
      width="500px"
    >
      <el-form :model="editForm" label-width="120px">
        <el-form-item label="租期开始">
          <el-date-picker
            v-model="editForm.lease_start"
            type="date"
            placeholder="选择开始日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="租期结束">
          <el-date-picker
            v-model="editForm.lease_end"
            type="date"
            placeholder="选择结束日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="月租金">
          <el-input-number
            v-model="editForm.monthly_rent"
            :min="0"
            :precision="2"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="押金">
          <el-input-number
            v-model="editForm.deposit_amount"
            :min="0"
            :precision="2"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="初始电表读数">
          <el-input-number
            v-model="editForm.initial_electricity_reading"
            :min="0"
            :precision="2"
            :step="10"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="初始水表读数">
          <el-input-number
            v-model="editForm.initial_water_reading"
            :min="0"
            :precision="2"
            :step="1"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="editForm.notes"
            type="textarea"
            :rows="3"
            placeholder="选填"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 续租对话框 -->
    <el-dialog
      v-model="renewDialogVisible"
      title="租客续租"
      width="450px"
      :close-on-click-modal="false"
    >
      <div v-if="tenant" class="renew-info">
        <p><strong>租客：</strong>{{ tenant.name }}</p>
        <p><strong>电话：</strong>{{ tenant.phone }}</p>
      </div>
      <el-form label-width="100px" style="margin-top: 16px">
        <el-form-item label="续租月数">
          <el-input-number
            v-model="renewForm.months"
            :min="1"
            :max="120"
            :step="1"
          />
        </el-form-item>
        <el-form-item label="新月租金">
          <el-input
            v-model.number="renewForm.monthly_rent"
            placeholder="不填则保持原租金"
            type="number"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="renewForm.notes"
            type="textarea"
            :rows="3"
            placeholder="可选备注"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="renewDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="renewLoading" @click="submitRenew">确认续租</el-button>
      </template>
    </el-dialog>

    <!-- 退租对话框 -->
    <el-dialog
      v-model="endLeaseDialogVisible"
      title="退租结算"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      >
        退租时录入当前水电表读数，系统自动生成水电缴费单；该读数将作为下个租客的初始读数。不填则跳过水电结算。
      </el-alert>
      <el-form :model="endLeaseForm" label-width="120px">
        <el-form-item label="房间">
          <span>{{ endLeaseForm.room_number }}</span>
        </el-form-item>
        <el-form-item label="当前水表读数">
          <el-input-number
            v-model="endLeaseForm.final_water_reading"
            :min="0"
            :precision="2"
            :step="1"
            placeholder="退租时水表读数"
            style="width: 100%"
          />
          <div v-if="endLeaseContext" class="reading-hint">
            上次：{{ endLeaseContext.water.previous_reading ?? '无记录' }}
            <template v-if="waterCostPreview && !waterCostPreview.error">
              ｜用量 {{ waterCostPreview.usage }} 吨 ｜水费 ¥{{ waterCostPreview.amount.toFixed(2) }}
            </template>
            <span v-else-if="waterCostPreview?.error" class="error-text">{{ waterCostPreview.error }}</span>
          </div>
        </el-form-item>
        <el-form-item label="当前电表读数">
          <el-input-number
            v-model="endLeaseForm.final_electricity_reading"
            :min="0"
            :precision="2"
            :step="10"
            placeholder="退租时电表读数"
            style="width: 100%"
          />
          <div v-if="endLeaseContext" class="reading-hint">
            上次：{{ endLeaseContext.electricity.previous_reading ?? '无记录' }}
            <template v-if="electricityCostPreview && !electricityCostPreview.error">
              ｜用量 {{ electricityCostPreview.usage }} 度 ｜电费 ¥{{ electricityCostPreview.amount.toFixed(2) }}
            </template>
            <span v-else-if="electricityCostPreview?.error" class="error-text">{{ electricityCostPreview.error }}</span>
          </div>
        </el-form-item>
        <el-form-item v-if="endLeaseForm.final_water_reading != null || endLeaseForm.final_electricity_reading != null" label="水电费">
          <el-radio-group v-model="endLeaseForm.utility_paid">
            <el-radio :value="true">已收款</el-radio>
            <el-radio :value="false">未收款</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="(endLeaseForm.final_water_reading != null || endLeaseForm.final_electricity_reading != null) && endLeaseForm.utility_paid" label="收款方式">
          <el-select v-model="endLeaseForm.payment_method" style="width: 100%">
            <el-option label="微信支付" value="微信支付" />
            <el-option label="支付宝" value="支付宝" />
            <el-option label="现金" value="现金" />
            <el-option label="银行转账" value="银行转账" />
          </el-select>
        </el-form-item>
        <el-form-item
          v-if="waterCostPreview && !waterCostPreview.error && electricityCostPreview && !electricityCostPreview.error"
          label="合计"
        >
          <span class="total-amount">¥{{ (waterCostPreview.amount + electricityCostPreview.amount).toFixed(2) }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="endLeaseDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="endLeaseSubmitting" @click="confirmEndLease">确认退租</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tenant-detail-page {
  padding: 20px;
}

.page-content {
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.info-card,
.history-card {
  margin-bottom: 20px;
}

.info-card h3,
.history-card h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.renew-info {
  background: #f5f7fa;
  padding: 12px 16px;
  border-radius: 8px;
}

.renew-info p {
  margin: 4px 0;
}

.reading-hint {
  font-size: 12px;
  color: #909399;
  line-height: 1.6;
  width: 100%;
}

.error-text {
  color: #f56c6c;
}

.total-amount {
  font-size: 18px;
  font-weight: 600;
  color: #f56c6c;
}
</style>
