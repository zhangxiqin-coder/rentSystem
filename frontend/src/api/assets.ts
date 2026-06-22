import axios from 'axios'
import type { AssetPlatform, AssetRecord, AssetSummary } from '@/types'

// 手动创建带认证的请求
async function authRequest<T>(config: {
  method: 'get' | 'post' | 'put' | 'delete'
  url: string
  data?: any
  params?: any
}): Promise<T> {
  const token = (() => {
    try {
      const encrypted = localStorage.getItem('access_token')
      if (!encrypted) return null
      const decoded = atob(encrypted)
      const key = import.meta.env.VITE_ENCRYPTION_KEY || 'dev-only-rent-system-encryption-key-2026'
      let result = ''
      for (let i = 0; i < decoded.length; i++) {
        result += String.fromCharCode(decoded.charCodeAt(i) ^ key.charCodeAt(i % key.length))
      }
      const parts = result.split('|')
      return parts.length === 4 ? parts[3] : null
    } catch {
      return null
    }
  })()

  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // 加CSRF token（非GET请求）
  if (config.method !== 'get') {
    const csrfToken = sessionStorage.getItem('csrf_token')
    if (csrfToken) {
      headers['X-CSRF-Token'] = csrfToken
    }
  }

  const res = await axios({
    method: config.method,
    url: config.url,
    data: config.data,
    params: config.params,
    headers
  })
  return res.data
}

export const assetApi = {
  // 平台管理
  async listPlatforms(): Promise<AssetPlatform[]> {
    return authRequest({ method: 'get', url: '/api/v1/assets/platforms' })
  },

  async createPlatform(data: { name: string; current_balance?: number; total_earnings?: number }): Promise<AssetPlatform> {
    return authRequest({ method: 'post', url: '/api/v1/assets/platforms', data })
  },

  async updatePlatform(id: number, data: Partial<AssetPlatform>): Promise<AssetPlatform> {
    return authRequest({ method: 'put', url: `/api/v1/assets/platforms/${id}`, data })
  },

  async deletePlatform(id: number): Promise<void> {
    await authRequest({ method: 'delete', url: `/api/v1/assets/platforms/${id}` })
  },

  // 变动记录
  async createRecord(data: {
    platform_id: number
    record_type: 'balance' | 'transfer_in' | 'transfer_out'
    reported_balance?: number | null
    reported_earnings?: number | null
    amount?: number | null
    notes?: string | null
  }): Promise<AssetRecord> {
    return authRequest({ method: 'post', url: '/api/v1/assets/records', data })
  },

  async listRecords(platform_id?: number, limit?: number): Promise<AssetRecord[]> {
    const params: any = {}
    if (platform_id) params.platform_id = platform_id
    if (limit) params.limit = limit
    return authRequest({ method: 'get', url: '/api/v1/assets/records', params })
  },

  // 总览
  async getSummary(): Promise<AssetSummary> {
    return authRequest({ method: 'get', url: '/api/v1/assets/summary' })
  },

  // 编辑记录（超级管理员）
  async updateRecord(id: number, data: {
    reported_balance?: number | null
    reported_earnings?: number | null
    amount?: number | null
    notes?: string | null
  }): Promise<AssetRecord> {
    return authRequest({ method: 'put', url: `/api/v1/assets/records/${id}`, data })
  }
}
