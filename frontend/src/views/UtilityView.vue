<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'

// Composables
import { useAmountFormatting } from '@/composables/useAmountFormatting'
import { useRoomData } from '@/composables/useRoomData'
import { useUtilityReadings } from '@/composables/useUtilityReadings'
import { useOverdueManagement } from '@/composables/useOverdueManagement'
import { useReadingForm } from '@/composables/useReadingForm'
import { useReadingEdit } from '@/composables/useReadingEdit'
import { usePaymentData } from '@/composables/usePaymentData'
import { useMessageGeneration } from '@/composables/useMessageGeneration'
import { useBatchOperations } from '@/composables/useBatchOperations'

// Child components
import UtilityReadingForm from '@/components/UtilityReadingForm.vue'
import RentManagementCard from '@/components/RentManagementCard.vue'
import ReadingsTable from '@/components/ReadingsTable.vue'
import BatchEntryDialog from '@/components/BatchEntryDialog.vue'
import PaymentDialog from '@/components/PaymentDialog.vue'
import BatchPaymentDialog from '@/components/BatchPaymentDialog.vue'
import EditReadingDialog from '@/components/EditReadingDialog.vue'
import MessageDialog from '@/components/MessageDialog.vue'
import RentReminderDialog from '@/components/RentReminderDialog.vue'

// Extend Room type for batch entry temporary fields
declare module '@/types' {
  interface Room {
    water_reading?: number
    electricity_reading?: number
  }
}

// Activity tab
const activeTab = ref('readings')

// 1. Amount formatting
const { hideAmounts, formatAmount, maskedAmount, maskedRate } = useAmountFormatting()

// 2. Room data
const {
  allRooms, roomOptions, roomsLoading, roomMap,
  loadRooms, getRoomNumber, getRoomInfo, getRoom,
} = useRoomData()

// 3. Message generation (needs getRoomNumber, getRoomInfo, hideAmounts, formatAmount)
const {
  messageDialogVisible, currentMessage, sendingWechat,
  rentReminderPreview, rentReminderVisible,
  generateRentReminder, showRentReminder, copyRentReminder,
  autoGenerateAndSendWechat, generateMessageText,
  copyMessage, showCopyFallback,
} = useMessageGeneration({
  getRoomNumber,
  getRoomInfo,
  hideAmounts,
  formatAmount,
})

// 4. Utility readings (needs roomOptions)
const {
  readings, allReadings, loading, payments, pagination, filters,
  loadReadings, handleFilter, resetFilter,
  handlePageChange, handleSizeChange, mergedReadings,
} = useUtilityReadings({ roomOptions })

// 5. Payment data (needs formatAmount, loadReadings, loadRooms)
const {
  paymentDialogVisible, paymentForm, paymentLoading,
  showPaymentDialog, submitPayment,
} = usePaymentData({ formatAmount, loadReadings, loadRooms })

// 6. Overdue management (needs allRooms, payments, allReadings, roomOptions, formatAmount, mergedReadings, showPaymentDialog)
const {
  overdueRooms, expiringRooms,
  canMarkExpiringRoomPaid, markExpiringRoomPaid,
  sendReminder, getNextPaymentDays,
} = useOverdueManagement({
  allRooms, payments, allReadings, roomOptions, formatAmount,
  mergedReadings, showPaymentDialog,
})

// 7. Reading edit (needs loadReadings, autoGenerateAndSendWechat)
const {
  editDialogVisible, editLoading, editForm,
  showEditDialog, saveEdit, handleDelete,
} = useReadingEdit({ loadReadings, autoGenerateAndSendWechat })

// 8. Reading form (needs roomOptions, getRoomNumber, getRoomInfo, hideAmounts, formatAmount, loadReadings, generateRentReminder, autoGenerateAndSendWechat)
const {
  showFormDialog, formSuccess, selectedRoomId,
  openUtilityForm, showAddForm,
  handleFormSuccessWithReminder,
} = useReadingForm({
  roomOptions, getRoomNumber, getRoomInfo, hideAmounts, formatAmount,
  loadReadings, generateRentReminder, autoGenerateAndSendWechat,
})

