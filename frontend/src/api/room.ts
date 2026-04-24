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
  getRoom: (id: number) => request.get<ApiResponse<Room>>(`/api/v1/rooms/${id}`),

  // Get rooms expiring soon
  getExpiringSoon: (days: number = 7) =>
    request.get<Room[]>('/api/v1/rooms/expiring-soon', { params: { days } }),

  // Create room
  createRoom: (data: CreateRoomRequest) => request.post<ApiResponse<Room>>('/api/v1/rooms', data),

  // Update room
  updateRoom: (id: number, data: UpdateRoomRequest) =>
    request.put<ApiResponse<Room>>(`/api/v1/rooms/${id}`, data),

  // Delete room
  deleteRoom: (id: number) => request.delete<ApiResponse<void>>(`/api/v1/rooms/${id}`),
}
