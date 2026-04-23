import request from './request'
import type { LoginRequest, LoginResponse, RegisterRequest, ApiResponse, User } from '@/types'

export const authApi = {
  // Login
  login: (data: LoginRequest) =>
    request.post<ApiResponse<LoginResponse>>('/api/v1/auth/login', data),

  // Register
  register: (data: RegisterRequest) =>
    request.post<ApiResponse<User>>('/api/v1/auth/register', data),

  // Get current user
  getCurrentUser: () => request.get<ApiResponse<User>>('/api/v1/auth/me'),

  // Logout
  logout: () => request.post<ApiResponse<void>>('/api/v1/auth/logout'),
}
