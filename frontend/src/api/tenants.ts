/**
 * 租客管理API
 */
import request from './request'
import type { ApiResponse, Tenant, TenantCreate, TenantUpdate, LeaseRecord } from '@/types'

export const tenantsApi = {
  // 获取租客列表
  list: async (params?: { status?: string; search?: string }) => {
    const response = await request.get<Tenant[]>('/api/v1/tenants', { params })
    return response.data
  },

  // 获取租客详情
  get: async (id: number) => {
    const response = await request.get<Tenant>(`/api/v1/tenants/${id}`)
    return response.data
  },

  // 创建租客
  create: async (data: TenantCreate) => {
    const response = await request.post<Tenant>('/api/v1/tenants/', data)
    return response.data
  },

  // 更新租客
  update: async (id: number, data: TenantUpdate) => {
    const response = await request.put<Tenant>(`/api/v1/tenants/${id}`, data)
    return response.data
  },

  // 删除租客
  delete: async (id: number) => {
    const response = await request.delete<void>(`/api/v1/tenants/${id}`)
    return response.data
  },

  // 续租
  renew: async (tenantId: number, data: { months: number; monthly_rent?: number; notes?: string }) => {
    const response = await request.post<LeaseRecord>(`/api/v1/tenants/${tenantId}/renew`, data)
    return response.data
  },

  // 获取租客的租赁记录
  getLeases: async (tenantId: number) => {
    const response = await request.get<LeaseRecord[]>(`/api/v1/tenants/${tenantId}/leases`)
    return response.data
  }
}
