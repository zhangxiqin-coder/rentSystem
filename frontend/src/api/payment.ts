import request from './request'

export interface UtilityPaymentItem {
  utility_type: 'water' | 'electricity'
  amount: number
  original_amount: number
  discount: number
}

export interface BulkPaymentCreate {
  room_id: number
  reading_date: string
  rent_amount: number
  rent_original: number
  water_charge?: UtilityPaymentItem
  electricity_charge?: UtilityPaymentItem
  payment_date?: string
  payment_method?: string
  notes?: string
}

export interface BulkPaymentResponse {
  success: boolean
  message: string
  payments: any[]
  total_original: number
  total_actual: number
  total_discount: number
}

export const paymentApi = {
  // 批量创建收租记录
  createBulkPayment: (data: BulkPaymentCreate) =>
    request.post<BulkPaymentResponse>('/api/v1/payments/bulk', data),

  // 获取年度统计
  getYearlyStats: (year?: number) =>
    request.get('/api/v1/payments/stats/yearly', { params: { year } }),

  // 获取房间账单
  getRoomBilling: (roomId: number, year?: number) =>
    request.get(`/api/v1/payments/stats/room/${roomId}`, { params: { year } })
}
