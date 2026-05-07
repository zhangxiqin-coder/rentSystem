import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { Room } from '@/types'

interface UseReadingFormDeps {
  roomOptions: Ref<Room[]>
  getRoomNumber: (roomId: number) => string
  getRoomInfo: (roomId: number) => Room | undefined
  hideAmounts: Ref<boolean>
  formatAmount: (value: number, currency?: string) => string
  loadReadings: () => Promise<void>
  generateRentReminder: (roomId: number, readings: any[]) => Promise<string>
  autoGenerateAndSendWechat: (roomId: number, readings: any[]) => Promise<void>
}

export function useReadingForm(deps: UseReadingFormDeps) {
  const {
    roomOptions,
    getRoomNumber,
    getRoomInfo,
    hideAmounts,
    formatAmount,
    loadReadings,
    generateRentReminder,
    autoGenerateAndSendWechat,
  } = deps

  // 表单对话框显示状态
  const showFormDialog = ref(false)
  const formSuccess = ref(false)
  const selectedRoomId = ref<number>()

  // 打开水电录入表单
  const openUtilityForm = (roomId?: number) => {
    selectedRoomId.value = roomId
    showFormDialog.value = true
    formSuccess.value = false
  }

  // 显示添加表单
  const showAddForm = () => {
    selectedRoomId.value = undefined
    showFormDialog.value = true
    formSuccess.value = false
  }

  // 表单成功后的处理（带收租提醒）
  const handleFormSuccessWithReminder = async (roomId: number, readings: any[]) => {
    formSuccess.value = true

    // 刷新列表
    await loadReadings()

    // 生成并显示收租提醒
    try {
      await generateRentReminder(roomId, readings)
    } catch (error) {
      console.error('Failed to generate rent reminder:', error)
    }

    // 可选：自动发送微信通知
    // await autoGenerateAndSendWechat(roomId, readings)
  }

  return {
    showFormDialog,
    formSuccess,
    selectedRoomId,
    openUtilityForm,
    showAddForm,
    handleFormSuccessWithReminder,
  }
}
