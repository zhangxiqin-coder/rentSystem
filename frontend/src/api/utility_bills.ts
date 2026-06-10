/** 水电账单API */
import request from './request'

export interface UtilityBill {
  id: number
  series: string
  year: number
  month: number
  utility_type: 'water' | 'electric'
  cost: number
  notes?: string
  created_at: string
  updated_at: string
}

export interface UtilityBillCreate {
  series: string
  year: number
  month: number
  utility_type: 'water' | 'electric'
  cost?: number
  notes?: string
}

export interface UtilityBillUpdate {
  water_cost?: number
  electric_cost?: number
  notes?: string
}

export interface BillWithProfit extends UtilityBill {
  water_collected: number
  electric_collected: number
  water_profit: number
  electric_profit: number
  total_profit: number
}

export interface UtilityBillProfitStats {
  total_water_profit: number
  total_electric_profit: number
  total_profit: number
  monthly_breakdown: Array<{
    series: string
    year: number
    month: number
    water_collected: number
    water_cost: number
    water_profit: number
    electric_collected: number
    electric_cost: number
    electric_profit: number
    total_profit: number
  }>
}

export interface SeriesInfo {
  series: string
  room_count: number
}

export interface SeriesUtilityDetail {
  room_id: number
  room_number: string
  water_previous: number | null
  water_current: number | null
  water_usage: number | null
  water_amount: number | null
  water_date: string | null
  electric_previous: number | null
  electric_current: number | null
  electric_usage: number | null
  electric_amount: number | null
  electric_date: string | null
  total_amount: number
}

/** 获取系列列表 */
export const getSeriesList = async () => {
  const response = await request.get<SeriesInfo[]>('/api/v1/utility-bills/series')
  return response.data
}

/** 获取指定系列、指定年月的水电收租明细 */
export const getSeriesUtilityDetail = async (series: string, year: number, month: number) => {
  const response = await request.get<SeriesUtilityDetail[]>(`/api/v1/utility-bills/series/${series}/detail`, {
    params: { year, month }
  })
  return response.data
}

/** 获取水电账单列表 */
export const getUtilityBills = async () => {
  const response = await request.get<UtilityBill[]>('/api/v1/utility-bills/')
  return response.data
}

/** 获取水电收益统计 */
export const getUtilityBillProfit = async () => {
  const response = await request.get<UtilityBillProfitStats>('/api/v1/utility-bills/profit')
  return response.data
}

/** 创建水电账单 */
export const createUtilityBill = async (data: UtilityBillCreate) => {
  const response = await request.post<UtilityBill>('/api/v1/utility-bills/', data)
  return response.data
}

/** 获取单个水电账单（含收益） */
export const getUtilityBill = async (id: number) => {
  const response = await request.get<BillWithProfit>(`/api/v1/utility-bills/${id}`)
  return response.data
}

/** 更新水电账单 */
export const updateUtilityBill = async (id: number, data: UtilityBillUpdate) => {
  const response = await request.put<UtilityBill>(`/api/v1/utility-bills/${id}`, data)
  return response.data
}

/** 删除水电账单 */
export const deleteUtilityBill = async (id: number) => {
  const response = await request.delete<{ message: string }>(`/api/v1/utility-bills/${id}`)
  return response.data
}
