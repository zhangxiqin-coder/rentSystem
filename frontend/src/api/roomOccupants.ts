/**
 * 房间居住人管理API（多租客：主租客 + 亲友）
 */
import request from './request'
import type { RoomOccupant, RoomOccupantCreate, RoomOccupantUpdate } from '@/types'

export const roomOccupantsApi = {
  // 获取房间的所有居住人
  listByRoom: async (roomId: number) => {
    const response = await request.get<RoomOccupant[]>(`/api/v1/room-occupants/room/${roomId}`)
    return response.data
  },

  // 添加居住人
  add: async (roomId: number, data: RoomOccupantCreate) => {
    const response = await request.post<RoomOccupant>(`/api/v1/room-occupants/room/${roomId}`, data)
    return response.data
  },

  // 更新居住人信息
  update: async (occupantId: number, data: RoomOccupantUpdate) => {
    const response = await request.put<RoomOccupant>(`/api/v1/room-occupants/${occupantId}`, data)
    return response.data
  },

  // 移除居住人
  remove: async (occupantId: number) => {
    await request.delete(`/api/v1/room-occupants/${occupantId}`)
  }
}
