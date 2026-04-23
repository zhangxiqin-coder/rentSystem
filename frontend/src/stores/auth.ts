import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import type { User, LoginRequest, RegisterRequest } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const isAuthenticated = computed(() => !!token.value && !!user.value)
  const userRole = computed(() => user.value?.role || null)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isLandlord = computed(() => user.value?.role === 'landlord')
  const isTenant = computed(() => user.value?.role === 'tenant')

  // Actions
  const login = async (credentials: LoginRequest) => {
    loading.value = true
    error.value = null
    try {
      const response = await authApi.login(credentials)
      token.value = response.data.data.access_token
      user.value = response.data.data.user

      // Store in localStorage
      localStorage.setItem('access_token', token.value)
      localStorage.setItem('user', JSON.stringify(user.value))

      return true
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Login failed'
      return false
    } finally {
      loading.value = false
    }
  }

  const register = async (data: RegisterRequest) => {
    loading.value = true
    error.value = null
    try {
      const response = await authApi.register(data)
      user.value = response.data.data
      return true
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Registration failed'
      return false
    } finally {
      loading.value = false
    }
  }

  const getCurrentUser = async () => {
    loading.value = true
    error.value = null
    try {
      const response = await authApi.getCurrentUser()
      user.value = response.data.data
      return true
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to get user info'
      return false
    } finally {
      loading.value = false
    }
  }

  const logout = async () => {
    loading.value = true
    try {
      await authApi.logout()
    } catch (err) {
      console.error('Logout error:', err)
    } finally {
      // Clear state regardless of API call result
      token.value = null
      user.value = null
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      loading.value = false
    }
  }

  const initializeAuth = () => {
    const storedToken = localStorage.getItem('access_token')
    const storedUser = localStorage.getItem('user')

    if (storedToken && storedUser) {
      token.value = storedToken
      user.value = JSON.parse(storedUser)
    }
  }

  return {
    // State
    user,
    token,
    loading,
    error,
    // Getters
    isAuthenticated,
    userRole,
    isAdmin,
    isLandlord,
    isTenant,
    // Actions
    login,
    register,
    getCurrentUser,
    logout,
    initializeAuth,
  }
})
