// API Response types
export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface ApiListResponse<T> {
  code: number
  message: string
  data: {
    items: T[]
    total: number
    page: number
    size: number
  }
}

// User types（统一前后端）
export interface User {
  id: number
  username: string
  email?: string
  full_name?: string
  role: 'admin' | 'landlord' | 'tenant'
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export interface RegisterRequest {
  username: string
  email?: string
  password: string
  full_name?: string
}

// Room types（统一前后端）
export interface Room {
  id: number
  room_number: string
  building?: string
  floor?: number
  area?: number
  monthly_rent: number
  deposit_amount?: number
  payment_cycle: number
  status: 'available' | 'occupied' | 'maintenance'
  tenant_name?: string
  tenant_phone?: string
  lease_start?: string
  lease_end?: string
  last_payment_date?: string
  description?: string
  created_at: string
  updated_at: string
}

export interface CreateRoomRequest {
  room_number: string
  building?: string
  floor?: number
  area?: number
  monthly_rent: number
  deposit_amount?: number
  payment_cycle?: number
  status?: 'available' | 'occupied' | 'maintenance'
  tenant_name?: string
  tenant_phone?: string
  lease_start?: string
  lease_end?: string
  description?: string
}

export interface UpdateRoomRequest extends Partial<CreateRoomRequest> {}

// Payment types（统一前后端）
export interface Payment {
  id: number
  room_id: number
  amount: number
  payment_type: 'rent' | 'deposit' | 'utility' | 'other'
  payment_date: string
  due_date?: string
  status: 'pending' | 'completed' | 'overdue' | 'cancelled'
  payment_method?: string
  description?: string
  receipt_image?: string
  created_at: string
  updated_at: string
}

export interface CreatePaymentRequest {
  room_id: number
  amount?: number  // 租金类型自动计算，其他类型必填
  payment_type: 'rent' | 'deposit' | 'utility' | 'other'
  payment_date?: string
  due_date?: string
  status?: 'pending' | 'completed' | 'overdue' | 'cancelled'
  payment_method?: string
  description?: string
  receipt_image?: string
}

export interface UpdatePaymentRequest extends Partial<CreatePaymentRequest> {}

// Utility Reading types（统一前后端）
export interface UtilityReading {
  id: number
  room_id: number
  utility_type: 'water' | 'electricity' | 'gas'
  reading: number
  reading_date: string
  previous_reading?: number
  usage?: number
  amount?: number
  rate_used?: number
  recorded_by?: number
  notes?: string
  created_at: string
  updated_at: string
}

export interface CreateUtilityReadingRequest {
  room_id: number
  utility_type: 'water' | 'electricity' | 'gas'
  reading: number
  reading_date: string
  notes?: string
}

export interface UpdateUtilityReadingRequest {
  notes?: string
}

// Utility Rate types（统一前后端）
export interface UtilityRate {
  id: number
  utility_type: 'water' | 'electricity' | 'gas'
  rate_per_unit: number
  effective_date: string
  is_active: boolean
  description?: string
  created_at: string
  updated_at: string
}

export interface CreateUtilityRateRequest {
  utility_type: 'water' | 'electricity' | 'gas'
  rate_per_unit: number
  effective_date: string
  description?: string
}

export interface UpdateUtilityRateRequest {
  rate_per_unit?: number
  effective_date?: string
  is_active?: boolean
  description?: string
}

// Common types
export interface PaginationParams {
  page?: number
  size?: number
  search?: string
  sort_by?: string
  order?: 'asc' | 'desc'
}

export interface IdParams {
  id: number | string
}

// Statistics types
export interface RoomStats {
  total_rooms: number
  available_rooms: number
  occupied_rooms: number
  maintenance_rooms: number
  occupancy_rate: number
}

export interface RevenueStats {
  total_revenue: number
  rent_revenue: number
  utility_revenue: number
  deposit_revenue: number
  by_month: { month: string; amount: number }[]
}

export interface UtilityStats {
  total_amount: number
  water_amount: number
  electricity_amount: number
  gas_amount: number
  by_month: { month: string; amount: number; type: string }[]
}

export interface OverdueInfo {
  room_id: number
  room_number: string
  tenant_name: string
  due_date: string
  overdue_days: number
  amount: number
}

export interface ExpiringLease {
  room_id: number
  room_number: string
  tenant_name: string
  lease_end: string
  days_remaining: number
}
