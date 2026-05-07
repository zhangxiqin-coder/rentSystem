import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { utilityApi } from '@/api/utility'
import type { Room, UtilityReading } from '@/types'

interface UseMessageGenerationDeps {
  getRoomNumber: (roomId: number) => string
  getRoomInfo: (roomId: number) => Room | undefined
  hideAmounts: Ref<boolean>
  formatAmount: (value: number, currency?: string) => string
}

export function useMessageGeneration(deps: UseMessageGenerationDeps) {
  const {
    getRoomNumber,
    getRoomInfo,
    hideAmounts,
    formatAmount,
  } = deps

  // 消息对话框状态
  const messageDialogVisible = ref(false)
  const currentMessage = ref('')
  const sendingWechat = ref(false)

  // 收租提醒相关
  const rentReminderPreview = ref('')
  const rentReminderVisible = ref(false)

  // 生成收租提醒消息
  const generateRentReminder = async (roomId: number, readings: UtilityReading[]): Promise<string> => {
    const room = getRoomInfo(roomId)
    if (!room) {
      ElMessage.error('房间信息不存在')
      return ''
    }

    const roomNumber = getRoomNumber(roomId)
    
    // 获取抄表日期（使用第一条读数的日期）
    const readingDate = readings.length > 0 
      ? new Date(readings[0].reading_date).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\//g, '/')
      : new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\//g, '/')

    let totalAmount = 0
    let waterText = ''
    let electricityText = ''

    readings.forEach(reading => {
      if (reading.utility_type === 'water') {
        const usage = reading.reading - (reading.previous_reading || 0)
        const cost = Number(reading.amount || 0)
        const rate = Number(room.water_rate || 5)
        const costText = hideAmounts.value ? '****' : formatAmount(cost)
        const rateText = hideAmounts.value ? '**' : rate.toFixed(2)
        waterText = `💧 水费：${reading.previous_reading || 0}→${reading.reading}（用量${usage}吨 × ¥${rateText}/吨 = ${costText}）`
        totalAmount += cost
      } else if (reading.utility_type === 'electricity') {
        const usage = reading.reading - (reading.previous_reading || 0)
        const cost = Number(reading.amount || 0)
        const rate = Number(room.electricity_rate || 1)
        const costText = hideAmounts.value ? '****' : formatAmount(cost)
        const rateText = hideAmounts.value ? '**' : rate.toFixed(2)
        electricityText = `⚡ 电费：${reading.previous_reading || 0}→${reading.reading}（用量${usage}度 × ¥${rateText}/度 = ${costText}）`
        totalAmount += cost
      }
    })

    // 添加房租
    const cycle = Math.max(1, Number(room.payment_cycle || 1))
    const rentAmount = Number(room.monthly_rent || 0) * cycle
    totalAmount += rentAmount
    
    // 构建消息
    let message = `【${roomNumber} 收租明细】\n`
    message += `抄表日期：${readingDate}\n`
    message += `💰 合计：${hideAmounts.value ? '****' : formatAmount(totalAmount)}\n`
    message += `🏠 房租：${hideAmounts.value ? '****' : formatAmount(rentAmount)}\n`
    if (waterText) message += `${waterText}\n`
    if (electricityText) message += `${electricityText}\n`
    
    // 移除最后一个换行符
    message = message.trim()

    currentMessage.value = message
    rentReminderPreview.value = message
    return message
  }

  // 显示收租提醒对话框
  const showRentReminder = async (roomId: number, readings: UtilityReading[]) => {
    await generateRentReminder(roomId, readings)
    rentReminderVisible.value = true
  }

  // 复制收租提醒
  const copyRentReminder = () => {
    navigator.clipboard.writeText(rentReminderPreview.value)
      .then(() => ElMessage.success('已复制到剪贴板'))
      .catch(() => ElMessage.error('复制失败'))
  }

  // 自动生成并发送微信通知
  const autoGenerateAndSendWechat = async (roomId: number, readings: UtilityReading[]) => {
    sendingWechat.value = true
    try {
      const message = await generateRentReminder(roomId, readings)

      // 调用后端API发送微信通知
      await utilityApi.sendWechatNotification({
        room_id: roomId,
        message,
      })

      ElMessage.success('微信通知已发送')
    } catch (error) {
      console.error('Failed to send wechat notification:', error)
      ElMessage.error('发送微信通知失败')
    } finally {
      sendingWechat.value = false
    }
  }

  // 生成消息文本（通用）
  const generateMessageText = async (roomId: number, readings: UtilityReading[]): Promise<string> => {
    return await generateRentReminder(roomId, readings)
  }

  // 复制消息
  const copyMessage = (message: string) => {
    navigator.clipboard.writeText(message)
      .then(() => ElMessage.success('已复制到剪贴板'))
      .catch(() => ElMessage.error('复制失败，请手动复制'))
  }

  // 显示复制失败提示
  const showCopyFallback = (message: string) => {
    messageDialogVisible.value = true
    currentMessage.value = message
  }

  return {
    messageDialogVisible,
    currentMessage,
    sendingWechat,
    rentReminderPreview,
    rentReminderVisible,
    generateRentReminder,
    showRentReminder,
    copyRentReminder,
    autoGenerateAndSendWechat,
    generateMessageText,
    copyMessage,
    showCopyFallback,
  }
}
