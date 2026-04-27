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
  // Get all rooms with pagination
  getRooms: (params?: PaginationParams) =>
    request.get<ApiListResponse<Room>>('/api/v1/rooms', { params }),

  // Get room by id
  getRoom: (id: number) => request.get<Room>(`/api/v1/rooms/${id}`),

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
    tenant_name: string
    tenant_phone: string
    lease_start: string
    lease_end: string
    deposit_amount?: number
    payment_cycle?: number
  }) => request.post<ApiResponse<Room>>(`/api/v1/rooms/${id}/checkin`, data),
}
