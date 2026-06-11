import request from './request'
import type {
  Room,
  CreateRoomRequest,
  UpdateRoomRequest,
  ApiResponse,
  ApiListResponse,
  PaginationParams,
} from '@/types'

export const roomApi = {
  // Get all rooms
  list: async () => {
    const response = await request.get<ApiListResponse<Room>>('/api/v1/rooms', { params: { page: 1, size: 1000 } })
    return response.data.items || []
  },

  // Get all rooms with pagination
  getRooms: (params?: PaginationParams) =>
    request.get<ApiListResponse<Room>>('/api/v1/rooms', { params }),

  // Get room by id
  getRoom: (id: number) => request.get<ApiResponse<Room>>(`/api/v1/rooms/${id}`),

  // Get rooms expiring soon
  getExpiringSoon: (days: number = 7) =>
    request.get<Room[]>('/api/v1/rooms/expiring-soon', { params: { days } }),

  // Create room
  createRoom: (data: CreateRoomRequest) => request.post<Room>('/api/v1/rooms', data),

  // Update room
  updateRoom: (id: number, data: UpdateRoomRequest) =>
    request.put<Room>(`/api/v1/rooms/${id}`, data),

  // Delete room
  deleteRoom: (id: number) => request.delete<void>(`/api/v1/rooms/${id}`),

  // 退租房间
  checkoutRoom: (id: number, data: {
    refund_amount: number
    refund_date: string
    refund_reason?: string
    payment_method: string
  }) => request.post<ApiResponse<any>>(`/api/v1/rooms/${id}/checkout`, data),

  // 入住房间
  checkinRoom: (id: number, data: {
    tenant_name?: string
    tenant_phone?: string
    tenant_id_card?: string
    lease_start: string
    lease_end: string
    monthly_rent?: number
    deposit_amount?: number
    payment_cycle?: number
    initial_electricity_reading?: number
    initial_water_reading?: number
  }) => request.post<ApiResponse<Room>>(`/api/v1/rooms/${id}/checkin`, data),

  // 续租房间
  renewLease: (id: number, data: {
    months: number
    monthly_rent?: number
    notes?: string
  }) => request.post<ApiResponse<{
    message: string
    room_id: number
    room_number: string
    old_lease_end: string
    new_lease_end: string
    months_added: number
    monthly_rent: number
  }>>(`/api/v1/rooms/${id}/renew`, data),

  // 批量导入房间
  batchImport: (formData: FormData) => {
    return request.post<ApiResponse<{
      message: string
      success_count: number
      failed_count: number
      errors: string[]
    }>>('/api/v1/rooms/batch-import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },
}
