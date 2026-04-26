import axios, {
  type AxiosInstance,
  type AxiosError,
  type InternalAxiosRequestConfig,
  type AxiosResponse,
} from 'axios'
import type { ApiResponse } from '@/types'
import { decryptToken, encryptToken, isTokenValid } from '@/utils/crypto'

// Get CSRF token from sessionStorage
const getCsrfToken = (): string | null => {
  return sessionStorage.getItem('csrf_token')
}

// Create axios instance
const request: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Token refresh state management
let isRefreshing = false
let failedQueue: Array<{
  resolve: (value?: unknown) => void
  reject: (reason?: unknown) => void
}> = []

// Process the queue of failed requests
const processQueue = (error: Error | null, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })

  failedQueue = []
}

// Clear authentication data
const clearAuthData = () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('user')
  sessionStorage.removeItem('csrf_token')
}

// Request interceptor
request.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    console.log('📤 [Request]', config.method?.toUpperCase(), config.url)

    // Get and decrypt token from localStorage
    const encryptedToken = localStorage.getItem('access_token')
    if (encryptedToken && isTokenValid(encryptedToken)) {
      const token = decryptToken(encryptedToken)
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
        console.log('🎫 [Request] Token added to headers')
      }
    }

    // Add CSRF token for state-changing requests (except login/register)
    const isAuthEndpoint = config.url?.includes('/login') || config.url?.includes('/register') || config.url?.includes('/csrf-token')
    
    if (config.method !== 'get' && config.method !== 'head' && !isAuthEndpoint) {
      let csrfToken = getCsrfToken()
      
      // If no CSRF token, fetch it first
      if (!csrfToken && encryptedToken) {
        try {
          console.log('🔒 [Request] No CSRF token, fetching...')
          const response = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/auth/csrf-token`, {
            headers: {
              Authorization: config.headers.Authorization
            }
          })
          csrfToken = response.headers['x-csrf-token']
          if (csrfToken) {
            sessionStorage.setItem('csrf_token', csrfToken)
            console.log('🔒 [Request] CSRF token fetched and saved')
          }
        } catch (error) {
          console.error('❌ [Request] Failed to fetch CSRF token:', error)
        }
      }
      
      if (csrfToken) {
        config.headers['X-CSRF-Token'] = csrfToken
        console.log('🔒 [Request] CSRF token added')
      } else {
        console.warn('⚠️ [Request] CSRF token missing, request may fail')
      }
    }

    console.log('📋 [Request] Headers:', JSON.stringify(config.headers, null, 2))
    return config
  },
  (error: AxiosError) => {
    console.error('❌ [Request] Error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor
request.interceptors.response.use(
  (response: AxiosResponse) => {
    console.log('✅ [Response]', response.config.method?.toUpperCase(), response.config.url, 'Status:', response.status)

    // Store CSRF token if present in response headers
    const csrfToken = response.headers['x-csrf-token']
    if (csrfToken) {
      sessionStorage.setItem('csrf_token', csrfToken)
      console.log('🔒 [Response] CSRF token updated')
    }
    return response
  },
  async (error: AxiosError<ApiResponse<unknown>>) => {
    console.error('❌ [Response] Error:', error.config?.method?.toUpperCase(), error.config?.url)
    console.error('❌ [Response] Error details:', {
      message: error.message,
      code: error.code,
      status: error.response?.status,
      data: error.response?.data,
      hasRequest: !!error.request,
      hasResponse: !!error.response
    })

    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    if (error.response) {
      const { status, data } = error.response

      // Handle 401 Unauthorized
      if (status === 401 && originalRequest && !originalRequest._retry) {
        // If this is a refresh token request, clear auth and redirect
        if (originalRequest.url?.includes('/refresh-token')) {
          clearAuthData()
          window.location.href = '/login'
          return Promise.reject(error)
        }

        // If already refreshing, add to queue
        if (isRefreshing) {
          return new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject })
          })
            .then(() => {
              // Retry the original request with new token
              const encryptedToken = localStorage.getItem('access_token')
              if (encryptedToken) {
                const token = decryptToken(encryptedToken)
                if (token) {
                  originalRequest.headers.Authorization = `Bearer ${token}`
                }
              }
              return request(originalRequest)
            })
            .catch((err) => {
              return Promise.reject(err)
            })
        }

        // Start token refresh process
        originalRequest._retry = true
        isRefreshing = true

        try {
          // Call refresh token endpoint
          const encryptedToken = localStorage.getItem('access_token')
          if (!encryptedToken) {
            throw new Error('No access token found')
          }

          const currentToken = decryptToken(encryptedToken)
          if (!currentToken) {
            throw new Error('Invalid or expired access token')
          }

          const response = await axios.post<ApiResponse<{ access_token: string }>>(
            `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/auth/refresh-token`,
            {},
            {
              headers: {
                Authorization: `Bearer ${currentToken}`,
              },
            }
          )

          const newToken = response.data.data.access_token

          // Encrypt and store new token
          const newEncryptedToken = encryptToken(newToken)
          localStorage.setItem('access_token', newEncryptedToken)

          // Update authorization header for current request
          originalRequest.headers.Authorization = `Bearer ${newToken}`

          // Process the queue with the new token
          processQueue(null, newToken)

          // Retry the original request
          return request(originalRequest)
        } catch (refreshError) {
          // Refresh failed, clear auth and redirect
          processQueue(refreshError as Error, null)
          clearAuthData()
          window.location.href = '/login'
          return Promise.reject(refreshError)
        } finally {
          isRefreshing = false
        }
      }

      // Handle other status codes
      switch (status) {
        case 403:
          console.error('Access forbidden')
          break
        case 404:
          console.error('Resource not found')
          break
        case 500:
          console.error('Internal server error')
          break
        default:
          console.error(data?.message || 'An error occurred')
      }

      return Promise.reject(data)
    } else if (error.request) {
      // Request was made but no response received
      console.error('Network error. Please check your connection.')
      return Promise.reject({ message: 'Network error. Please check your connection.' })
    } else {
      // Error in setting up the request
      console.error('Error:', error.message)
      return Promise.reject({ message: error.message })
    }
  }
)

export default request
