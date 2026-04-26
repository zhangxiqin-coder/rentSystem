<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { utilityApi } from '@/api/utility'
import { roomApi } from '@/api/room'
import { paymentApi } from '@/api/payment'
import UtilityReadingForm from '@/components/UtilityReadingForm.vue'
import type { UtilityReading, Room } from '@/types'
import axios from 'axios'

// 活动标签页
const activeTab = ref('readings')

// 水电记录列表（原始数据）
const readings = ref<UtilityReading[]>([])
const loading = ref(false)

// 支付记录（用于判断是否已收租）
const payments = ref<Payment[]>([])

// 即将到期的房间
const expiringRooms = ref<Room[]>([])

// 所有房间（用于计算欠租）
const allRooms = ref<Room[]>([])

// 欠租房间
const overdueRooms = computed(() => {
  const overdue: Array<{
    room: Room
    overdueDays: number
    overdueAmount: number
    lastPaymentDate: string
    nextPaymentDate: string
  }> = []

  allRooms.value.forEach(room => {
    const nextPaymentDate = getNextPaymentDate(room)
    const nextPaymentDays = getNextPaymentDays(room)

    // 如果下次收租日期是今天或之前，说明欠租
    if (nextPaymentDays <= 0) {
      const overdueDays = Math.abs(nextPaymentDays)
      const lastPaymentDate = room.last_payment_date || room.lease_start

      // 计算欠租金额（房租 + 估算的水电费）
      const overdueAmount = room.monthly_rent + 100 // 估算水电费100元

      overdue.push({
        room,
        overdueDays,
        overdueAmount,
        lastPaymentDate: formatDate(lastPaymentDate),
        nextPaymentDate: formatDate(nextPaymentDate)
      })
    }
  })

  // 按欠租天数排序（天数越多越靠前）
  return overdue.sort((a, b) => b.overdueDays - a.overdueDays)
})

// 收租对话框
const paymentDialogVisible = ref(false)
const paymentForm = ref({
  room_id: 0,
  reading_date: '',
  rent_original: 0,
  rent_amount: 0,
  water_original: 0,
  water_amount: 0,
  electricity_original: 0,
  electricity_amount: 0,
  payment_method: '现金',
  notes: ''
})
const paymentLoading = ref(false)

// 编辑对话框
const editDialogVisible = ref(false)
const editLoading = ref(false)
const editForm = ref({
  water_reading_id: null as number | null,
  electricity_reading_id: null as number | null,
  water_reading: 0,
  electricity_reading: 0,
  notes: '',
})
const editOriginalData = ref<MergedReading | null>(null)

// 消息输出对话框
const messageDialogVisible = ref(false)
const currentMessage = ref('')
const sendingWechat = ref(false)

// 批量录入对话框
const batchDialogVisible = ref(false)
const batchLoading = ref(false)
const selectedRooms = ref<number[]>([])
const batchForm = ref({
  reading_date: new Date().toISOString().split('T')[0], // 默认今天
  utility_type: 'both', // 默认水电全录
  notes: ''
})

// 扩展Room类型，添加临时读数字段
declare module '@/types' {
  interface Room {
    water_reading?: number
    electricity_reading?: number
  }
}

// 显示批量录入表单
const showBatchForm = () => {
  // 清空之前的选择
  selectedRooms.value = []
  // 重置所有房间的读数
  allRooms.value.forEach(room => {
    room.water_reading = 0
    room.electricity_reading = 0
  })
  batchDialogVisible.value = true
}

// 全选房间
const selectAllRooms = () => {
  selectedRooms.value = allRooms.value.map(r => r.id)
}

// 清空选择
const clearRoomSelection = () => {
  selectedRooms.value = []
}

// 仅选择已租房间
const selectOccupiedRooms = () => {
  selectedRooms.value = allRooms.value
    .filter(r => r.status === 'occupied')
    .map(r => r.id)
}

// 计算总记录数
const calculateTotalRecords = () => {
  const roomCount = selectedRooms.value.length
  if (batchForm.value.utility_type === 'both') {
    return roomCount * 2
  }
  return roomCount
}

// 提交批量录入
const submitBatch = async () => {
  if (selectedRooms.value.length === 0) {
    ElMessage.warning('请至少选择一个房间')
    return
  }

  batchLoading.value = true
  try {
    // 构建批量数据
    const readings: any[] = []

    selectedRooms.value.forEach(roomId => {
      const room = allRooms.value.find(r => r.id === roomId)
      if (!room) return

      // 水费读数
      if ((batchForm.value.utility_type === 'water' || batchForm.value.utility_type === 'both') && room.water_reading > 0) {
        readings.push({
          room_id: roomId,
          utility_type: 'water',
          reading: room.water_reading
        })
      }

      // 电费读数
      if ((batchForm.value.utility_type === 'electricity' || batchForm.value.utility_type === 'both') && room.electricity_reading > 0) {
        readings.push({
          room_id: roomId,
          utility_type: 'electricity',
          reading: room.electricity_reading
        })
      }
    })

    if (readings.length === 0) {
      ElMessage.warning('请至少录入一条读数')
      batchLoading.value = false
      return
    }

    // 调用批量API
    const result = await utilityApi.batchCreate({
      readings,
      reading_date: batchForm.value.reading_date,
      notes: batchForm.value.notes
    })

    // 显示结果
    if (result.failed_count > 0) {
      ElMessage.warning(`成功 ${result.success_count} 条，失败 ${result.failed_count} 条`)
      if (result.errors.length > 0) {
        console.error('批量录入错误:', result.errors)
      }
    } else {
      ElMessage.success(`批量录入成功！共 ${result.success_count} 条记录，总金额 ¥${result.total_amount}`)
    }

    // 关闭对话框并刷新列表
    batchDialogVisible.value = false
    loadReadings()
    loadPayments() // 刷新支付记录

  } catch (error: any) {
    console.error('批量录入失败:', error)
    ElMessage.error(error.response?.data?.detail || '批量录入失败')
  } finally {
    batchLoading.value = false
  }
}

// 自动生成并发送微信消息
const autoGenerateAndSendWechat = async (merged: MergedReading) => {
  try {
    // 生成消息
    const message = generateMessageText(merged)
    currentMessage.value = message
    messageDialogVisible.value = true

    // 自动推送到微信
    sendingWechat.value = true
    await sendWechatNotification(merged, message)
    ElMessage.success('微信消息已自动推送')
  } catch (error: any) {
    console.error('Failed to send wechat notification:', error)
    ElMessage.warning('消息已生成，但微信推送失败')
  } finally {
    sendingWechat.value = false
  }
}

