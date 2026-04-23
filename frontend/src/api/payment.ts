import request from './request'
import type {
  Payment,
  CreatePaymentRequest,
  ApiResponse,
  ApiListResponse,
  PaginationParams,
} from '@/types'

export const paymentApi = {
  // Get all payments with pagination
  getPayments: (params?: PaginationParams) =>
    request.get<ApiListResponse<Payment>>('/api/v1/payments', { params }),

  // Get payment by id
  getPayment: (id: number) => request.get<ApiResponse<Payment>>(`/api/v1/payments/${id}`),

  // Create payment
  createPayment: (data: CreatePaymentRequest) =>
    request.post<ApiResponse<Payment>>('/api/v1/payments', data),

  // Update payment
  updatePayment: (id: number, data: Partial<CreatePaymentRequest>) =>
    request.put<ApiResponse<Payment>>(`/api/v1/payments/${id}`, data),

  // Delete payment
  deletePayment: (id: number) => request.delete<ApiResponse<void>>(`/api/v1/payments/${id}`),

  // Get payments by room
  getPaymentsByRoom: (roomId: number, params?: PaginationParams) =>
    request.get<ApiListResponse<Payment>>(`/api/v1/rooms/${roomId}/payments`, { params }),
}
