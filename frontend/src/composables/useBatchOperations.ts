import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
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
  const batchSelectedRooms = ref<number[]>([])

  // 显示批量录入对话框
  const showBatchDialog = () => {
    batchDialogVisible.value = true
    batchSelectedRooms.value = []
  }

  // 批量录入提交
  const submitBatchEntry = async (formData: any) => {
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

  // 批量支付对话框
  const batchPaymentDialogVisible = ref(false)
  const batchPaymentLoading = ref(false)
  const batchPaymentSelectedRooms = ref<number[]>([])

  // 显示批量支付对话框
  const showBatchPaymentDialog = () => {
    batchPaymentDialogVisible.value = true
    batchPaymentSelectedRooms.value = []
  }

  // 批量支付提交
  const submitBatchPayment = async (paymentData: any) => {
    batchPaymentLoading.value = true
    try {
      // TODO: 实现批量支付逻辑
      ElMessage.success('批量支付成功')
      batchPaymentDialogVisible.value = false
      await loadReadings()
      await loadRooms()
    } catch (error) {
      console.error('Failed to submit batch payment:', error)
      ElMessage.error('批量支付失败')
    } finally {
      batchPaymentLoading.value = false
    }
  }

  // 批量生成消息
  const generateBatchMessages = async (roomIds: number[]) => {
    try {
      const messages: string[] = []

      for (const roomId of roomIds) {
        // TODO: 获取房间的水电读数
        const readings: any[] = []
        const message = await generateMessageText(roomId, readings)
        messages.push(message)
      }

      // 合并所有消息
      const combinedMessage = messages.join('\n\n---\n\n')
      showCopyFallback(combinedMessage)
    } catch (error) {
      console.error('Failed to generate batch messages:', error)
      ElMessage.error('生成批量消息失败')
    }
  }

  return {
    batchDialogVisible,
    batchLoading,
    batchSelectedRooms,
    showBatchDialog,
    submitBatchEntry,

    batchPaymentDialogVisible,
    batchPaymentLoading,
    batchPaymentSelectedRooms,
    showBatchPaymentDialog,
    submitBatchPayment,

    generateBatchMessages,
  }
}
