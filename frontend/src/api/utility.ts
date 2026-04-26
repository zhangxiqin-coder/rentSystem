import request from './request'
import type {
  UtilityReading,
  CreateUtilityReadingRequest,
  UtilityRate,
  CreateUtilityRateRequest,
  ApiResponse,
  ApiListResponse,
  PaginationParams,
} from '@/types'

export const utilityApi = {
  // Get all readings
  getReadings: (params?: PaginationParams) =>
    request.get<ApiListResponse<UtilityReading>>('/api/v1/utility/readings', { params }),

  // Get reading by id
  getReading: (id: number) =>
    request.get<ApiResponse<UtilityReading>>(`/api/v1/utility/readings/${id}`),

  // Create reading
  createReading: (data: CreateUtilityReadingRequest) =>
    request.post<ApiResponse<UtilityReading>>('/api/v1/utility/readings', data),

  // Update reading
  updateReading: (id: number, data: Partial<CreateUtilityReadingRequest>) =>
    request.put<ApiResponse<UtilityReading>>(`/api/v1/utility/readings/${id}`, data),

  // Delete reading
  deleteReading: (id: number) =>
    request.delete<ApiResponse<void>>(`/api/v1/utility/readings/${id}`),

  // Get readings by room
  getReadingsByRoom: (roomId: number, params?: PaginationParams) =>
    request.get<ApiListResponse<UtilityReading>>(`/api/v1/rooms/${roomId}/utility-readings`, {
      params,
    }),

  // Get all rates
  getRates: (params?: PaginationParams) =>
    request.get<ApiListResponse<UtilityRate>>('/api/v1/utility/rates', { params }),

  // Get rate by id
  getRate: (id: number) => request.get<ApiResponse<UtilityRate>>(`/api/v1/utility/rates/${id}`),

  // Create rate
  createRate: (data: CreateUtilityRateRequest) =>
    request.post<ApiResponse<UtilityRate>>('/api/v1/utility/rates', data),

  // Update rate
  updateRate: (id: number, data: Partial<CreateUtilityRateRequest>) =>
    request.put<ApiResponse<UtilityRate>>(`/api/v1/utility/rates/${id}`, data),

  // Delete rate
  deleteRate: (id: number) => request.delete<ApiResponse<void>>(`/api/v1/utility/rates/${id}`),

  // Get active rates
  getActiveRates: () => request.get<ApiResponse<UtilityRate[]>>('/api/v1/utility/rates/active'),

  // Batch create readings
  batchCreate: (data: {
    readings: Array<{
      room_id: number
      utility_type: string
      reading: number
    }>
    reading_date: string
    notes?: string
  }) =>
    request.post<{
      success_count: number
      failed_count: number
      total_amount: number
      readings: UtilityReading[]
      errors: string[]
    }>('/api/v1/utility/readings/batch', data),
}
