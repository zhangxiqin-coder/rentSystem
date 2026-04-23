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

// User types
export interface User {
  id: number
  username: string
  email: string
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
  email: string
  password: string
  full_name?: string
}

// Room types
export interface Room {
  id: number
  room_number: string
  building?: string
  floor?: number
  area?: number
  rent_amount: number
  deposit_amount: number
  status: 'available' | 'occupied' | 'maintenance'
  tenant_id?: number
  landlord_id: number
  description?: string
  created_at: string
  updated_at: string
}

export interface CreateRoomRequest {
  room_number: string
  building?: string
  floor?: number
  area?: number
  rent_amount: number
  deposit_amount: number
  description?: string
}

export interface UpdateRoomRequest extends Partial<CreateRoomRequest> {
  status?: 'available' | 'occupied' | 'maintenance'
  tenant_id?: number
}

// Payment types
export interface Payment {
  id: number
  room_id: number
  tenant_id: number
  amount: number
  payment_type: 'rent' | 'deposit' | 'utility' | 'other'
  payment_date: string
  due_date?: string
  status: 'pending' | 'completed' | 'overdue' | 'cancelled'
  payment_method?: string
  description?: string
  created_at: string
  updated_at: string
}

export interface CreatePaymentRequest {
  room_id: number
  amount: number
  payment_type: 'rent' | 'deposit' | 'utility' | 'other'
  payment_date?: string
  due_date?: string
  payment_method?: string
  description?: string
}

// Utility Reading types
export interface UtilityReading {
  id: number
  room_id: number
  utility_type: 'water' | 'electricity' | 'gas'
  reading_date: string
  previous_reading: number
  current_reading: number
  usage: number
  amount: number
  recorded_by: number
  notes?: string
  created_at: string
  updated_at: string
}

export interface CreateUtilityReadingRequest {
  room_id: number
  utility_type: 'water' | 'electricity' | 'gas'
  reading_date: string
  current_reading: number
  notes?: string
}

// Utility Rate types
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
