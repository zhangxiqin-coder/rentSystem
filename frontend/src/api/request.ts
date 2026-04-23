import axios, {
  type AxiosInstance,
  type AxiosError,
  type InternalAxiosRequestConfig,
  type AxiosResponse,
} from 'axios'
import type { ApiResponse } from '@/types'
import { decryptToken, isTokenValid } from '@/utils/crypto'

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

// Request interceptor
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Get and decrypt token from localStorage
    const encryptedToken = localStorage.getItem('access_token')
    if (encryptedToken && isTokenValid(encryptedToken)) {
      const token = decryptToken(encryptedToken)
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }

    // Add CSRF token for state-changing requests
    if (config.method !== 'get' && config.method !== 'head') {
      const csrfToken = getCsrfToken()
      if (csrfToken) {
        config.headers['X-CSRF-Token'] = csrfToken
      }
    }

    return config
  },
  (error: AxiosError) => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor
request.interceptors.response.use(
  (response: AxiosResponse) => {
    // Store CSRF token if present in response headers
    const csrfToken = response.headers['x-csrf-token']
    if (csrfToken) {
      sessionStorage.setItem('csrf_token', csrfToken)
    }
    return response
  },
  (error: AxiosError<ApiResponse<unknown>>) => {
    if (error.response) {
      // Server responded with error status
      const { status, data } = error.response

      switch (status) {
        case 401:
          // Unauthorized - clear token and redirect to login
          localStorage.removeItem('access_token')
          localStorage.removeItem('user')
          sessionStorage.removeItem('csrf_token')
          window.location.href = '/login'
          break
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
