import { ref, type Ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'
import type { MergedReading } from '@/composables/useMergedReadings'
import type { Room } from '@/types'

export function useMessageGeneration(deps: {
  getRoomNumber: (roomId: number) => string
  getRoomInfo: (roomId: number, field: keyof Room) => any
  hideAmounts: Ref<boolean>
  formatAmount: (value: number, currency?: string) => string
}) {
  const {
    getRoomNumber,
    getRoomInfo,
    hideAmounts,
    formatAmount,
  } = deps

  // 消息输出对话框
  const messageDialogVisible = ref(false)
  const currentMessage = ref('')
  const sendingWechat = ref(false)

  // 催租消息预览
  const rentReminderPreview = ref('')
  const rentReminderVisible = ref(false)

  // 生成催租消息文本（用于预览）
  const generateRentReminder = (merged: MergedReading): string => {
    const roomNumber = getRoomNumber(merged.room_id)
    const date = new Date(merged.reading_date).toLocaleDateString('zh-CN')

    const cycle = Math.max(1, Number(merged.payment_cycle || 1))
    const rentAmount = Number(merged.monthly_rent || 0) * cycle
    const rentLabel = cycle > 1 ? `房租（${cycle}个月）` : '房租'
    const waterAmount = Number(merged.water_reading?.amount || 0)
    const electricityAmount = Number(merged.electricity_reading?.amount || 0)
    const total = rentAmount + waterAmount + electricityAmount

    let message = `【${roomNumber} 收租明细】\n抄表日期：${date}\n\n💰 合计：${formatAmount(total)}\n`

    if (rentAmount > 0) {
      message += `🏠 ${rentLabel}：${formatAmount(rentAmount)}\n`
    }

    if (merged.water_reading) {
      const prev = Number(merged.water_reading.previous_reading || 0)
      const curr = Number(merged.water_reading.reading || 0)
      const usage = Number(merged.water_reading.usage ?? Math.max(0, curr - prev))
      const rate = Number(
        merged.water_reading.rate_used ?? getRoomInfo(merged.room_id, 'water_rate') ?? 0
      )
      const amount = Number(merged.water_reading.amount || 0)
      message += `💧 水费：${prev}→${curr}（用量${usage}吨 × ${hideAmounts.value ? '****/吨' : `¥${rate}/吨`} = ${formatAmount(amount)}）\n`
    }

    if (merged.electricity_reading) {
      const prev = Number(merged.electricity_reading.previous_reading || 0)
      const curr = Number(merged.electricity_reading.reading || 0)
      const usage = Number(merged.electricity_reading.usage ?? Math.max(0, curr - prev))
      const rate = Number(
        merged.electricity_reading.rate_used ?? getRoomInfo(merged.room_id, 'electricity_rate') ?? 0
      )
      const amount = Number(merged.electricity_reading.amount || 0)
      message += `⚡ 电费：${prev}→${curr}（用量${usage}度 × ${hideAmounts.value ? '****/度' : `¥${rate}/度`} = ${formatAmount(amount)}）\n`
    }

    return message
  }

  const showRentReminder = (row: MergedReading) => {
    rentReminderPreview.value = generateRentReminder(row)
    rentReminderVisible.value = true
  }

  // 复制催租消息到剪贴板
  const copyRentReminder = async () => {
    try {
      await navigator.clipboard.writeText(rentReminderPreview.value)
      ElMessage.success('已复制到剪贴板')
    } catch (error) {
      console.error('Failed to copy:', error)
      ElMessage.error('复制失败，请手动复制')
    }
  }

  const autoGenerateAndSendWechat = async (merged: MergedReading) => {
    try {
      // 生成消息
      const message = generateMessageText(merged)
      currentMessage.value = message
      messageDialogVisible.value = true

      // 注意：后端在水电录入时已经自动发送消息到飞书了
      // 这里只显示消息，不再重复调用后端API
      sendingWechat.value = true
      ElMessage.success('消息已自动生成并推送到飞书')
    } catch (error: any) {
      console.error('Failed to generate wechat message:', error)
      ElMessage.warning('消息生成失败')
    } finally {
      sendingWechat.value = false
    }
  }

  // 生成消息文本
  const generateMessageText = (merged: MergedReading): string => {
    const roomNumber = getRoomNumber(merged.room_id)
    const date = new Date(merged.reading_date).toLocaleDateString('zh-CN')
    const cycle = Math.max(1, Number(merged.payment_cycle || 1))
    const rentDue = Number(merged.monthly_rent || 0) * cycle
    const rentLabel = cycle > 1 ? `房租（${cycle}个月）` : '房租'

    let message = `【收租通知】\n房间：${roomNumber}\n抄表日期：${date}\n`

    if (rentDue > 0) {
      message += `\n🏠 ${rentLabel}：${formatAmount(rentDue)}\n`
    }

    if (merged.water_reading) {
      message += `\n💧 水费：\n`
      message += `  上次读数：${merged.water_reading.previous_reading} 吨\n`
      message += `  本次读数：${merged.water_reading.reading} 吨\n`
      message += `  用量：${merged.water_reading.usage} 吨\n`
      message += `  费用：${formatAmount(Number(merged.water_reading.amount || 0))}\n`
    }

    if (merged.electricity_reading) {
      message += `\n⚡ 电费：\n`
      message += `  上次读数：${merged.electricity_reading.previous_reading} 度\n`
      message += `  本次读数：${merged.electricity_reading.reading} 度\n`
      message += `  用量：${merged.electricity_reading.usage} 度\n`
      message += `  费用：${formatAmount(Number(merged.electricity_reading.amount || 0))}\n`
    }

    message += `\n💰 应付总额：${formatAmount(merged.total_amount)}`

    if (merged.notes) {
      message += `\n\n备注：${merged.notes}`
    }

    message += `\n\n请及时缴纳费用，谢谢！\n${'='.repeat(30)}\n`

    return message
  }

  // 发送微信通知（调用后端API）
  const sendWechatNotification = async (merged: MergedReading, message: string) => {
    // 调用后端API发送微信通知
    const payload = {
      room_id: merged.room_id,
      reading_date: merged.reading_date,
      message,
    }

    await request({
      method: 'POST',
      url: '/api/v1/utility/send-wechat-notification',
      data: payload,
    })
  }

  // 复制消息到剪贴板
  const copyMessage = () => {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(currentMessage.value)
      ElMessage.success('消息已复制到剪贴板')
    } else {
      ElMessage.warning('自动复制失败，请手动复制')
    }
  }

  // Fallback：显示消息内容并提供复制提示
  const showCopyFallback = (message: string) => {
    // 创建一个临时文本框来复制
    const textArea = document.createElement('textarea')
    textArea.value = message
    textArea.style.position = 'fixed'
    textArea.style.left = '-9999px'
    document.body.appendChild(textArea)
    textArea.select()

    try {
      const successful = document.execCommand('copy')
      document.body.removeChild(textArea)

      if (successful) {
        ElMessage.success('微信消息已复制到剪贴板')
      } else {
        throw new Error('Copy failed')
      }
    } catch (err) {
      document.body.removeChild(textArea)
      ElMessage.warning('自动复制失败，请手动复制以下内容：')
      console.log('Generated message:', message)

      // 显示消息内容对话框
      ElMessageBox.alert(
        message,
        '水电费通知消息',
        {
          confirmButtonText: '关闭',
          type: 'info',
        }
      )
    }
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
    sendWechatNotification,
    copyMessage,
    showCopyFallback,
  }
}
