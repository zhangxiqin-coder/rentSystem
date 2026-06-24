import request from './request'

export interface OverdueRoom {
  room_id: number
  room_number: string
  tenant_name: string | null
  monthly_rent: number
  payment_cycle: number
  rent_due: number
  utility_amount: number
  total_amount: number
  target_due: string
  days_to_due: number
  overdue_days?: number
  days_until_due?: number
  last_payment_date: string | null
  lease_start: string | null
}

export interface OverdueRoomsResponse {
  overdue: OverdueRoom[]
  expiring: OverdueRoom[]
  overdue_count: number
  expiring_count: number
}

export interface ReminderItem {
  room_id: number
  room_number: string
  reminder_type: string
  reminder_date: string
  days_left: number
  amount: number
  tenant_name: string | null
  message: string
  breakdown?: {
    rent: number
    water: number
    electricity: number
  }
}

export interface ReminderResponse {
  total: number
  reminders: ReminderItem[]
  as_of_date: string
}

export interface RemindersSummary {
  lease_expiry: {
    next_7_days: number
    next_30_days: number
    overdue: number
  }
  payment_due: {
    today: number
    next_7_days: number
    overdue: number
  }
  total_reminders: number
}

export const remindersApi = {
  // 获取即将到期的提醒
  getUpcomingReminders: (params?: {
    days_ahead?: number
    include_overdue?: boolean
    advance_rent_days?: number
  }) => request.get<ReminderResponse>('/api/v1/reminders/upcoming', { params }),

  // 获取逾期房间列表(推荐使用)
  getOverdueRooms: (params?: {
    advance_rent_days?: number
  }) => request.get<OverdueRoomsResponse>('/api/v1/reminders/overdue-rooms', { params }),

  // 获取提醒摘要统计
  getRemindersSummary: () => request.get<RemindersSummary>('/api/v1/reminders/summary'),

  // 发送提醒通知
  sendReminderNotifications: (params?: {
    days_ahead?: number
  }) => request.post('/api/v1/reminders/send-notifications', null, { params }),

  // 为单个房间发送催租通知
  sendRentReminder: (roomId: number) =>
    request.post(`/api/v1/reminders/send-rent-reminder/${roomId}`),
}
