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
  generateRentReminder: (roomId: number, readings: any[], forceShowAmount?: boolean) => Promise<string>
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

    // 刷新列表（加载最新的水电记录，包含 previous_reading 和 amount）
    await loadReadings()

    // 从 result 中提取 roomId
    const roomId = result.room_id
    const readingDate = result.reading_date

    // 等待一下，确保后端数据已完全写入和索引
    await new Promise(resolve => setTimeout(resolve, 100))

    // 从API重新获取该房间该日期的完整记录（包含 previous_reading 和 amount）
    let completeReadings: any[] = []
    try {
      // 查询该房间该日期的水电记录
      const { utilityApi } = await import('@/api/utility')
      const response = await utilityApi.getReadings({
        room_id: roomId,
        start_date: readingDate,
        end_date: readingDate,
        size: 10
      })

      // 提取水和电的完整记录
      const items = response.data.items || []
      const waterReading = items.find((r: any) => r.utility_type === 'water')
      const electricReading = items.find((r: any) => r.utility_type === 'electricity')

      if (waterReading) completeReadings.push(waterReading)
      if (electricReading) completeReadings.push(electricReading)

      console.log('查询到的完整水电记录:', completeReadings)
    } catch (error) {
      console.error('Failed to fetch complete readings:', error)
    }

    // 如果没找到完整记录，降级使用临时数据（至少有当前读数）
    if (completeReadings.length === 0) {
      console.warn('未找到完整记录，使用临时数据')
      completeReadings = [
        {
          utility_type: 'water',
          reading: result.water_reading,
          reading_date: result.reading_date,
          previous_reading: 0, // 临时数据没有上个月读数
          amount: 0, // 临时数据没有费用
          notes: result.notes
        },
        {
          utility_type: 'electricity',
          reading: result.electric_reading,
          reading_date: result.reading_date,
          previous_reading: 0,
          amount: 0,
          notes: result.notes
        }
      ]
    }

    // 生成并显示收租提醒（强制显示真实金额）
    try {
      const message = await generateRentReminder(roomId, completeReadings, true)
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
    // await autoGenerateAndSendWechat(roomId, completeReadings)
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