// 9. Batch operations (needs allRooms, formatAmount, getRoomNumber, loadReadings, loadRooms, generateMessageText, showCopyFallback)
const {
  batchDialogVisible, batchLoading, selectedRooms, batchForm,
  showBatchForm, selectAllRooms, clearRoomSelection, selectOccupiedRooms,
  submitBatch, tableRef, selectedRows, canBatchPay,
  handleSelectionChange, clearSelection,
  batchPaymentDialogVisible, batchPaymentLoading, batchPayments,
  showBatchPaymentDialog, submitBatchPayment,
  batchGenerateMessages, batchDelete,
} = useBatchOperations({
  allRooms, formatAmount, getRoomNumber, loadReadings, loadRooms,
  generateMessageText, showCopyFallback,
})

// Form success handler that shows rent reminder preview
const onFormSuccess = (result: any) => {
  handleFormSuccessWithReminder(result, {
    setRentReminderPreview: (value: string) => { rentReminderPreview.value = value },
    setRentReminderVisible: (value: boolean) => { rentReminderVisible.value = value },
  })
}

// Handle show reminder event from table
const handleShowReminder = async (row: any) => {
  const readings: any[] = []
  if (row.water_reading) {
    readings.push(row.water_reading)
  }
  if (row.electricity_reading) {
    readings.push(row.electricity_reading)
  }
  await showRentReminder(row.room_id, readings)
}

// Initialize
onMounted(async () => {
  await loadRooms()  // 先加载房间列表
  loadReadings()     // 再加载水电记录（此时 roomOptions 已准备好）
})
</script>

