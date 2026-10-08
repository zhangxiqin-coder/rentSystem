import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { paymentApi } from '@/api/payment'
import type { MergedReading } from '@/composables/useMergedReadings'
import { shouldIncludeRent, getCoveragePeriod } from '@/utils/paymentCycle'

export function usePaymentData(deps: {
  formatAmount: (value: number, currency?: string) => string
  loadReadings: () => Promise<void>
  loadRooms: () => Promise<void>
  payments?: { value: import('@/types').Payment[] }
}) {
  const { formatAmount, loadReadings, loadRooms, payments } = deps

  const paymentDialogVisible = ref(false)
  const paymentForm = ref({
    room_id: 0,
    reading_date: '',
    payment_date: new Date().toISOString().split('T')[0],
    rent_original: 0,
    rent_amount: 0,
    rentCyclePaid: false,
    water_original: 0,
    water_amount: 0,
    electricity_original: 0,
    electricity_amount: 0,
    payment_method: '微信支付',
    notes: '',
    period_start: '',
    period_end: '',
  })
  const paymentLoading = ref(false)

  const showPaymentDialog = (row: MergedReading) => {
    const water_amount = Number(row.water_reading?.amount || 0)
    const electricity_amount = Number(row.electricity_reading?.amount || 0)
    const cycle = Math.max(1, Number(row.payment_cycle || 1))

    // 季付/半年付：本周期房租已收过则房租=0，只收水电
    // （2026-09-30 102-2 事故：8-01已交4650，9-27标记已收弹窗又预填了房租）
    let rent_amount = Number(row.monthly_rent || 0) * cycle
    let rent_already_paid = false
    if (cycle > 1 && payments && !shouldIncludeRent(row, payments.value)) {
      rent_amount = 0
      rent_already_paid = true
    }

    // 计算覆盖周期：下一个未付期（预收口径）。
    // 修复前 bug：取"今天所在期"且不看付款记录——租客已预付到 10-09
    // 时弹窗仍显示 09-10~10-09（已收过的期）。现改为 v5 起租日网格
    // 推"最后已付期+1"，与 shouldIncludeRent/到期列表同一口径。
    const coverage = payments ? getCoveragePeriod(row, payments.value) : null
    const periodStart = coverage?.start || ''
    const periodEnd = coverage?.end || ''

    paymentForm.value = {
      room_id: row.room_id,
      reading_date: row.reading_date,
      payment_date: new Date().toISOString().split('T')[0],
      // 归零时 original 一并归 0：否则底部"原始总额/总折扣"会显示 4650，
      // 误导为打折。信息由 rentCyclePaid 提示条承担（"本周期房租已收"）
      rent_original: rent_amount,
      rent_amount: rent_amount,
      rentCyclePaid: rent_already_paid,
      water_original: water_amount,
      water_amount: water_amount,
      electricity_original: electricity_amount,
      electricity_amount: electricity_amount,
      payment_method: '微信支付',
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
        payment_date: paymentForm.value.payment_date || new Date().toISOString().split('T')[0],
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
