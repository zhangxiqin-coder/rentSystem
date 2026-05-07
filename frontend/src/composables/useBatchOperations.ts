import { ref, computed, type Ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { utilityApi } from '@/api/utility'
import { paymentApi } from '@/api/payment'
import type { MergedReading } from '@/composables/useMergedReadings'
import type { Room } from '@/types'

export function useBatchOperations(deps: {
  allRooms: Ref<Room[]>
  formatAmount: (value: number, currency?: string) => string
  getRoomNumber: (roomId: number) => string
  loadReadings: () => Promise<void>
  loadRooms: () => Promise<void>
  generateMessageText: (merged: MergedReading) => string
  showCopyFallback: (message: string) => void
}) {
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
  const selectedRooms = ref<number[]>([])
  const batchForm = ref({
    reading_date: new Date().toISOString().split('T')[0], // 默认今天
    utility_type: 'both', // 默认水电全录
    notes: ''
  })

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
      if (result.data.failed_count > 0) {
        ElMessage.warning(`成功 ${result.data.success_count} 条，失败 ${result.data.failed_count} 条`)
        if (result.data.errors.length > 0) {
          console.error('批量录入错误:', result.data.errors)
        }
      } else {
        ElMessage.success(`批量录入成功！共 ${result.data.success_count} 条记录，总金额 ${formatAmount(Number(result.data.total_amount || 0))}`)
      }

      // 关闭对话框并刷新列表
      batchDialogVisible.value = false
      loadReadings()
      // loadPayments is covered by loadReadings which reloads payments

    } catch (error: any) {
      console.error('批量录入失败:', error)
      ElMessage.error(error.response?.data?.detail || '批量录入失败')
    } finally {
      batchLoading.value = false
    }
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
      const cycle = Math.max(1, Number(row.payment_cycle || 1))
      const rent_amount = Number(row.monthly_rent || 0) * cycle

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
        `确认批量收租 ${batchPayments.value.length} 个房间？\n原始总额：${formatAmount(totalOriginal)}\n实收总额：${formatAmount(totalActual)}`,
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
        const cycle = Math.max(1, Number(row.payment_cycle || 1))
        const rentDue = Number(row.monthly_rent || 0) * cycle
        const rentLabel = cycle > 1 ? `房租（${cycle}个月）` : '房租'

        let message = `\n【收租通知 ${index + 1}/${selectedRows.value.length}】\n房间：${roomNumber}\n抄表日期：${date}\n`

        if (rentDue > 0) {
          message += `\n🏠 ${rentLabel}：${formatAmount(rentDue)}\n`
        }

        if (row.water_reading) {
          message += `\n💧 水费：\n`
          message += `  上次读数：${row.water_reading.previous_reading} 吨\n`
          message += `  本次读数：${row.water_reading.reading} 吨\n`
          message += `  用量：${row.water_reading.usage} 吨\n`
          message += `  费用：${formatAmount(Number(row.water_reading.amount || 0))}\n`
        }

        if (row.electricity_reading) {
          message += `\n⚡ 电费：\n`
          message += `  上次读数：${row.electricity_reading.previous_reading} 度\n`
          message += `  本次读数：${row.electricity_reading.reading} 度\n`
          message += `  用量：${row.electricity_reading.usage} 度\n`
          message += `  费用：${formatAmount(Number(row.electricity_reading.amount || 0))}\n`
        }

        message += `\n💰 应付总额：${formatAmount(row.total_amount)}`

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

  return {
    batchDialogVisible,
    batchLoading,
    selectedRooms,
    batchForm,
    showBatchForm,
    selectAllRooms,
    clearRoomSelection,
    selectOccupiedRooms,
    calculateTotalRecords,
    submitBatch,
    tableRef,
    selectedRows,
    canBatchPay,
    handleSelectionChange,
    clearSelection,
    batchPaymentDialogVisible,
    batchPaymentLoading,
    batchPayments,
    showBatchPaymentDialog,
    submitBatchPayment,
    batchGenerateMessages,
    batchDelete,
  }
}