// 生成消息文本
const generateMessageText = (merged: MergedReading): string => {
  const roomNumber = getRoomNumber(merged.room_id)
  const date = new Date(merged.reading_date).toLocaleDateString('zh-CN')

  let message = `【收租通知】\n房间：${roomNumber}\n抄表日期：${date}\n`

  if (merged.monthly_rent) {
    message += `\n🏠 房租：¥${merged.monthly_rent.toFixed(2)}\n`
  }

  if (merged.water_reading) {
    message += `\n💧 水费：\n`
    message += `  上次读数：${merged.water_reading.previous_reading} 吨\n`
    message += `  本次读数：${merged.water_reading.reading} 吨\n`
    message += `  用量：${merged.water_reading.usage} 吨\n`
    message += `  费用：¥${(merged.water_reading.amount || 0).toFixed(2)}\n`
  }

  if (merged.electricity_reading) {
    message += `\n⚡ 电费：\n`
    message += `  上次读数：${merged.electricity_reading.previous_reading} 度\n`
    message += `  本次读数：${merged.electricity_reading.reading} 度\n`
    message += `  用量：${merged.electricity_reading.usage} 度\n`
    message += `  费用：¥${(merged.electricity_reading.amount || 0).toFixed(2)}\n`
  }

  message += `\n💰 应付总额：¥${merged.total_amount.toFixed(2)}`

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

  await utilityApi.request({
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

// 合并水和电的记录（用于自动发送微信）
const mergeReadings = (readings: UtilityReading[]): MergedReading[] => {
  const map = new Map<string, MergedReading>()

  readings.forEach(reading => {
    const key = `${reading.room_id}_${reading.reading_date}`

    if (!map.has(key)) {
      const room = roomOptions.value.find(r => r.id === reading.room_id)
      map.set(key, {
        room_id: reading.room_id,
        reading_date: reading.reading_date,
        water_reading: reading.utility_type === 'water' ? reading : undefined,
        electricity_reading: reading.utility_type === 'electricity' ? reading : undefined,
        monthly_rent: room?.monthly_rent,
        total_amount: 0,
        notes: '',
      })
    } else {
      const merged = map.get(key)!
      if (reading.utility_type === 'water') {
        merged.water_reading = reading
      } else if (reading.utility_type === 'electricity') {
        merged.electricity_reading = reading
      }
    }
  })

  // 计算总费用
  Array.from(map.values()).forEach(merged => {
    let total = merged.monthly_rent || 0

    if (merged.water_reading) {
      total += merged.water_reading.amount || 0
    }

    if (merged.electricity_reading) {
      total += merged.electricity_reading.amount || 0
    }

    merged.total_amount = total
    merged.notes = merged.water_reading?.notes || merged.electricity_reading?.notes || ''
  })

  return Array.from(map.values()).sort((a, b) =>
    new Date(b.reading_date).getTime() - new Date(a.reading_date).getTime()
  )
}

// 批量选择
const tableRef = ref()
const selectedRows = ref<MergedReading[]>([])

// 批量收租对话框
const batchPaymentDialogVisible = ref(false)
const batchPaymentLoading = ref(false)
const batchPayments = ref<Array<{
  room_id: number
  reading_date: string
  rent_original: number
  rent_amount: number
  water_original: number
  water_amount: number
  electricity_original: number
  electricity_amount: number
  payment_method: string
  notes: string
}>>([])

// 计算是否可以批量收租（所有选中行都必须有水电数据）
const canBatchPay = computed(() => {
  return selectedRows.value.length > 0 &&
    selectedRows.value.every(row => row.water_reading || row.electricity_reading)
})

// 合并后的记录列表（水和电在同一行）
interface MergedReading {
  room_id: number
  reading_date: string
  water_reading?: UtilityReading
  electricity_reading?: UtilityReading
  monthly_rent?: number  // 月租金
  total_amount: number
  notes: string
  is_paid?: boolean  // 是否已收租
}

const mergedReadings = computed(() => {
  const map = new Map<string, MergedReading>()

  readings.value.forEach(reading => {
    const key = `${reading.room_id}_${reading.reading_date}`
    
    if (!map.has(key)) {
      // 获取房间信息（包含房租）
      const room = roomOptions.value.find(r => r.id === reading.room_id)
      map.set(key, {
        room_id: reading.room_id,
        reading_date: reading.reading_date,
        monthly_rent: room?.monthly_rent,
        total_amount: Number(room?.monthly_rent || 0),  // 总计包含房租，确保是数字
        notes: reading.notes || ''
      })
    }

    const merged = map.get(key)!
    
    if (reading.utility_type === 'water') {
      merged.water_reading = reading
    } else if (reading.utility_type === 'electricity') {
      merged.electricity_reading = reading
    }
    
    // 累加水电费到总计（房租已在初始化时添加）
    merged.total_amount += Number(reading.amount || 0)
    if (reading.notes) {
      merged.notes = merged.notes ? `${merged.notes}; ${reading.notes}` : reading.notes
    }
  })

  // 检查每条记录是否已收租
  const result = Array.from(map.values())
  result.forEach(merged => {
    // 查找对应的支付记录（同房间、同月份）
    const hasPayment = payments.value.some(p => 
      p.room_id === merged.room_id && 
      p.payment_date.startsWith(merged.reading_date.substring(0, 7))  // 比较年月
    )
    merged.is_paid = hasPayment
  })

  return result.sort((a, b) => 
    new Date(b.reading_date).getTime() - new Date(a.reading_date).getTime()
  )
})

// 房间选项（用于筛选）
const roomOptions = ref<Room[]>([])
const roomsLoading = ref(false)

// 房间信息映射（用于显示房间号）
const roomMap = computed(() => {
  const map = new Map<number, Room>()
  roomOptions.value.forEach(room => {
    map.set(room.id, room)
  })
  return map
})

// 分页
const pagination = ref({
  page: 1,
  size: 20,
  total: 0,
})

// 筛选条件
const filters = ref({
  room_id: undefined as number | undefined,
  start_date: '',
  end_date: '',
})

// 表单对话框
const showFormDialog = ref(false)
const formSuccess = ref(false)
const selectedRoomId = ref<number | undefined>(undefined)

// 打开录入水电对话框（可传入固定房间ID）
const openUtilityForm = (roomId?: number) => {
  selectedRoomId.value = roomId
  showFormDialog.value = true
}

// 加载水电记录列表
const loadReadings = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pagination.value.page,
      size: pagination.value.size,
    }

    if (filters.value.room_id) {
      params.room_id = filters.value.room_id
    }
    if (filters.value.start_date) {
      params.start_date = filters.value.start_date
    }
    if (filters.value.end_date) {
      params.end_date = filters.value.end_date
    }

    const res = await utilityApi.getReadings(params)
    readings.value = res.data.items || []
    pagination.value.total = res.data.total || 0
    
    // 同时加载支付记录，用于判断是否已收租
    const paymentsRes = await paymentApi.getPayments({ size: 1000 })
    payments.value = paymentsRes.data.items || []
  } catch (error) {
    console.error('Failed to load readings:', error)
    ElMessage.error('加载水电记录失败')
  } finally {
    loading.value = false
  }
}

// 加载房间列表（用于筛选和显示房间号）
const loadRooms = async () => {
  roomsLoading.value = true
  try {
    // 后端API限制size最大为100，需要分页加载
    let allRooms: Room[] = []
    let page = 1
    let hasMore = true
    
    while (hasMore) {
      const res = await roomApi.getRooms({ page, size: 100 })
      const items = res.data.items || []
      allRooms = [...allRooms, ...items]
      
      // 如果返回的数据少于100条，说明没有更多数据了
      hasMore = items.length === 100
      page++
    }
    
    roomOptions.value = allRooms
    allRooms.value = allRooms // 设置所有房间，用于计算欠租
  } catch (error) {
    console.error('Failed to load rooms:', error)
    ElMessage.error('加载房间列表失败')
  } finally {
    roomsLoading.value = false
  }
}

