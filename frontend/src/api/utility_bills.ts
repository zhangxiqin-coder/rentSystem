/** 水电账单API */
import request from './request'

export interface UtilityBill {
  id: number
  year: number
  month: number
  water_cost: number
  electric_cost: number
  notes?: string
  created_at: string
  updated_at: string
}

export interface UtilityBillCreate {
  year: number
  month: number
  water_cost?: number
  electric_cost?: number
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

/** 获取水电账单列表 */
export const getUtilityBills = async () => {
  return request<UtilityBill[]>({
    url: '/api/v1/utility-bills/',
    method: 'GET'
  })
}

/** 获取水电收益统计 */
export const getUtilityBillProfit = async () => {
  return request<UtilityBillProfitStats>({
    url: '/api/v1/utility-bills/profit',
    method: 'GET'
  })
}

/** 创建水电账单 */
export const createUtilityBill = async (data: UtilityBillCreate) => {
  return request<UtilityBill>({
    url: '/api/v1/utility-bills/',
    method: 'POST',
    data
  })
}

/** 获取单个水电账单（含收益） */
export const getUtilityBill = async (id: number) => {
  return request<BillWithProfit>({
    url: `/api/v1/utility-bills/${id}`,
    method: 'GET'
  })
}

/** 更新水电账单 */
export const updateUtilityBill = async (id: number, data: UtilityBillUpdate) => {
  return request<UtilityBill>({
    url: `/api/v1/utility-bills/${id}`,
    method: 'PUT',
    data
  })
}

/** 删除水电账单 */
export const deleteUtilityBill = async (id: number) => {
  return request<{ message: string }>({
    url: `/api/v1/utility-bills/${id}`,
    method: 'DELETE'
  })
}
