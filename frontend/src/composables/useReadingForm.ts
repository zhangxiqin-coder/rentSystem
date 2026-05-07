import { ref, type Ref } from 'vue'
import { utilityApi } from '@/api/utility'
import { mergeReadings, type MergedReading } from '@/composables/useMergedReadings'
import type { Room } from '@/types'

export function useReadingForm(deps: {
  roomOptions: Ref<Room[]>
  getRoomNumber: (roomId: number) => string
  getRoomInfo: (roomId: number, field: keyof Room) => any
  hideAmounts: Ref<boolean>
  formatAmount: (value: number, currency?: string) => string
  loadReadings: () => Promise<void>
  generateRentReminder: (merged: MergedReading) => string
  autoGenerateAndSendWechat: (merged: MergedReading) => Promise<void>
}) {
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

  const showFormDialog = ref(false)
  const formSuccess = ref(false)
  const selectedRoomId = ref<number | undefined>(undefined)

  // 打开录入水电对话框（可传入固定房间ID）
  const openUtilityForm = (roomId?: number) => {
    selectedRoomId.value = roomId
    showFormDialog.value = true
  }

  // 显示录入表单
  const showAddForm = () => {
    openUtilityForm() // 不传roomId，让用户自由选择
  }

  // 表单成功回调
  const handleFormSuccess = async (result: any) => {
    formSuccess.value = true
    showFormDialog.value = false
    selectedRoomId.value = undefined
    await loadReadings()

    // 生成催租消息预览
    setTimeout(async () => {
      try {
        const readings = await utilityApi.getReadingsByRoom(result.room_id, {
          page: 1,
          size: 10,
        })

        // 找到对应日期的记录
        const mergedList = mergeReadings(readings.data.items || [], roomOptions.value)
        const merged = mergedList.find(m => m.reading_date === result.reading_date)

        if (merged) {
          // 生成催租消息预览（使用外部的 rentReminderPreview / rentReminderVisible）
          // 这里通过回调方式返回 merged 对象供调用者处理
          return merged
        }
      } catch (error) {
        console.error('Failed to generate rent reminder:', error)
      }
      return null
    }, 500)
  }

  // 带催租预览的表单成功回调
  const handleFormSuccessWithReminder = async (
    result: any,
    callbacks: {
      setRentReminderPreview: (value: string) => void
      setRentReminderVisible: (value: boolean) => void
    }
  ) => {
    formSuccess.value = true
    showFormDialog.value = false
    selectedRoomId.value = undefined
    await loadReadings()

    // 生成催租消息预览
    setTimeout(async () => {
      try {
        const readings = await utilityApi.getReadingsByRoom(result.room_id, {
          page: 1,
          size: 10,
        })

        // 找到对应日期的记录
        const mergedList = mergeReadings(readings.data.items || [], roomOptions.value)
        const merged = mergedList.find(m => m.reading_date === result.reading_date)

        if (merged) {
          // 生成催租消息预览
          const reminder = generateRentReminder(merged)
          callbacks.setRentReminderPreview(reminder)
          callbacks.setRentReminderVisible(true)

          // 同时也发送微信消息（原有功能）
          await autoGenerateAndSendWechat(merged)
        }
      } catch (error) {
        console.error('Failed to generate rent reminder:', error)
      }
    }, 500)
  }

  return {
    showFormDialog,
    formSuccess,
    selectedRoomId,
    openUtilityForm,
    showAddForm,
    handleFormSuccess,
    handleFormSuccessWithReminder,
  }
}