<template>
  <div class="utility-view">
    <div class="page-header">
      <h1>水电表管理</h1>
      <div class="header-buttons">
        <el-button type="success" @click="showBatchForm">
          <el-icon><Plus /></el-icon>
          批量录入
        </el-button>
        <el-button type="primary" @click="showAddForm">
          <el-icon><Plus /></el-icon>
          录入水电
        </el-button>
      </div>
    </div>

    <!-- Rent management card -->
    <RentManagementCard
      :overdue-rooms="overdueRooms"
      :expiring-rooms="expiringRooms"
      :hide-amounts="hideAmounts"
      :format-amount="formatAmount"
      :masked-amount="maskedAmount"
      :get-next-payment-days="getNextPaymentDays"
      :can-mark-expiring-room-paid="canMarkExpiringRoomPaid"
      @send-reminder="sendReminder"
      @mark-paid="markExpiringRoomPaid"
      @open-utility-form="openUtilityForm"
    />

    <el-tabs v-model="activeTab">
      <el-tab-pane label="水电记录" name="readings">
        <!-- Filters -->
        <el-card class="filter-card">
          <el-form :inline="true">
            <el-form-item label="房间号">
              <el-select
                v-model="filters.room_id"
                placeholder="选择房间"
                clearable
                filterable
                :loading="roomsLoading"
              >
                <el-option
                  v-for="room in roomOptions"
                  :key="room.id"
                  :label="room.room_number"
                  :value="room.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="抄表日期">
              <el-date-picker
                v-model="filters.start_date"
                type="date"
                placeholder="开始日期"
                value-format="YYYY-MM-DD"
              />
              <span class="date-separator">-</span>
              <el-date-picker
                v-model="filters.end_date"
                type="date"
                placeholder="结束日期"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="handleFilter">筛选</el-button>
              <el-button @click="resetFilter">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- Batch actions bar -->
        <el-card v-if="selectedRows.length > 0" class="batch-actions-card">
          <div class="batch-actions">
            <span class="selected-info">
              已选择 <strong>{{ selectedRows.length }}</strong> 条记录
            </span>
            <div class="batch-buttons">
              <el-button type="primary" :disabled="!canBatchPay" @click="showBatchPaymentDialog">
                批量收租 ({{ selectedRows.length }})
              </el-button>
              <el-button type="success" @click="batchGenerateMessages">
                批量生成消息
              </el-button>
              <el-button type="danger" @click="batchDelete">
                批量删除
              </el-button>
              <el-button @click="clearSelection">
                取消选择
              </el-button>
            </div>
          </div>
        </el-card>

        <!-- Readings table -->
        <ReadingsTable
          ref="tableRef"
          :loading="loading"
          :data="mergedReadings"
          :room-map="roomMap"
          :hide-amounts="hideAmounts"
          :format-amount="formatAmount"
          :masked-amount="maskedAmount"
          :get-room-number="getRoomNumber"
          :get-room-info="getRoomInfo"
          @show-reminder="handleShowReminder"
          @show-payment="showPaymentDialog"
          @edit="showEditDialog"
          @delete="handleDelete"
          @selection-change="handleSelectionChange"
        />

        <!-- Pagination -->
        <div class="pagination-container">
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.size"
            :page-sizes="[10, 20, 50, 100]"
            :total="pagination.total"
            layout="total, sizes, prev, pager, next, jumper"
            @current-change="handlePageChange"
            @size-change="handleSizeChange"
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- Reading form dialog -->
    <el-dialog
      v-model="showFormDialog"
      title="录入水电表读数"
      width="600px"
      :close-on-click-modal="false"
      @close="showFormDialog = false; selectedRoomId = undefined"
    >
      <UtilityReadingForm
        v-if="showFormDialog"
        :room-id="selectedRoomId"
        @success="onFormSuccess"
        @cancel="showFormDialog = false; selectedRoomId = undefined"
      />
    </el-dialog>

    <!-- Batch entry dialog -->
    <BatchEntryDialog
      v-model="batchDialogVisible"
      :all-rooms="allRooms"
      :batch-form="batchForm"
      :batch-loading="batchLoading"
      :selected-rooms="selectedRooms"
      :hide-amounts="hideAmounts"
      :masked-rate="maskedRate"
      @submit="submitBatch"
      @select-all="selectAllRooms"
      @clear="clearRoomSelection"
      @select-occupied="selectOccupiedRooms"
    />

    <!-- Payment dialog -->
    <PaymentDialog
      v-model="paymentDialogVisible"
      :payment-form="paymentForm"
      :payment-loading="paymentLoading"
      :format-amount="formatAmount"
      :get-room-number="getRoomNumber"
      @submit="submitPayment"
    />

    <!-- Edit reading dialog -->
    <EditReadingDialog
      v-model="editDialogVisible"
      :edit-form="editForm"
      :edit-loading="editLoading"
      @submit="saveEdit"
    />

    <!-- Message dialog -->
    <MessageDialog
      v-model="messageDialogVisible"
      :message="currentMessage"
      :sending-wechat="sendingWechat"
      @copy="copyMessage"
    />

    <!-- Batch payment dialog -->
    <BatchPaymentDialog
      v-model="batchPaymentDialogVisible"
      :batch-payments="batchPayments"
      :batch-payment-loading="batchPaymentLoading"
      :format-amount="formatAmount"
      :get-room-number="getRoomNumber"
      @submit="submitBatchPayment"
    />

    <!-- Rent reminder dialog -->
    <RentReminderDialog
      v-model="rentReminderVisible"
      :preview="rentReminderPreview"
      @copy="copyRentReminder"
    />
  </div>
</template>

<style scoped>
.utility-view {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.filter-card {
  margin-bottom: 20px;
}

.date-separator {
  margin: 0 8px;
  color: #909399;
}

.pagination-container {
  display: flex;
  justify-content: center;
}

/* Batch actions styles */
.batch-actions-card {
  margin-bottom: 20px;
  border: 2px solid #409eff;
  background: linear-gradient(135deg, #ecf5ff 0%, #ffffff 100%);
}

.batch-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 8px;
}

.batch-actions .selected-info {
  font-size: 15px;
  color: #409eff;
  font-weight: 500;
}

.batch-actions .selected-info strong {
  font-size: 18px;
  font-weight: 700;
}

.batch-actions .batch-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.header-buttons {
  display: flex;
  gap: 8px;
}
</style>
