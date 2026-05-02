import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { paymentApi } from '@/api/payment'
import type { MergedReading } from '@/composables/useMergedReadings'

export function usePaymentData(deps: {
  formatAmount: (value: number, currency?: string) => string
  loadReadings: () => Promise<void>
  loadRooms: () => Promise<void>
}) {
  const { formatAmount, loadReadings, loadRooms } = deps

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
    notes: '',
    period_start: '',
    period_end: '',
  })
  const paymentLoading = ref(false)

  const showPaymentDialog = (row: MergedReading) => {
    const water_amount = Number(row.water_reading?.amount || 0)
    const electricity_amount = Number(row.electricity_reading?.amount || 0)
    const cycle = Math.max(1, Number(row.payment_cycle || 1))
    const rent_amount = Number(row.monthly_rent || 0) * cycle

    // 计算覆盖周期
    let periodStart = ''
    let periodEnd = ''
    const leaseStart = row.lease_start
    if (leaseStart) {
      const anchor = new Date(leaseStart)
      const dueDay = anchor.getDate()
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      const buildDue = (y: number, m: number, d: number) => {
        const dim = new Date(y, m + 1, 0).getDate()
        const dt = new Date(y, m, Math.min(d, dim))
        dt.setHours(0, 0, 0, 0)
        return dt
      }
      const addMonths = (base: Date, months: number) => {
        const d = new Date(base)
        d.setDate(1)
        d.setMonth(d.getMonth() + months)
        return buildDue(d.getFullYear(), d.getMonth(), dueDay)
      }
      let cursor = buildDue(anchor.getFullYear(), anchor.getMonth(), dueDay)
      while (cursor <= today) {
        cursor = addMonths(cursor, cycle)
      }
      const pStart = addMonths(cursor, -cycle)
      periodStart = pStart.toISOString().split('T')[0]
      periodEnd = new Date(cursor.getTime() - 86400000).toISOString().split('T')[0]
    }

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
      notes: '',
      period_start: periodStart,
      period_end: periodEnd,
    }
    paymentDialogVisible.value = true
  }

  // 提交收租记录
  const submitPayment = async () => {
    paymentLoading.value = true
    try {
      const payload: any = {
        room_id: paymentForm.value.room_id,
        reading_date: paymentForm.value.reading_date || new Date().toISOString().split('T')[0],
        rent_amount: paymentForm.value.rent_amount,
        rent_original: paymentForm.value.rent_original,
        payment_method: paymentForm.value.payment_method,
        notes: paymentForm.value.notes,
        period_start: paymentForm.value.period_start || undefined,
        period_end: paymentForm.value.period_end || undefined,
      }

      // 添加水电费（如果有金额）
      if (paymentForm.value.water_amount > 0) {
        payload.water_charge = {
          utility_type: 'water',
          amount: Number(paymentForm.value.water_amount),
          original_amount: Number(paymentForm.value.water_original),
          discount: Number(paymentForm.value.water_original) - Number(paymentForm.value.water_amount)
        }
      }

      if (paymentForm.value.electricity_amount > 0) {
        payload.electricity_charge = {
          utility_type: 'electricity',
          amount: Number(paymentForm.value.electricity_amount),
          original_amount: Number(paymentForm.value.electricity_original),
          discount: Number(paymentForm.value.electricity_original) - Number(paymentForm.value.electricity_amount)
        }
      }

      // 添加调试日志
      console.log('📤 [Bulk Payment] Payload:', payload)

      const response = await paymentApi.createBulkPayment(payload)

      console.log('✅ [Bulk Payment] Response:', response.data)

      if (response.data.success) {
        ElMessage.success(`收租记录创建成功！实收：${formatAmount(Number(response.data.total_actual || 0))}`)
        paymentDialogVisible.value = false
        // 刷新列表与房间状态（用于重新计算欠租/到期）
        loadReadings()
        loadRooms()
      }
    } catch (error: any) {
      console.error('Failed to create payment:', error)
      ElMessage.error(error.response?.data?.detail || '创建收租记录失败')
    } finally {
      paymentLoading.value = false
    }
  }

  return {
    paymentDialogVisible,
    paymentForm,
    paymentLoading,
    showPaymentDialog,
    submitPayment,
  }
}
