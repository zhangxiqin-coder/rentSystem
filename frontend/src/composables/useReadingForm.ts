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
  const handleFormSuccessWithReminder = async (result: any, callbacks?: {
    setRentReminderPreview?: (value: string) => void
    setRentReminderVisible?: (value: boolean) => void
  }) => {
    formSuccess.value = true

    // 刷新列表
    await loadReadings()

    // 从 result 中提取 roomId 和构建 readings 数组
    const roomId = result.room_id
    const readings = [
      {
        utility_type: 'water',
        reading: result.water_reading,
        reading_date: result.reading_date,
        notes: result.notes
      },
      {
        utility_type: 'electricity',
        reading: result.electric_reading,
        reading_date: result.reading_date,
        notes: result.notes
      }
    ]

    // 生成并显示收租提醒（强制显示真实金额）
    try {
      const message = await generateRentReminder(roomId, readings, true)
      // 如果传入了回调，设置提醒预览和可见性
      if (callbacks?.setRentReminderPreview && callbacks?.setRentReminderVisible) {
        callbacks.setRentReminderPreview(message)
        callbacks.setRentReminderVisible(true)
      }
    } catch (error) {
      console.error('Failed to generate rent reminder:', error)
    }

    // 关闭弹窗，返回列表页
    showFormDialog.value = false

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
