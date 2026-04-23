/**
 * Simple encryption utility for token storage
 * This provides basic obfuscation to protect tokens from casual XSS attacks
 * Note: For production, use httpOnly cookies + server-side session management
 */

const ENCRYPTION_KEY = import.meta.env.VITE_ENCRYPTION_KEY || 'rent-mgmt-default-key-2024'
const ENCRYPTION_VERSION = 'v1'

/**
 * Simple XOR cipher with base64 encoding
 * This is NOT military-grade encryption, but provides basic obfuscation
 */
function xorCipher(text: string, key: string): string {
  let result = ''
  for (let i = 0; i < text.length; i++) {
    result += String.fromCharCode(text.charCodeAt(i) ^ key.charCodeAt(i % key.length))
  }
  return result
}

/**
 * Generate a fingerprint from user agent and salt
 */
function generateFingerprint(): string {
  const userAgent = navigator.userAgent
  const salt = ENCRYPTION_KEY
  const combined = userAgent + salt
  
  // Simple hash function
  let hash = 0
  for (let i = 0; i < combined.length; i++) {
    const char = combined.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash // Convert to 32-bit integer
  }
  return Math.abs(hash).toString(36)
}

/**
 * Encrypt data with version and fingerprint
 */
export function encryptToken(token: string): string {
  try {
    const timestamp = Date.now().toString()
    const fingerprint = generateFingerprint()
    
    // Create payload: version|timestamp|fingerprint|token
    const payload = `${ENCRYPTION_VERSION}|${timestamp}|${fingerprint}|${token}`
    
    // Encrypt and encode
    const encrypted = xorCipher(payload, ENCRYPTION_KEY)
    const base64 = btoa(encrypted)
    
    return base64
  } catch (error) {
    console.error('Token encryption failed:', error)
    // Fall back to plain token (better than failing completely)
    return token
  }
}

/**
 * Decrypt and validate token
 * Returns null if validation fails (expired, wrong fingerprint, corrupted)
 */
export function decryptToken(encryptedData: string | null): string | null {
  if (!encryptedData) return null

  try {
    // Decode base64
    const encrypted = atob(encryptedData)
    
    // Decrypt
    const payload = xorCipher(encrypted, ENCRYPTION_KEY)
    
    // Parse parts
    const parts = payload.split('|')
    if (parts.length !== 4) {
      console.warn('Token format invalid')
      return null
    }

    const [version, timestamp, storedFingerprint, token] = parts
    
    // Verify version
    if (version !== ENCRYPTION_VERSION) {
      console.warn('Token version mismatch')
      return null
    }

    // Verify fingerprint (detect if token was stolen and used from different browser)
    const currentFingerprint = generateFingerprint()
    if (storedFingerprint !== currentFingerprint) {
      console.warn('Token fingerprint mismatch - possible theft')
      return null
    }

    // Check token age (max 7 days)
    const tokenAge = Date.now() - parseInt(timestamp)
    const maxAge = 7 * 24 * 60 * 60 * 1000 // 7 days
    if (tokenAge > maxAge) {
      console.warn('Token expired')
      return null
    }

    return token
  } catch (error) {
    console.error('Token decryption failed:', error)
    return null
  }
}

/**
 * Validate if token is still valid
 */
export function isTokenValid(encryptedData: string | null): boolean {
  return decryptToken(encryptedData) !== null
}

/**
 * Hash a string (for simple obfuscation)
 */
export function simpleHash(str: string): string {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash
  }
  return Math.abs(hash).toString(36)
}
