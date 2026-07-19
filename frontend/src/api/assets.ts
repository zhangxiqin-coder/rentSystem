import axios from 'axios'
import type { AssetPlatform, AssetRecord, AssetSummary, AssetTrend, AssetItem, PortfolioSummary, PlatformItemsResponse, FixedAsset } from '@/types'

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
    let csrfToken = sessionStorage.getItem('csrf_token')

    // 如果没有CSRF token，主动获取
    if (!csrfToken && token) {
      try {
        const csrfRes = await axios({
          method: 'get',
          url: '/api/v1/auth/csrf-token',
          headers: { Authorization: `Bearer ${token}` }
        })
        csrfToken = csrfRes.headers['x-csrf-token'] as string
        if (csrfToken) {
          sessionStorage.setItem('csrf_token', csrfToken)
        }
      } catch {
        console.warn('⚠️ [Assets API] Failed to fetch CSRF token')
      }
    }

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
  },

  // 趋势
  async getTrend(): Promise<AssetTrend> {
    return authRequest({ method: 'get', url: '/api/v1/assets/trend' })
  },

  // 赵平飞年度统计
  async getZhaopingfeiSummary(): Promise<{
    years: Array<{ year: string; transfer_in: number; transfer_out: number; net: number }>
    total_in: number
    total_out: number
    total_net: number
  }> {
    return authRequest({ method: 'get', url: '/api/v1/assets/zhaopingfei-summary' })
  },

  // 持仓明细
  async listItems(): Promise<AssetItem[]> {
    return authRequest({ method: 'get', url: '/api/v1/assets/items' })
  },

  async createItem(data: {
    name: string
    code?: string | null
    amount: number
    stock_pct: number
    bond_pct: number
    cash_pct: number
    commodity_pct: number
    fixed_income_pct: number
    other_pct: number
    platform_id?: number | null
  }): Promise<AssetItem> {
    return authRequest({ method: 'post', url: '/api/v1/assets/items', data })
  },

  async updateItem(id: number, data: Partial<AssetItem>): Promise<AssetItem> {
    return authRequest({ method: 'put', url: `/api/v1/assets/items/${id}`, data })
  },

  async deleteItem(id: number): Promise<void> {
    await authRequest({ method: 'delete', url: `/api/v1/assets/items/${id}` })
  },

  async getPortfolioSummary(): Promise<PortfolioSummary> {
    return authRequest({ method: 'get', url: '/api/v1/assets/portfolio-summary' })
  },

  async getPlatformItems(): Promise<PlatformItemsResponse> {
    return authRequest({ method: 'get', url: '/api/v1/assets/platform-items' })
  },

  // 固定资产
  async listFixedAssets(): Promise<FixedAsset[]> {
    return authRequest({ method: 'get', url: '/api/v1/assets/fixed-assets' })
  },

  // 租金汇总（从 rooms 表实时算，替代曾经硬编码的 xiqin 租金数字）
  async getRentSummary(): Promise<{
    monthly_total: number
    room_count: number
    ytd_total: number
    annual_projected: number
    months_elapsed: number
  }> {
    return authRequest({ method: 'get', url: '/api/v1/assets/rent-summary' })
  },

  async createFixedAsset(data: { name: string; category: string; estimated_value: number; role?: string; monthly_rent?: number; notes?: string }): Promise<FixedAsset> {
    return authRequest({ method: 'post', url: '/api/v1/assets/fixed-assets', data })
  },

  async updateFixedAsset(id: number, data: Partial<FixedAsset>): Promise<FixedAsset> {
    return authRequest({ method: 'put', url: `/api/v1/assets/fixed-assets/${id}`, data })
  },

  async deleteFixedAsset(id: number): Promise<void> {
    await authRequest({ method: 'delete', url: `/api/v1/assets/fixed-assets/${id}` })
  }
}
