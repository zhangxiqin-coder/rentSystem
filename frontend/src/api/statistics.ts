import request from './request'
import type {
  ApiResponse,
  RoomStats,
  RevenueStats,
  UtilityStats,
  OverdueInfo,
  ExpiringLease,
} from '@/types'

export const statisticsApi = {
  // Get room statistics
  getRoomStats: () => request.get<ApiResponse<RoomStats>>('/api/v1/statistics/rooms'),

  // Get revenue statistics
  getRevenueStats: (params?: { start_date?: string; end_date?: string }) =>
    request.get<ApiResponse<RevenueStats>>('/api/v1/statistics/revenue', { params }),

  // Get utility statistics
  getUtilityStats: (params?: { start_date?: string; end_date?: string }) =>
    request.get<ApiResponse<UtilityStats>>('/api/v1/statistics/utility', { params }),

  // Get overdue payments info
  getOverdueInfo: () => request.get<ApiResponse<OverdueInfo[]>>('/api/v1/statistics/overdue'),

  // Get expiring leases
  getExpiringLeases: (days?: number) =>
    request.get<ApiResponse<ExpiringLease[]>>('/api/v1/statistics/expiring-leases', {
      params: { days },
    }),

  // Get dashboard summary
  getDashboardSummary: () =>
    request.get<ApiResponse<any>>('/api/v1/statistics/dashboard'),
}
