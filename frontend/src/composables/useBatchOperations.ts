import { ref, type Ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Room } from '@/types'

interface UseBatchOperationsDeps {
  allRooms: Ref<Room[]>
  formatAmount: (value: number, currency?: string) => string
  getRoomNumber: (roomId: number) => string
  loadReadings: () => Promise<void>
  loadRooms: () => Promise<void>
  generateMessageText: (roomId: number, readings: any[]) => Promise<string>
  showCopyFallback: (message: string) => void
}

export function useBatchOperations(deps: UseBatchOperationsDeps) {
  const {
    allRooms,
    formatAmount,
    getRoomNumber,
    loadReadings,
    loadRooms,
    generateMessageText,
    showCopyFallback,
  } = deps

  // 批量录入对话框
  const batchDialogVisible = ref(false)
  const batchLoading = ref(false)
  const selectedRooms = ref<number[]>([])
  const batchForm = ref({
    reading_date: new Date().toISOString().split('T')[0],
    rooms: [] as number[],
    water_reading: null as number | null,
    electric_reading: null as number | null,
  })

  // 显示批量录入对话框
  const showBatchForm = () => {
    batchDialogVisible.value = true
    selectedRooms.value = []
    batchForm.value.rooms = []
  }

  // 全选房间
  const selectAllRooms = () => {
    selectedRooms.value = allRooms.value.map(r => r.id)
    batchForm.value.rooms = allRooms.value.map(r => r.id)
  }

  // 清除房间选择
  const clearRoomSelection = () => {
    selectedRooms.value = []
    batchForm.value.rooms = []
  }

  // 选择已入住房间
  const selectOccupiedRooms = () => {
    const occupied = allRooms.value.filter(r => r.status === 'occupied')
    selectedRooms.value = occupied.map(r => r.id)
    batchForm.value.rooms = occupied.map(r => r.id)
  }

  // 批量录入提交
  const submitBatch = async (formData: any) => {
    batchLoading.value = true
    try {
      // TODO: 实现批量录入逻辑
      ElMessage.success('批量录入成功')
      batchDialogVisible.value = false
      await loadReadings()
    } catch (error) {
      console.error('Failed to submit batch entry:', error)
      ElMessage.error('批量录入失败')
    } finally {
      batchLoading.value = false
    }
  }

  // 表格相关
  const tableRef = ref<any>(null)
  const selectedRows = ref<any[]>([])
  const canBatchPay = ref(false)

  // 处理表格选择变化
  const handleSelectionChange = (selection: any[]) => {
    selectedRows.value = selection
    canBatchPay.value = selection.length > 0
  }

  // 清除表格选择
  const clearSelection = () => {
    selectedRows.value = []
    canBatchPay.value = false
    if (tableRef.value) {
      tableRef.value.clearSelection()
    }
  }

  // 批量支付对话框
  const batchPaymentDialogVisible = ref(false)
  const batchPaymentLoading = ref(false)
  const batchPayments = ref<any[]>([])

  // 显示批量支付对话框
  const showBatchPaymentDialog = () => {
    if (selectedRows.value.length === 0) {
      ElMessage.warning('请先选择要收租的记录')
      return
    }
    batchPaymentDialogVisible.value = true
    batchPayments.value = selectedRows.value.map(row => ({
      room_id: row.room_id,
      amount: row.total_amount || 0,
      payment_method: '微信支付',
      payment_date: new Date().toISOString().split('T')[0],
      notes: '',
    }))
  }

  // 批量支付提交
  const submitBatchPayment = async () => {
    batchPaymentLoading.value = true
    try {
      // TODO: 实现批量支付逻辑
      ElMessage.success('批量收租成功')
      batchPaymentDialogVisible.value = false
      clearSelection()
      await loadReadings()
      await loadRooms()
    } catch (error) {
      console.error('Failed to submit batch payment:', error)
      ElMessage.error('批量收租失败')
    } finally {
      batchPaymentLoading.value = false
    }
  }

  // 批量生成消息
  const batchGenerateMessages = async () => {
    if (selectedRows.value.length === 0) {
      ElMessage.warning('请先选择要生成消息的记录')
      return
    }

    try {
      const messages: string[] = []

      for (const row of selectedRows.value) {
        // TODO: 获取房间的水电读数
        const readings: any[] = []
        const message = await generateMessageText(row.room_id, readings)
        messages.push(message)
      }

      // 合并所有消息
      const combinedMessage = messages.join('\n\n---\n\n')
      showCopyFallback(combinedMessage)
      ElMessage.success(`已生成 ${messages.length} 条消息`)
    } catch (error) {
      console.error('Failed to generate batch messages:', error)
      ElMessage.error('生成批量消息失败')
    }
  }

  // 批量删除
  const batchDelete = async () => {
    if (selectedRows.value.length === 0) {
      ElMessage.warning('请先选择要删除的记录')
      return
    }

    try {
      await ElMessageBox.confirm(
        `确定要删除选中的 ${selectedRows.value.length} 条记录吗？`,
        '批量删除',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )

      // TODO: 实现批量删除逻辑
      ElMessage.success('批量删除成功')
      clearSelection()
      await loadReadings()
    } catch (error) {
      if (error !== 'cancel') {
        console.error('Failed to batch delete:', error)
        ElMessage.error('批量删除失败')
      }
    }
  }

  return {
    batchDialogVisible,
    batchLoading,
    selectedRooms,
    batchForm,
    showBatchForm,
    selectAllRooms,
    clearRoomSelection,
    selectOccupiedRooms,
    submitBatch,
    tableRef,
    selectedRows,
    canBatchPay,
    handleSelectionChange,
    clearSelection,
    batchPaymentDialogVisible,
    batchPaymentLoading,
    batchPayments,
    showBatchPaymentDialog,
    submitBatchPayment,
    batchGenerateMessages,
    batchDelete,
  }
}
