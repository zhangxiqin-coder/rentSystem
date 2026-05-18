import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { utilityApi } from '@/api/utility'
import { roomApi } from '@/api/room'
import type { Room, UtilityReading } from '@/types'

interface UseMessageGenerationDeps {
  getRoomNumber: (roomId: number) => string
  getRoomInfo: (roomId: number) => Room | undefined
  hideAmounts: Ref<boolean>
  formatAmount: (value: number, currency?: string) => string
  formatAmountForNotification: (value: number, currency?: string) => string
}

export function useMessageGeneration(deps: UseMessageGenerationDeps) {
  const {
    getRoomNumber,
    getRoomInfo,
    hideAmounts,
    formatAmount,
    formatAmountForNotification,
  } = deps

  // 消息对话框状态
  const messageDialogVisible = ref(false)
  const currentMessage = ref('')
  const sendingWechat = ref(false)

  // 收租提醒相关
  const rentReminderPreview = ref('')
  const rentReminderVisible = ref(false)

  // 生成收租提醒消息
  const generateRentReminder = async (roomId: number, readings: UtilityReading[], forceShowAmount = false): Promise<string> => {
    let room = getRoomInfo(roomId)

    // 如果缓存中没有找到房间，尝试从API重新获取
    if (!room) {
      try {
        const response = await roomApi.getRoom(roomId)
        room = response.data
      } catch (error) {
        console.error('Failed to fetch room info:', error)
        ElMessage.error('房间信息不存在')
        return ''
      }
    }

    const roomNumber = getRoomNumber(roomId)

    // 获取抄表日期（使用第一条读数的日期）
    const readingDate = readings.length > 0
      ? new Date(readings[0].reading_date).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\//g, '/')
      : new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\//g, '/')

    // 根据forceShowAmount参数选择合适的格式化函数
    const formatter = forceShowAmount ? formatAmountForNotification : formatAmount

    let totalAmount = 0
    let waterText = ''
    let electricityText = ''

    readings.forEach(reading => {
      if (reading.utility_type === 'water') {
        const usage = reading.reading - (reading.previous_reading || 0)
        const cost = Number(reading.amount || 0)
        const rate = Number(room.water_rate || 5)
        // forceShowAmount=true 时忽略 hideAmounts，始终显示真实金额
        const costText = (forceShowAmount || !hideAmounts.value) ? formatter(cost) : '****'
        const rateText = (forceShowAmount || !hideAmounts.value) ? rate.toFixed(2) : '**'
        waterText = `💧 水费：${reading.previous_reading || 0}→${reading.reading}（用量${usage}吨 × ¥${rateText}/吨 = ${costText}）`
        totalAmount += cost
      } else if (reading.utility_type === 'electricity') {
        const usage = reading.reading - (reading.previous_reading || 0)
        const cost = Number(reading.amount || 0)
        const rate = Number(room.electricity_rate || 1)
        // forceShowAmount=true 时忽略 hideAmounts，始终显示真实金额
        const costText = (forceShowAmount || !hideAmounts.value) ? formatter(cost) : '****'
        const rateText = (forceShowAmount || !hideAmounts.value) ? rate.toFixed(2) : '**'
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
    message += `💰 合计：${(forceShowAmount || !hideAmounts.value) ? formatter(totalAmount) : '****'}\n`
    message += `🏠 房租：${(forceShowAmount || !hideAmounts.value) ? formatter(rentAmount) : '****'}\n`
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
    // 显示收租提醒对话框时，强制显示真实金额，不受隐藏金额开关影响
    await generateRentReminder(roomId, readings, true)
    rentReminderVisible.value = true
  }

  // 复制收租提醒（带降级方案）
  const copyRentReminder = () => {
    // 先尝试使用现代 Clipboard API
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(rentReminderPreview.value)
        .then(() => ElMessage.success('已复制到剪贴板'))
        .catch(() => fallbackCopy(rentReminderPreview.value))
    } else {
      // 降级到传统方法
      fallbackCopy(rentReminderPreview.value)
    }
  }

  // 自动生成并发送微信通知
  const autoGenerateAndSendWechat = async (roomId: number, readings: UtilityReading[]) => {
    sendingWechat.value = true
    try {
      // 发送微信通知时，强制显示真实金额，不受隐藏金额开关影响
      const message = await generateRentReminder(roomId, readings, true)

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

  // 生成消息文本（通用，用于复制发送）
  const generateMessageText = async (roomId: number, readings: UtilityReading[]): Promise<string> => {
    // 生成消息文本时，强制显示真实金额，不受隐藏金额开关影响
    return await generateRentReminder(roomId, readings, true)
  }

  // 复制消息（带降级方案）
  const copyMessage = (message: string) => {
    // 先尝试使用现代 Clipboard API
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(message)
        .then(() => ElMessage.success('已复制到剪贴板'))
        .catch(() => fallbackCopy(message))
    } else {
      // 降级到传统方法
      fallbackCopy(message)
    }
  }

  // 降级复制方法
  const fallbackCopy = (message: string) => {
    const textArea = document.createElement('textarea')
    textArea.value = message
    textArea.style.position = 'fixed'
    textArea.style.left = '-999999px'
    textArea.style.top = '-999999px'
    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()
    
    try {
      const successful = document.execCommand('copy')
      if (successful) {
        ElMessage.success('已复制到剪贴板')
      } else {
        ElMessage.error('复制失败，请手动复制')
      }
    } catch (err) {
      ElMessage.error('复制失败，请手动复制')
    }
    
    document.body.removeChild(textArea)
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