// 加载即将到期的房间
const loadExpiringRooms = async () => {
  try {
    const response = await roomApi.getExpiringSoon(7)
    expiringRooms.value = response.data || []
  } catch (error) {
    console.error('Failed to load expiring rooms:', error)
    // 静默失败，不显示错误消息
  }
}

// 计算距离到期天数
const getDaysDiff = (leaseEnd: string) => {
  const today = new Date()
  const endDate = new Date(leaseEnd)
  const diff = Math.ceil((endDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
  return Math.max(0, diff)
}

// 格式化日期
const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

// 一键催租
const sendReminder = async (room: Room, type: 'overdue' | 'upcoming') => {
  try {
    const today = new Date().toLocaleDateString('zh-CN')
    const nextPaymentDate = formatDate(getNextPaymentDate(room))
    const days = getNextPaymentDays(room)

    let message = ''

    if (type === 'overdue') {
      const overdueDays = Math.abs(days)
      message = `【欠租催缴通知】

亲爱的${room.room_number}租客：

您好！温馨提醒您，您的房租已逾期${overdueDays}天。

📋 租赁信息：
• 房间号：${room.room_number}
• 房租金额：¥${room.monthly_rent}/月
• 收租周期：${room.payment_cycle === 1 ? '月付' : room.payment_cycle === 3 ? '季付' : '年付'}
• 上次交租：${room.last_payment_date ? formatDate(room.last_payment_date) : '未知'}
• 应交日期：${nextPaymentDate}
• 逾期天数：${overdueDays}天
• 欠租金额：约¥${room.monthly_rent + 100}

请您尽快支付房租，避免产生更多滞纳金。如有特殊情况，请及时与我们联系。

感谢您的配合！🙏`
    } else {
      message = `【收租温馨提醒】

亲爱的${room.room_number}租客：

您好！温馨提醒您，下次收租日期即将到来。

📋 租赁信息：
• 房间号：${room.room_number}
• 房租金额：¥${room.monthly_rent}/月
• 收租周期：${room.payment_cycle === 1 ? '月付' : room.payment_cycle === 3 ? '季付' : '年付'}
• 下次收租：${nextPaymentDate}
• 距离天数：${days}天

请您提前准备好房租，我们将在${days}天内联系您收取。

感谢您的配合！🙏`
    }

    // 复制到剪贴板
    await navigator.clipboard.writeText(message)
    ElMessage.success('催租消息已复制到剪贴板，请发送给租客')

    // 可选：同时发送微信通知（如果集成了微信推送）
    // await sendWechatNotification(message)
  } catch (error) {
    console.error('Failed to send reminder:', error)
    ElMessage.error('发送催租消息失败')
  }
}

// 计算下次收租日期
const getNextPaymentDate = (room: Room) => {
  const lastPayment = room.last_payment_date || room.lease_start
  const lastDate = new Date(lastPayment)

  // 计算下次收租日期：lastDate + payment_cycle个月
  const nextDate = new Date(lastDate)
  // 先设置日期为1，避免溢出（比如1月31日加1个月会变成3月）
  nextDate.setDate(1)
  nextDate.setMonth(nextDate.getMonth() + room.payment_cycle)

  // 恢复原始日期，处理月份天数不足的情况
  const lastDay = lastDate.getDate()
  const daysInMonth = new Date(nextDate.getFullYear(), nextDate.getMonth() + 1, 0).getDate()
  if (lastDay > daysInMonth) {
    nextDate.setDate(daysInMonth)
  } else {
    nextDate.setDate(lastDay)
  }

  return nextDate.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

// 计算距离下次收租的天数
const getNextPaymentDays = (room: Room) => {
  const lastPayment = room.last_payment_date || room.lease_start
  const lastDate = new Date(lastPayment)

  // 计算下次收租日期
  const nextDate = new Date(lastDate)
  // 先设置日期为1，避免溢出
  nextDate.setDate(1)
  nextDate.setMonth(nextDate.getMonth() + room.payment_cycle)

  const lastDay = lastDate.getDate()
  const daysInMonth = new Date(nextDate.getFullYear(), nextDate.getMonth() + 1, 0).getDate()
  if (lastDay > daysInMonth) {
    nextDate.setDate(daysInMonth)
  } else {
    nextDate.setDate(lastDay)
  }

  const today = new Date()
  today.setHours(0, 0, 0, 0)  // 清除时分秒，确保准确计算天数
  nextDate.setHours(0, 0, 0, 0)

  const diff = Math.ceil((nextDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
  return diff  // 返回实际天数差，可以是负数（表示逾期）
}

// 获取房间号
const getRoomNumber = (roomId: number) => {
  const room = roomMap.value.get(roomId)
  return room?.room_number || `房间${roomId}`
}

// 获取房间信息
const getRoomInfo = (roomId: number, field: keyof Room) => {
  const room = roomMap.value.get(roomId)
  if (!room) return undefined
  return room[field]
}

// 获取房间信息
const getRoom = (roomId: number) => {
  return roomMap.value.get(roomId)
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

  // 自动生成并发送微信消息
  // 需要重新加载数据后才能获取完整的记录信息
  setTimeout(async () => {
    try {
      const readings = await utilityApi.getReadingsByRoom(result.room_id, {
        page: 1,
        size: 10,
      })

      // 找到对应日期的记录
      const mergedList = mergeReadings(readings.data.items || [])
      const merged = mergedList.find(m => m.reading_date === result.reading_date)

      if (merged) {
        await autoGenerateAndSendWechat(merged)
      }
    } catch (error) {
      console.error('Failed to auto send wechat:', error)
    }
  }, 500)
}

// 筛选
const handleFilter = () => {
  pagination.value.page = 1
  loadReadings()
}

// 重置筛选
const resetFilter = () => {
  filters.value = {
    room_id: undefined,
    start_date: '',
    end_date: '',
  }
  pagination.value.page = 1
  loadReadings()
}

// 显示编辑对话框
const showEditDialog = (merged: MergedReading) => {
  editOriginalData.value = merged
  editForm.value = {
    water_reading_id: merged.water_reading?.id || null,
    electricity_reading_id: merged.electricity_reading?.id || null,
    water_reading: merged.water_reading?.reading || 0,
    electricity_reading: merged.electricity_reading?.reading || 0,
    notes: merged.notes || '',
  }
  editDialogVisible.value = true
}

// 保存编辑
const saveEdit = async () => {
  try {
    editLoading.value = true
    const updatePromises: Promise<any>[] = []

    // 更新水表读数
    if (editForm.value.water_reading_id !== null && editForm.value.water_reading > 0) {
      updatePromises.push(
        utilityApi.updateReading(editForm.value.water_reading_id, {
          reading: editForm.value.water_reading,
          notes: editForm.value.notes,
        })
      )
    }

    // 更新电表读数
    if (editForm.value.electricity_reading_id !== null && editForm.value.electricity_reading > 0) {
      updatePromises.push(
        utilityApi.updateReading(editForm.value.electricity_reading_id, {
          reading: editForm.value.electricity_reading,
          notes: editForm.value.notes,
        })
      )
    }

    // 如果只有水或只有电，只更新备注
    if (editForm.value.water_reading_id === null && editForm.value.electricity_reading_id !== null) {
      updatePromises.push(
        utilityApi.updateReading(editForm.value.electricity_reading_id, {
          notes: editForm.value.notes,
        })
      )
    }
    if (editForm.value.electricity_reading_id === null && editForm.value.water_reading_id !== null) {
      updatePromises.push(
        utilityApi.updateReading(editForm.value.water_reading_id, {
          notes: editForm.value.notes,
        })
      )
    }

    await Promise.all(updatePromises)
    ElMessage.success('编辑成功')
    editDialogVisible.value = false

    // 自动生成并发送微信消息
    await autoGenerateAndSendWechat(editOriginalData.value!)
    loadReadings()
  } catch (error: any) {
    console.error('Failed to update reading:', error)
    const errorMsg = error.response?.data?.detail || '编辑失败，请重试'
    ElMessage.error(errorMsg)
  } finally {
    editLoading.value = false
  }
}

// 打开收租对话框
const showPaymentDialog = (row: MergedReading) => {
  const water_amount = Number(row.water_reading?.amount || 0)
  const electricity_amount = Number(row.electricity_reading?.amount || 0)
  const rent_amount = Number(row.monthly_rent || 0)
  
  paymentForm.value = {
    room_id: row.room_id,
    reading_date: row.reading_date,
    rent_original: rent_amount,
    rent_amount: rent_amount,
    water_original: water_amount,
    water_amount: water_amount,
    electricity_original: electricity_amount,
    electricity_amount: electricity_amount,
    payment_method: '现金',
    notes: ''
  }
  paymentDialogVisible.value = true
}

// 提交收租记录
const submitPayment = async () => {
  paymentLoading.value = true
  try {
    const payload: any = {
      room_id: paymentForm.value.room_id,
      reading_date: paymentForm.value.reading_date,
      rent_amount: paymentForm.value.rent_amount,
      rent_original: paymentForm.value.rent_original,
      payment_method: paymentForm.value.payment_method,
      notes: paymentForm.value.notes
    }
    
    // 水费
    if (paymentForm.value.water_original > 0) {
      payload.water_charge = {
        utility_type: 'water',
        amount: paymentForm.value.water_amount,
        original_amount: paymentForm.value.water_original,
        discount: paymentForm.value.water_original - paymentForm.value.water_amount
      }
    }
    
    // 电费
    if (paymentForm.value.electricity_original > 0) {
      payload.electricity_charge = {
        utility_type: 'electricity',
        amount: paymentForm.value.electricity_amount,
        original_amount: paymentForm.value.electricity_original,
        discount: paymentForm.value.electricity_original - paymentForm.value.electricity_amount
      }
    }
    
    const response = await paymentApi.createBulkPayment(payload)
    
    if (response.data.success) {
      ElMessage.success(`收租记录创建成功！实收：¥${response.data.total_actual}`)
      paymentDialogVisible.value = false
      // 刷新列表
      loadReadings()
    }
  } catch (error: any) {
    console.error('Failed to create payment:', error)
    ElMessage.error(error.response?.data?.detail || '创建收租记录失败')
  } finally {
    paymentLoading.value = false
  }
}

// 批量选择变化处理
const handleSelectionChange = (selection: MergedReading[]) => {
  selectedRows.value = selection
}

// 清除选择
const clearSelection = () => {
  tableRef.value?.clearSelection()
}

// 显示批量收租对话框
const showBatchPaymentDialog = () => {
  batchPayments.value = selectedRows.value.map(row => {
    const water_amount = Number(row.water_reading?.amount || 0)
    const electricity_amount = Number(row.electricity_reading?.amount || 0)
    const rent_amount = Number(row.monthly_rent || 0)

    return {
      room_id: row.room_id,
      reading_date: row.reading_date,
      rent_original: rent_amount,
      rent_amount: rent_amount,
      water_original: water_amount,
      water_amount: water_amount,
      electricity_original: electricity_amount,
      electricity_amount: electricity_amount,
      payment_method: '现金',
      notes: ''
    }
  })
  batchPaymentDialogVisible.value = true
}

// 提交批量收租
const submitBatchPayment = async () => {
  try {
    batchPaymentLoading.value = true

    const totalOriginal = batchPayments.value.reduce((sum, p) =>
      sum + p.rent_original + p.water_original + p.electricity_original, 0
    )
    const totalActual = batchPayments.value.reduce((sum, p) =>
      sum + p.rent_amount + p.water_amount + p.electricity_amount, 0
    )

    await ElMessageBox.confirm(
      `确认批量收租 ${batchPayments.value.length} 个房间？\n原始总额：¥${totalOriginal.toFixed(2)}\n实收总额：¥${totalActual.toFixed(2)}`,
      '批量收租确认',
      { type: 'warning' }
    )

    // 逐个创建收租记录
    const promises = batchPayments.value.map(payment => {
      const payload: any = {
        room_id: payment.room_id,
        payment_date: new Date().toISOString().split('T')[0],
        amount: payment.rent_amount,
        payment_method: payment.payment_method,
        notes: payment.notes
      }

      if (payment.water_original > 0) {
        payload.water_charge = {
          utility_type: 'water',
          amount: payment.water_amount,
          original_amount: payment.water_original,
          discount: payment.water_original - payment.water_amount
        }
      }

      if (payment.electricity_original > 0) {
        payload.electricity_charge = {
          utility_type: 'electricity',
          amount: payment.electricity_amount,
          original_amount: payment.electricity_original,
          discount: payment.electricity_original - payment.electricity_amount
        }
      }

      return paymentApi.createBulkPayment(payload)
    })

    await Promise.all(promises)
    ElMessage.success(`批量收租成功！共处理 ${batchPayments.value.length} 个房间`)
    batchPaymentDialogVisible.value = false
    clearSelection()
    loadReadings()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('Batch payment failed:', error)
      ElMessage.error(error.response?.data?.detail || '批量收租失败')
    }
  } finally {
    batchPaymentLoading.value = false
  }
}

// 批量生成消息
const batchGenerateMessages = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要为选中的 ${selectedRows.value.length} 条记录生成微信消息吗？`,
      '批量生成消息',
      { type: 'info' }
    )

    let allMessages = ''
    selectedRows.value.forEach((row, index) => {
      const roomNumber = getRoomNumber(row.room_id)
      const date = new Date(row.reading_date).toLocaleDateString('zh-CN')

      let message = `\n【收租通知 ${index + 1}/${selectedRows.value.length}】\n房间：${roomNumber}\n抄表日期：${date}\n`

      if (row.monthly_rent) {
        message += `\n🏠 房租：¥${row.monthly_rent.toFixed(2)}\n`
      }

      if (row.water_reading) {
        message += `\n💧 水费：\n`
        message += `  上次读数：${row.water_reading.previous_reading} 吨\n`
        message += `  本次读数：${row.water_reading.reading} 吨\n`
        message += `  用量：${row.water_reading.usage} 吨\n`
        message += `  费用：¥${(row.water_reading.amount || 0).toFixed(2)}\n`
      }

      if (row.electricity_reading) {
        message += `\n⚡ 电费：\n`
        message += `  上次读数：${row.electricity_reading.previous_reading} 度\n`
        message += `  本次读数：${row.electricity_reading.reading} 度\n`
        message += `  用量：${row.electricity_reading.usage} 度\n`
        message += `  费用：¥${(row.electricity_reading.amount || 0).toFixed(2)}\n`
      }

      message += `\n💰 应付总额：¥${row.total_amount.toFixed(2)}`

      if (row.notes) {
        message += `\n\n备注：${row.notes}`
      }

      message += `\n\n请及时缴纳费用，谢谢！\n${'='.repeat(30)}\n`

      allMessages += message
    })

    // 复制到剪贴板
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(allMessages)
      ElMessage.success(`已生成 ${selectedRows.value.length} 条消息并复制到剪贴板`)
    } else {
      showCopyFallback(allMessages)
      ElMessage.success(`已生成 ${selectedRows.value.length} 条消息`)
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('Batch generate messages failed:', error)
      ElMessage.error('批量生成消息失败')
    }
  }
}

// 批量删除
const batchDelete = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedRows.value.length} 条记录吗？这将删除这些房间在对应日期的所有水电记录。`,
      '批量删除确认',
      { type: 'warning' }
    )

    const deletePromises: Promise<any>[] = []
    selectedRows.value.forEach(row => {
      if (row.water_reading) {
        deletePromises.push(utilityApi.deleteReading(row.water_reading.id))
      }
      if (row.electricity_reading) {
        deletePromises.push(utilityApi.deleteReading(row.electricity_reading.id))
      }
    })

    await Promise.all(deletePromises)
    ElMessage.success(`批量删除成功！共删除 ${selectedRows.value.length} 条记录`)
    clearSelection()
    loadReadings()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('Batch delete failed:', error)
      ElMessage.error('批量删除失败')
    }
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

// 分页改变
const handlePageChange = (page: number) => {
  pagination.value.page = page
  loadReadings()
}

const handleSizeChange = (size: number) => {
  pagination.value.size = size
  pagination.value.page = 1
  loadReadings()
}

// 初始化
onMounted(() => {
  loadRooms() // 先加载房间列表
  loadReadings()
  loadExpiringRooms() // 加载即将到期的房间
})
</script>

<template>
  <div class="utility-view">
    <div class="page-header">
      <h1>水电表管理</h1>
      <div class="header-buttons">
        <el-button type="success" @click="showBatchForm">
          <el-icon><Plus /></el-icon>
          批量录入
        </el-button>
        <el-button type="primary" @click="showAddForm">
          <el-icon><Plus /></el-icon>
          录入水电
        </el-button>
      </div>
    </div>

    <!-- 收租提醒 - 始终显示 -->
    <el-card class="expiring-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="title">💰 收租管理</span>
          <div class="tags">
            <el-tag type="danger" size="small">欠租: {{ overdueRooms.length }} 个</el-tag>
            <el-tag type="warning" size="small">即将到期: {{ expiringRooms.length }} 个</el-tag>
          </div>
        </div>
      </template>

      <!-- 欠租房间列表 -->
      <div class="reminder-section">
        <div class="section-header overdue-header">
          <span class="section-title">🚨 欠租房间（已逾期）</span>
        </div>
        <div v-if="overdueRooms.length > 0" class="expiring-list">
          <div v-for="item in overdueRooms" :key="item.room.id" class="expiring-item overdue-item">
            <div class="room-info">
              <span class="room-number">{{ item.room.room_number }}</span>
              <span class="room-rent">¥{{ item.room.monthly_rent }}/月</span>
              <el-tag size="small" type="danger">逾期{{ item.overdueDays }}天</el-tag>
            </div>
            <div class="lease-info">
              <span class="overdue-amount">欠费约: ¥{{ item.overdueAmount }}</span>
              <el-button type="danger" size="small" @click="sendReminder(item.room, 'overdue')">
                📱 催租
              </el-button>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <el-text type="info">✅ 暂无欠租房间</el-text>
        </div>
      </div>

      <!-- 即将到期房间列表 -->
      <div class="reminder-section">
        <div class="section-header upcoming-header">
          <span class="section-title">📅 即将到期（7天内需收租）</span>
        </div>
        <div v-if="expiringRooms.length > 0" class="expiring-list">
          <div v-for="room in expiringRooms" :key="room.id" class="expiring-item">
            <div class="room-info">
              <span class="room-number">{{ room.room_number }}</span>
              <span class="room-rent">¥{{ room.monthly_rent }}/月</span>
              <el-tag size="small" type="info">{{ room.payment_cycle === 1 ? '月付' : room.payment_cycle === 3 ? '季付' : '年付' }}</el-tag>
            </div>
            <div class="lease-info">
              <el-tag :type="getNextPaymentDays(room) <= 3 ? 'danger' : 'warning'" size="small">
                {{ getNextPaymentDays(room) }}天后需收租
              </el-tag>
              <el-button type="primary" size="small" @click="openUtilityForm(room.id)">
                💧 录入水电
              </el-button>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <el-text type="info">✅ 暂无即将到期房间</el-text>
        </div>
      </div>
    </el-card>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="水电记录" name="readings">
        <!-- 筛选条件 -->
        <el-card class="filter-card">
          <el-form :inline="true">
            <el-form-item label="房间号">
              <el-select
                v-model="filters.room_id"
                placeholder="选择房间"
                clearable
                filterable
                :loading="roomsLoading"
              >
                <el-option
                  v-for="room in roomOptions"
                  :key="room.id"
                  :label="room.room_number"
                  :value="room.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="抄表日期">
              <el-date-picker
                v-model="filters.start_date"
                type="date"
                placeholder="开始日期"
                value-format="YYYY-MM-DD"
              />
              <span class="date-separator">-</span>
              <el-date-picker
                v-model="filters.end_date"
                type="date"
                placeholder="结束日期"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="handleFilter">筛选</el-button>
              <el-button @click="resetFilter">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 批量操作栏 -->
        <el-card v-if="selectedRows.length > 0" class="batch-actions-card">
          <div class="batch-actions">
            <span class="selected-info">
              已选择 <strong>{{ selectedRows.length }}</strong> 条记录
            </span>
            <div class="batch-buttons">
              <el-button type="primary" :disabled="!canBatchPay" @click="showBatchPaymentDialog">
                批量收租 ({{ selectedRows.length }})
              </el-button>
              <el-button type="success" @click="batchGenerateMessages">
                批量生成消息
              </el-button>
              <el-button type="danger" @click="batchDelete">
                批量删除
              </el-button>
              <el-button @click="clearSelection">
                取消选择
              </el-button>
            </div>
          </div>
        </el-card>

        <!-- 数据表格 -->
        <el-table
          ref="tableRef"
          v-loading="loading"
          :data="mergedReadings"
          stripe
          class="utility-table"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="55" />

          <el-table-column prop="reading_date" label="抄表日期" width="120">
            <template #default="{ row }">
              {{ new Date(row.reading_date).toLocaleDateString('zh-CN') }}
            </template>
          </el-table-column>

          <el-table-column prop="room_id" label="房间号" width="120">
            <template #default="{ row }">
              {{ getRoomNumber(row.room_id) }}
            </template>
          </el-table-column>

          <el-table-column label="💰 月租金" width="110">
            <template #default="{ row }">
              <span class="rent-amount">¥{{ getRoomInfo(row.room_id, 'monthly_rent') || '-' }}</span>
            </template>
          </el-table-column>

          <el-table-column label="💧 水表" width="200">
            <template #default="{ row }">
              <div v-if="row.water_reading" class="reading-cell">
                <!-- 如果水费为0，说明是无水电费房间 -->
                <div v-if="row.water_reading.amount === 0 || row.water_reading.amount === '0'" class="no-data">
                  无水电费
                </div>
                <div v-else>
                  <div class="reading-row">
                    <span class="label">上次:</span>
                    <span>{{ row.water_reading.previous_reading }}</span>
                  </div>
                  <div class="reading-row">
                    <span class="label">本次:</span>
                    <span>{{ row.water_reading.reading }}</span>
                  </div>
                  <div class="reading-row highlight">
                    <span class="label">用量:</span>
                    <span>{{ row.water_reading.usage }}</span>
                  </div>
                </div>
              </div>
              <span v-else class="no-data">未录入</span>
            </template>
          </el-table-column>

          <el-table-column label="⚡ 电表" width="200">
            <template #default="{ row }">
              <div v-if="row.electricity_reading" class="reading-cell">
                <!-- 如果电费为0，说明是无水电费房间 -->
                <div v-if="row.electricity_reading.amount === 0 || row.electricity_reading.amount === '0'" class="no-data">
                  无水电费
                </div>
                <div v-else>
                  <div class="reading-row">
                    <span class="label">上次:</span>
                    <span>{{ row.electricity_reading.previous_reading }}</span>
                  </div>
                  <div class="reading-row">
                    <span class="label">本次:</span>
                    <span>{{ row.electricity_reading.reading }}</span>
                  </div>
                  <div class="reading-row highlight">
                    <span class="label">用量:</span>
                    <span>{{ row.electricity_reading.usage }}</span>
                  </div>
                </div>
              </div>
              <span v-else class="no-data">未录入</span>
            </template>
          </el-table-column>

          <el-table-column label="费用" width="150">
            <template #default="{ row }">
              <div class="amount-cell">
                <div v-if="row.water_reading" class="amount-row">
                  <span class="amount-label">水费:</span>
                  <span class="amount">¥{{ Number(row.water_reading.amount || 0).toFixed(2) }}</span>
                </div>
                <div v-if="row.electricity_reading" class="amount-row">
                  <span class="amount-label">电费:</span>
                  <span class="amount">¥{{ Number(row.electricity_reading.amount || 0).toFixed(2) }}</span>
                </div>
                <div class="total-amount">
                  <span class="amount-label">总计:</span>
                  <span class="amount total">¥{{ Number(row.total_amount || 0).toFixed(2) }}</span>
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column prop="notes" label="备注" min-width="150" show-overflow-tooltip />

          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button
                type="primary"
                size="small"
                @click="showEditDialog(row)"
              >
                编辑
              </el-button>
              <el-button
                type="success"
                size="small"
                :disabled="row.is_paid"
                @click="showPaymentDialog(row)"
              >
                {{ row.is_paid ? '已收租' : '标记已收' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <div class="pagination-container">
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.size"
            :page-sizes="[10, 20, 50, 100]"
            :total="pagination.total"
            layout="total, sizes, prev, pager, next, jumper"
            @current-change="handlePageChange"
            @size-change="handleSizeChange"
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 录入表单对话框 -->
    <el-dialog
      v-model="showFormDialog"
      title="录入水电表读数"
      width="600px"
      :close-on-click-modal="false"
      @close="showFormDialog = false; selectedRoomId = undefined"
    >
      <UtilityReadingForm
        v-if="showFormDialog"
        :room-id="selectedRoomId"
        @success="handleFormSuccess"
        @cancel="showFormDialog = false; selectedRoomId = undefined"
      />
    </el-dialog>

    <!-- 批量录入对话框 -->
    <el-dialog
      v-model="batchDialogVisible"
      title="批量录入水电读数"
      width="800px"
      :close-on-click-modal="false"
    >
      <el-form :model="batchForm" label-width="100px">
        <el-form-item label="抄表日期">
          <el-date-picker
            v-model="batchForm.reading_date"
            type="date"
            placeholder="选择日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>

        <el-form-item label="水电类型">
          <el-radio-group v-model="batchForm.utility_type">
            <el-radio label="water">仅水费</el-radio>
            <el-radio label="electricity">仅电费</el-radio>
            <el-radio label="both">水电全录</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-divider content-position="left">选择房间并录入读数</el-divider>

        <el-form-item>
          <el-button @click="selectAllRooms" size="small">全选</el-button>
          <el-button @click="clearRoomSelection" size="small">清空</el-button>
          <el-button @click="selectOccupiedRooms" size="small" type="primary">仅选已租</el-button>
        </el-form-item>

        <div class="batch-room-list">
          <el-checkbox-group v-model="selectedRooms">
            <div
              v-for="room in allRooms"
              :key="room.id"
              class="batch-room-item"
              :class="{ 'selected': selectedRooms.includes(room.id) }"
            >
              <el-checkbox :label="room.id">
                <span class="room-number">{{ room.room_number }}</span>
                <el-tag size="small" :type="room.status === 'occupied' ? 'success' : 'info'">
                  {{ room.status === 'occupied' ? '已租' : '空置' }}
                </el-tag>
                <span class="room-rent">¥{{ room.monthly_rent }}/月</span>
              </el-checkbox>

              <!-- 选中时显示读数输入框 -->
              <div v-if="selectedRooms.includes(room.id)" class="room-readings">
                <div v-if="batchForm.utility_type === 'water' || batchForm.utility_type === 'both'" class="reading-input">
                  <span class="label">💧 水表读数:</span>
                  <el-input-number
                    v-model="room.water_reading"
                    :min="0"
                    :precision="1"
                    :step="0.1"
                    size="small"
                  />
                  <span class="rate">费率: ¥{{ room.water_rate || 0 }}/吨</span>
                </div>
                <div v-if="batchForm.utility_type === 'electricity' || batchForm.utility_type === 'both'" class="reading-input">
                  <span class="label">⚡ 电表读数:</span>
                  <el-input-number
                    v-model="room.electricity_reading"
                    :min="0"
                    :precision="1"
                    :step="1"
                    size="small"
                  />
                  <span class="rate">费率: ¥{{ room.electricity_rate || 0 }}/度</span>
                </div>
              </div>
            </div>
          </el-checkbox-group>
        </div>

        <el-form-item label="统一备注">
          <el-input
            v-model="batchForm.notes"
            type="textarea"
            :rows="2"
            placeholder="可选：填写备注（将应用到所有记录）"
          />
        </el-form-item>

        <div class="batch-summary" v-if="selectedRooms.length > 0">
          <div>已选择: <strong>{{ selectedRooms.length }}</strong> 个房间</div>
          <div>预计录入: <strong>{{ calculateTotalRecords() }}</strong> 条记录</div>
        </div>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="batchDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitBatch" :loading="batchLoading" :disabled="selectedRooms.length === 0">
            批量录入 ({{ selectedRooms.length }}个房间)
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 收租对话框 -->
    <el-dialog
      v-model="paymentDialogVisible"
      title="💰 标记已收（支持打折）"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form :model="paymentForm" label-width="100px">
        <el-form-item label="房间号">
          <span>{{ getRoomNumber(paymentForm.room_id) }}</span>
        </el-form-item>

        <el-form-item label="抄表日期">
          <span>{{ paymentForm.reading_date }}</span>
        </el-form-item>

        <el-divider content-position="left">🏠 房租</el-divider>

        <el-form-item label="原始房租">
          <span class="original-amount">¥{{ Number(paymentForm.rent_original || 0).toFixed(2) }}</span>
        </el-form-item>

        <el-form-item label="实收房租">
          <el-input-number
            v-model="paymentForm.rent_amount"
            :min="0"
            :max="Number(paymentForm.rent_original || 0)"
            :precision="2"
            :step="10"
          />
          <span v-if="Number(paymentForm.rent_amount || 0) < Number(paymentForm.rent_original || 0)" class="discount-hint">
            打折：¥{{ (Number(paymentForm.rent_original || 0) - Number(paymentForm.rent_amount || 0)).toFixed(2) }}
          </span>
        </el-form-item>

        <el-divider content-position="left">💧 水费</el-divider>

        <el-form-item label="原始水费">
          <span class="original-amount">¥{{ Number(paymentForm.water_original || 0).toFixed(2) }}</span>
        </el-form-item>

        <el-form-item label="实收水费">
          <el-input-number
            v-model="paymentForm.water_amount"
            :min="0"
            :max="Number(paymentForm.water_original || 0)"
            :precision="2"
            :step="1"
          />
          <span v-if="Number(paymentForm.water_amount || 0) < Number(paymentForm.water_original || 0)" class="discount-hint">
            打折：¥{{ (Number(paymentForm.water_original || 0) - Number(paymentForm.water_amount || 0)).toFixed(2) }}
          </span>
        </el-form-item>

        <el-divider content-position="left">⚡ 电费</el-divider>

        <el-form-item label="原始电费">
          <span class="original-amount">¥{{ Number(paymentForm.electricity_original || 0).toFixed(2) }}</span>
        </el-form-item>

        <el-form-item label="实收电费">
          <el-input-number
            v-model="paymentForm.electricity_amount"
            :min="0"
            :max="Number(paymentForm.electricity_original || 0)"
            :precision="2"
            :step="1"
          />
          <span v-if="Number(paymentForm.electricity_amount || 0) < Number(paymentForm.electricity_original || 0)" class="discount-hint">
            打折：¥{{ (Number(paymentForm.electricity_original || 0) - Number(paymentForm.electricity_amount || 0)).toFixed(2) }}
          </span>
        </el-form-item>

        <el-divider />

        <el-form-item label="总计">
          <div class="total-summary">
            <div>原始总额：¥{{ (Number(paymentForm.rent_original || 0) + Number(paymentForm.water_original || 0) + Number(paymentForm.electricity_original || 0)).toFixed(2) }}</div>
            <div class="actual-total">实收总额：¥{{ (Number(paymentForm.rent_amount || 0) + Number(paymentForm.water_amount || 0) + Number(paymentForm.electricity_amount || 0)).toFixed(2) }}</div>
            <div v-if="(Number(paymentForm.rent_amount || 0) + Number(paymentForm.water_amount || 0) + Number(paymentForm.electricity_amount || 0)) < (Number(paymentForm.rent_original || 0) + Number(paymentForm.water_original || 0) + Number(paymentForm.electricity_original || 0))" class="total-discount">
              总折扣：¥{{ ((Number(paymentForm.rent_original || 0) + Number(paymentForm.water_original || 0) + Number(paymentForm.electricity_original || 0)) - (Number(paymentForm.rent_amount || 0) + Number(paymentForm.water_amount || 0) + Number(paymentForm.electricity_amount || 0))).toFixed(2) }}
            </div>
          </div>
        </el-form-item>

        <el-form-item label="收款方式">
          <el-select v-model="paymentForm.payment_method">
            <el-option label="现金" value="现金" />
            <el-option label="微信支付" value="微信支付" />
            <el-option label="支付宝" value="支付宝" />
            <el-option label="银行转账" value="银行转账" />
          </el-select>
        </el-form-item>

        <el-form-item label="备注">
          <el-input
            v-model="paymentForm.notes"
            type="textarea"
            :rows="2"
            placeholder="可选，如：提前付款、部分付款等"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="paymentDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="paymentLoading" @click="submitPayment">
          确认收款
        </el-button>
      </template>
    </el-dialog>

    <!-- 编辑对话框 -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑水电记录"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form label-width="120px">
        <el-alert
          title="编辑提示"
          type="info"
          :closable="false"
          style="margin-bottom: 20px"
        >
          修改读数会自动重新计算用量和费用
        </el-alert>

        <template v-if="editForm.water_reading_id !== null">
          <el-divider content-position="left">💧 水表</el-divider>
          <el-form-item label="水表读数（吨）">
            <el-input-number
              v-model="editForm.water_reading"
              :min="0"
              :precision="1"
              :step="1"
              style="width: 200px"
            />
          </el-form-item>
        </template>

        <template v-if="editForm.electricity_reading_id !== null">
          <el-divider content-position="left">⚡ 电表</el-divider>
          <el-form-item label="电表读数（度）">
            <el-input-number
              v-model="editForm.electricity_reading"
              :min="0"
              :precision="0"
              :step="1"
              style="width: 200px"
            />
          </el-form-item>
        </template>

        <el-divider content-position="left">📝 备注</el-divider>
        <el-form-item label="备注">
          <el-input
            v-model="editForm.notes"
            type="textarea"
            :rows="3"
            placeholder="请输入备注信息"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="saveEdit">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 消息输出对话框 -->
    <el-dialog
      v-model="messageDialogVisible"
      title="📱 收租消息（已自动推送到微信）"
      width="600px"
    >
      <el-alert
        title="消息已生成"
        type="success"
        :closable="false"
        style="margin-bottom: 15px"
      >
        消息已自动推送到企业微信群，并复制到剪贴板
      </el-alert>

      <el-input
        v-model="currentMessage"
        type="textarea"
        :rows="15"
        readonly
        style="font-family: 'Courier New', monospace; font-size: 14px"
      />

      <template #footer>
        <el-button type="primary" @click="copyMessage">
          📋 复制消息
        </el-button>
        <el-button @click="messageDialogVisible = false">
          关闭
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量收租对话框 -->
    <el-dialog
      v-model="batchPaymentDialogVisible"
      title="批量收租"
      width="900px"
      :close-on-click-modal="false"
    >
      <el-table :data="batchPayments" max-height="400">
        <el-table-column prop="room_id" label="房间" width="100">
          <template #default="{ row }">
            {{ getRoomNumber(row.room_id) }}
          </template>
        </el-table-column>

        <el-table-column label="房租" width="150">
          <template #default="{ row }">
            <el-input-number
              v-model="row.rent_amount"
              :min="0"
              :max="row.rent_original"
              :precision="2"
              :step="10"
              size="small"
            />
          </template>
        </el-table-column>

        <el-table-column label="水费" width="150">
          <template #default="{ row }">
            <el-input-number
              v-model="row.water_amount"
              :min="0"
              :max="row.water_original"
              :precision="2"
              :step="1"
              size="small"
              :disabled="row.water_original === 0"
            />
          </template>
        </el-table-column>

        <el-table-column label="电费" width="150">
          <template #default="{ row }">
            <el-input-number
              v-model="row.electricity_amount"
              :min="0"
              :max="row.electricity_original"
              :precision="2"
              :step="1"
              size="small"
              :disabled="row.electricity_original === 0"
            />
          </template>
        </el-table-column>

        <el-table-column label="收款方式" width="130">
          <template #default="{ row }">
            <el-select v-model="row.payment_method" size="small">
              <el-option label="现金" value="现金" />
              <el-option label="微信支付" value="微信支付" />
              <el-option label="支付宝" value="支付宝" />
              <el-option label="银行转账" value="银行转账" />
            </el-select>
          </template>
        </el-table-column>

        <el-table-column label="备注" min-width="150">
          <template #default="{ row }">
            <el-input v-model="row.notes" size="small" placeholder="备注" />
          </template>
        </el-table-column>
      </el-table>

      <el-divider />

      <div class="batch-summary">
        <div>
          <span>原始总额：</span>
          <span class="amount">
            ¥{{
              batchPayments.reduce(
                (sum, p) => sum + p.rent_original + p.water_original + p.electricity_original,
                0
              ).toFixed(2)
            }}
          </span>
        </div>
        <div>
          <span>实收总额：</span>
          <span class="amount actual">
            ¥{{
              batchPayments.reduce(
                (sum, p) => sum + p.rent_amount + p.water_amount + p.electricity_amount,
                0
              ).toFixed(2)
            }}
          </span>
        </div>
      </div>

      <template #footer>
        <el-button @click="batchPaymentDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchPaymentLoading" @click="submitBatchPayment">
          确认批量收款
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.utility-view {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.filter-card {
  margin-bottom: 20px;
}

.date-separator {
  margin: 0 8px;
  color: #909399;
}

.utility-table {
  margin-bottom: 20px;
}

.reading-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.reading-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}

.reading-row .label {
  color: #909399;
  font-weight: 500;
}

.reading-row.highlight {
  color: #409eff;
  font-weight: 600;
  margin-top: 2px;
}

.no-data {
  color: #c0c4cc;
  font-size: 13px;
}

.amount-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.amount-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}

.amount-label {
  color: #909399;
  font-weight: 500;
}

.amount {
  color: #f56c6c;
  font-weight: 600;
}

.total-amount {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px dashed #dcdfe6;
}

.amount.total {
  color: #f56c6c;
  font-size: 15px;
  font-weight: 700;
}

.pagination-container {
  display: flex;
  justify-content: center;
}

/* 即将到期提醒卡片样式 */
.expiring-card {
  margin-bottom: 20px;
  border: 1px solid #e6a23c;
  background: linear-gradient(135deg, #fff7e6 0%, #ffffff 100%);
}

.expiring-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.expiring-card .title {
  font-weight: 600;
  color: #e6a23c;
}

.expiring-card .tags {
  display: flex;
  gap: 8px;
}

/* 欠租管理区块样式 */
.reminder-section {
  margin-bottom: 16px;
}

.reminder-section:last-child {
  margin-bottom: 0;
}

.section-header {
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 12px;
  background: white;
  border-left: 4px solid;
}

.section-header.overdue-header {
  border-left-color: #f56c6c;
  background: linear-gradient(135deg, #fef0f0 0%, #ffffff 100%);
}

.section-header.upcoming-header {
  border-left-color: #e6a23c;
  background: linear-gradient(135deg, #fff7e6 0%, #ffffff 100%);
}

.section-title {
  font-weight: 600;
  font-size: 14px;
  color: #606266;
}

.overdue-item {
  background: linear-gradient(135deg, #fef0f0 0%, #ffffff 100%);
  border-color: #fbc4c4;
}

.overdue-amount {
  font-size: 13px;
  color: #f56c6c;
  font-weight: 600;
  margin-right: 8px;
}

.expiring-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.empty-state {
  padding: 24px;
  text-align: center;
  background: #f9f9f9;
  border-radius: 6px;
  border: 1px dashed #dcdfe6;
}

.expiring-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: white;
  border-radius: 6px;
  border: 1px solid #f5dab1;
  transition: all 0.2s;
}

.expiring-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 2px 8px rgba(230, 162, 60, 0.2);
}

.expiring-item .room-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.expiring-item .room-number {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.expiring-item .room-rent {
  font-size: 13px;
  color: #909399;
}

.expiring-item .lease-info {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.expiring-item .lease-date {
  font-size: 12px;
  color: #909399;
}

/* 收租对话框样式 */
.original-amount {
  font-size: 16px;
  color: #909399;
  text-decoration: line-through;
}

.discount-hint {
  margin-left: 10px;
  font-size: 13px;
  color: #e6a23c;
  font-weight: 500;
}

.total-summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.total-summary > div {
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 14px;
}

.actual-total {
  font-size: 18px !important;
  font-weight: 700;
  color: #67c23a !important;
  background: #f0f9ff !important;
}

.total-discount {
  color: #e6a23c;
  font-weight: 600;
  background: #fff7e6 !important;
}

/* 批量操作样式 */
.batch-actions-card {
  margin-bottom: 20px;
  border: 2px solid #409eff;
  background: linear-gradient(135deg, #ecf5ff 0%, #ffffff 100%);
}

.batch-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 8px;
}

.batch-actions .selected-info {
  font-size: 15px;
  color: #409eff;
  font-weight: 500;
}

.batch-actions .selected-info strong {
  font-size: 18px;
  font-weight: 700;
}

.batch-actions .batch-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.batch-summary {
  display: flex;
  justify-content: space-around;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 16px;
}

.batch-summary > div {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.batch-summary .amount {
  font-size: 20px;
  font-weight: 700;
  color: #303133;
}

.batch-summary .amount.actual {
  font-size: 24px;
  color: #67c23a;
}

/* 批量录入对话框样式 */
.header-buttons {
  display: flex;
  gap: 8px;
}

.batch-room-list {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 12px;
  background: #f5f7fa;
}

.batch-room-item {
  padding: 12px;
  margin-bottom: 8px;
  background: white;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
  transition: all 0.3s;
}

.batch-room-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.1);
}

.batch-room-item.selected {
  border-color: #409eff;
  background: #ecf5ff;
}

.batch-room-item .room-number {
  font-weight: 600;
  margin-right: 8px;
  font-size: 16px;
}

.batch-room-item .room-rent {
  margin-left: 8px;
  color: #909399;
  font-size: 14px;
}

.room-readings {
  margin-top: 12px;
  padding: 8px;
  background: #f9fafc;
  border-radius: 4px;
}

.reading-input {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.reading-input:last-child {
  margin-bottom: 0;
}

.reading-input .label {
  min-width: 80px;
  font-weight: 500;
  color: #606266;
}

.reading-input .rate {
  margin-left: auto;
  color: #909399;
  font-size: 12px;
}

</style>
