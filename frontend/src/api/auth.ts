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

  // Get CSRF token
  getCsrfToken: () => request.get<ApiResponse<{ csrf_token: string }>>('/api/v1/auth/csrf-token'),

  // Refresh token
  refreshToken: () => request.post<ApiResponse<{ access_token: string }>>('/api/v1/auth/refresh-token'),

  // Change password
  changePassword: (data: { old_password: string; new_password: string }) =>
    request.post<ApiResponse<void>>('/api/v1/auth/change-password', data),

  // Update profile (full_name)
  updateProfile: (userId: number, data: { full_name?: string }) =>
    request.put<ApiResponse<User>>(`/api/v1/users/${userId}`, data),
}
