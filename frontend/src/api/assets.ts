import axios from 'axios'
import type { AssetPlatform, AssetRecord, AssetSummary } from '@/types'

export const assetApi = {
  // 平台管理
  async listPlatforms(): Promise<AssetPlatform[]> {
    const res = await axios.get('/api/v1/assets/platforms')
    return res.data
  },

  async createPlatform(data: { name: string; current_balance?: number; total_earnings?: number }): Promise<AssetPlatform> {
    const res = await axios.post('/api/v1/assets/platforms', data)
    return res.data
  },

  async updatePlatform(id: number, data: Partial<AssetPlatform>): Promise<AssetPlatform> {
    const res = await axios.put(`/api/v1/assets/platforms/${id}`, data)
    return res.data
  },

  async deletePlatform(id: number): Promise<void> {
    await axios.delete(`/api/v1/assets/platforms/${id}`)
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
    const res = await axios.post('/api/v1/assets/records', data)
    return res.data
  },

  async listRecords(platform_id?: number, limit?: number): Promise<AssetRecord[]> {
    const params: any = {}
    if (platform_id) params.platform_id = platform_id
    if (limit) params.limit = limit
    const res = await axios.get('/api/v1/assets/records', { params })
    return res.data
  },

  // 总览
  async getSummary(): Promise<AssetSummary> {
    const res = await axios.get('/api/v1/assets/summary')
    return res.data
  }
}
