import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import { encryptToken, decryptToken } from '@/utils/crypto'
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

      // Store encrypted token in localStorage
      const encryptedToken = encryptToken(token.value)
      localStorage.setItem('access_token', encryptedToken)
      localStorage.setItem('user', JSON.stringify(user.value))

      // Fetch and store CSRF token
      try {
        const csrfResponse = await authApi.getCsrfToken()
        if (csrfResponse.data.data.csrf_token) {
          sessionStorage.setItem('csrf_token', csrfResponse.data.data.csrf_token)
        }
      } catch (csrfError) {
        console.warn('Failed to fetch CSRF token:', csrfError)
      }

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
      // Decrypt and validate token
      const decryptedToken = decryptToken(storedToken)
      if (decryptedToken) {
        token.value = decryptedToken
        user.value = JSON.parse(storedUser)
      } else {
        // Token is invalid or expired, clear storage
        console.warn('Stored token is invalid or expired')
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')
      }
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
