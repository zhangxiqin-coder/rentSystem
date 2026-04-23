/**
 * Error message mappings for backend error codes
 */
export const ERROR_MESSAGES: Record<string, string> = {
  // Auth errors (AUTH_*)
  'AUTH_INVALID_CREDENTIALS': 'Invalid username or password',
  'AUTH_USER_NOT_FOUND': 'User not found',
  'AUTH_USER_DISABLED': 'Your account has been disabled',
  'AUTH_TOKEN_EXPIRED': 'Your session has expired, please login again',
  'AUTH_TOKEN_INVALID': 'Invalid authentication token',
  'AUTH_USERNAME_EXISTS': 'Username already exists',
  'AUTH_EMAIL_EXISTS': 'Email already registered',
  'AUTH_WEAK_PASSWORD': 'Password is too weak. It should contain at least 8 characters with letters and numbers',
  'AUTH_PASSWORDS_MISMATCH': 'Passwords do not match',
  'AUTH_INVALID_EMAIL': 'Invalid email address',
  'AUTH_INVALID_USERNAME': 'Username must be at least 3 characters long and contain only letters, numbers and underscores',

  // Validation errors (VALIDATION_*)
  'VALIDATION_ERROR': 'Please check your input and try again',
  'VALIDATION_REQUIRED': 'This field is required',
  'VALIDATION_EMAIL': 'Please enter a valid email address',
  'VALIDATION_MIN_LENGTH': 'This field is too short',
  'VALIDATION_MAX_LENGTH': 'This field is too long',
  'VALIDATION_PASSWORD_MISMATCH': 'Passwords do not match',

  // Permission errors (PERMISSION_*)
  'PERMISSION_DENIED': 'You do not have permission to perform this action',
  'PERMISSION_INSUFFICIENT': 'Insufficient permissions',

  // Resource errors (RESOURCE_*)
  'RESOURCE_NOT_FOUND': 'Resource not found',
  'RESOURCE_ALREADY_EXISTS': 'Resource already exists',
  'RESOURCE_CONFLICT': 'Resource conflict',

  // Rate limiting (RATE_LIMIT_*)
  'RATE_LIMIT_EXCEEDED': 'Too many requests. Please try again later',

  // Server errors
  'INTERNAL_ERROR': 'An internal server error occurred',
  'DATABASE_ERROR': 'Database error occurred',
  'SERVICE_UNAVAILABLE': 'Service temporarily unavailable',
}

/**
 * Get friendly error message from error response
 */
export const getErrorMessage = (error: any): string => {
  // Handle string error
  if (typeof error === 'string') {
    return error
  }

  // Handle error object with error_code
  if (error?.error_code) {
    const errorCode = error.error_code as string
    if (ERROR_MESSAGES[errorCode]) {
      return ERROR_MESSAGES[errorCode]
    }
  }

  // Handle error object with message
  if (error?.message) {
    return error.message
  }

  // Handle error object with detail
  if (error?.detail) {
    return error.detail
  }

  // Default error message
  return 'An unexpected error occurred. Please try again.'
}

/**
 * Get field-specific error message
 */
export const getFieldError = (error: any, field: string): string | null => {
  if (error?.details && typeof error.details === 'object') {
    const fieldError = (error.details as Record<string, string>)[field]
    if (fieldError) {
      return fieldError
    }
  }
  return null
}
