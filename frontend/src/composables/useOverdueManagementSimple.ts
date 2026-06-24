import { ref, computed, onMounted } from 'vue'
import { remindersApi, type OverdueRoom } from '@/api/reminders'
import { ElMessage } from 'element-plus'

/**
 * 简化的逾期管理 Composable
 * 直接从后端API获取数据,不再本地重复计算
 */
export function useOverdueManagementSimple() {
  const overdueRooms = ref<OverdueRoom[]>([])
  const expiringRooms = ref<OverdueRoom[]>([])
  const loading = ref(false)
  const advanceRentDays = ref(0)

  // 加载逾期房间数据
  const loadOverdueRooms = async () => {
    loading.value = true
    try {
      const response = await remindersApi.getOverdueRooms({
        advance_rent_days: advanceRentDays.value,
      })
      
      if (response.data) {
        overdueRooms.value = response.data.overdue || []
        expiringRooms.value = response.data.expiring || []
      }
    } catch (error) {
      console.error('Failed to load overdue rooms:', error)
      ElMessage.error('加载逾期房间失败')
    } finally {
      loading.value = false
    }
  }

  // 刷新数据
  const refresh = () => {
    loadOverdueRooms()
  }

  // 设置提前收租天数并重新加载
  const setAdvanceRentDays = (days: number) => {
    advanceRentDays.value = days
    loadOverdueRooms()
  }

  // 发送催租消息(需要配合其他composable使用)
  const sendReminder = async (room: OverdueRoom, type: 'overdue' | 'upcoming') => {
    // TODO: 这里可以集成消息生成功能
    // 目前简化处理,只显示提示
    const message = type === 'overdue'
      ? `${room.room_number} 已逾期${room.overdue_days || 0}天,欠费¥${room.total_amount.toFixed(2)}`
      : `${room.room_number} ${room.days_until_due}天后到期,应付¥${room.total_amount.toFixed(2)}`
    
    ElMessage.info(message)
    // 实际使用时可以调用 useMessageGeneration 生成详细消息
  }

  // 标记即将到期房间为已支付
  const markExpiringRoomPaid = (room: OverdueRoom) => {
    // TODO: 打开支付对话框
    ElMessage.info(`打开 ${room.room_number} 的支付对话框`)
  }

  // 判断是否可以标记为已支付
  const canMarkExpiringRoomPaid = (room: OverdueRoom) => {
    // 简化逻辑:有水电费就可以标记
    return room.utility_amount > 0
  }

  // 获取距离到期天数(兼容旧接口)
  const getNextPaymentDays = (room: OverdueRoom) => {
    return room.days_to_due
  }

  // 自动加载数据
  onMounted(() => {
    loadOverdueRooms()
  })

  return {
    // 数据
    overdueRooms,
    expiringRooms,
    loading,
    advanceRentDays,
    
    // 方法
    loadOverdueRooms,
    refresh,
    setAdvanceRentDays,
    sendReminder,
    markExpiringRoomPaid,
    canMarkExpiringRoomPaid,
    getNextPaymentDays,
  }
}
