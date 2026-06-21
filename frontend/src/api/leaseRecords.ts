/**
 * 租赁记录API
 */
import request from './request'
import type { ApiResponse, LeaseRecord, LeaseRecordCreate, LeaseRecordUpdate } from '@/types'

export const leaseRecordsApi = {
  // 获取租赁记录列表
  list: async (params?: { tenant_id?: number; room_id?: number; is_active?: boolean; skip?: number; limit?: number }) => {
    const response = await request.get<LeaseRecord[]>('/api/v1/lease-records', { params })
    return response.data
  },

  // 获取租赁记录详情
  get: async (id: number) => {
    const response = await request.get<LeaseRecord>(`/api/v1/lease-records/${id}`)
    return response.data
  },

  // 创建租赁记录（入住操作）
  create: async (data: LeaseRecordCreate) => {
    const response = await request.post<ApiResponse<LeaseRecord>>('/api/v1/lease-records', data)
    return response.data.data
  },

  // 更新租赁记录
  update: async (id: number, data: LeaseRecordUpdate) => {
    const response = await request.put<ApiResponse<LeaseRecord>>(`/api/v1/lease-records/${id}`, data)
    return response.data.data
  },

  // 删除租赁记录
  delete: async (id: number) => {
    const response = await request.delete<ApiResponse<null>>(`/api/v1/lease-records/${id}`)
    return response.data.data
  },

  // 结束租赁（退租操作）
  endLease: async (id: number) => {
    const response = await request.post<ApiResponse<LeaseRecord>>(`/api/v1/lease-records/${id}/end-lease`)
    return response.data.data
  },

  // 恢复租赁（恢复入住操作）
  restore: async (id: number) => {
    const response = await request.post<ApiResponse<LeaseRecord>>(`/api/v1/lease-records/${id}/restore`)
    return response.data.data
  }
}
