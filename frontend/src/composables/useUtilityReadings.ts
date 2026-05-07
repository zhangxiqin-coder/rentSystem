import { ref, computed, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { utilityApi } from '@/api/utility'
import { paymentApi } from '@/api/payment'
import { mergeReadings, type MergedReading } from '@/composables/useMergedReadings'
import type { UtilityReading, Room, Payment as RentPayment } from '@/types'

export function useUtilityReadings(deps: {
  roomOptions: Ref<Room[]>
}) {
  const { roomOptions } = deps

  // 水电记录列表（原始数据）
  const readings = ref<UtilityReading[]>([])
  const allReadings = ref<UtilityReading[]>([])
  const loading = ref(false)

  // 支付记录（用于判断是否已收租）
  const payments = ref<RentPayment[]>([])

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

  // 加载所有水电记录（分页全部加载）
  const loadAllReadings = async (): Promise<UtilityReading[]> => {
    const loaded: UtilityReading[] = []
    let page = 1
    let hasMore = true

    while (hasMore) {
      const res = await utilityApi.getReadings({ page, size: 100 })
      const items = res.data.items || []
      loaded.push(...items)

      hasMore = items.length === 100
      page += 1
    }

    return loaded
  }

  // 加载水电记录列表（带分页和筛选）
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

      const [res, allItems, paymentsRes] = await Promise.all([
        utilityApi.getReadings(params),
        loadAllReadings(),
        paymentApi.getPayments({ size: 1000 })
      ])

      readings.value = res.data.items || []
      allReadings.value = allItems
      pagination.value.total = res.data.total || 0

      // 同时加载支付记录，用于判断是否已收租
      payments.value = paymentsRes.data.items || []
    } catch (error) {
      console.error('Failed to load readings:', error)
      ElMessage.error('加载水电记录失败')
    } finally {
      loading.value = false
    }
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

  // 合并后的记录列表（水和电在同一行）
  const mergedReadings = computed(() => {
    const map = new Map<string, MergedReading>()

    readings.value.forEach(reading => {
      const key = `${reading.room_id}_${reading.reading_date}`

      if (!map.has(key)) {
        // 获取房间信息（包含房租）
        const room = roomOptions.value.find(r => r.id === reading.room_id)
        const cycle = Math.max(1, Number(room?.payment_cycle || 1))
        map.set(key, {
          room_id: reading.room_id,
          reading_date: reading.reading_date,
          monthly_rent: room?.monthly_rent || 0,
          payment_cycle: room?.payment_cycle || 1,
          total_amount: Number(room?.monthly_rent || 0) * cycle,  // 总计包含房租，按周期计算
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

    // 检查每条记录是否已收租（使用payment_id字段）
    const result = Array.from(map.values())
    result.forEach(merged => {
      // 使用payment_id字段判断是否已支付（更准确）
      const waterPaid = (merged.water_reading as any)?.payment_id
      const elecPaid = (merged.electricity_reading as any)?.payment_id

      // 平摊房间（不收水电费）：以当月租金已收作为“已收租”标记
      const room = roomOptions.value.find(r => r.id === merged.room_id)
      const isZeroUtilityRoom = !!room &&
        Number(room.water_rate ?? 0) === 0 &&
        Number(room.electricity_rate ?? 0) === 0
      const waterAmount = Number(merged.water_reading?.amount || 0)
      const elecAmount = Number(merged.electricity_reading?.amount || 0)
      const isZeroUtilityChargeRecord = waterAmount + elecAmount === 0
      const readingDate = new Date(merged.reading_date)
      const rentPaidInSameMonth = payments.value.some(payment => {
        if (payment.room_id !== merged.room_id) return false
        if (payment.payment_type !== 'rent') return false
        if (payment.status !== 'completed') return false
        if (!payment.payment_date) return false

        const paidDate = new Date(payment.payment_date)
        return (
          paidDate.getFullYear() === readingDate.getFullYear() &&
          paidDate.getMonth() === readingDate.getMonth()
        )
      })

      merged.is_paid = !!(
        waterPaid ||
        elecPaid ||
        ((isZeroUtilityRoom || isZeroUtilityChargeRecord) && rentPaidInSameMonth)
      )
    })

    // 返回所有记录（包括已支付的），按日期倒序排列
    return result.sort((a, b) =>
      new Date(b.reading_date).getTime() - new Date(a.reading_date).getTime()
    )
  })

  return {
    readings,
    allReadings,
    loading,
    payments,
    pagination,
    filters,
    loadReadings,
    loadAllReadings,
    handleFilter,
    resetFilter,
    handlePageChange,
    handleSizeChange,
    mergedReadings,
  }
}
