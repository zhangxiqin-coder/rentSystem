<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const form = ref({
  username: '',
  password: '',
})

// Validation state
const errors = ref<Record<string, string>>({})
const touched = ref<Record<string, boolean>>({})

const loading = ref(false)

// Validate individual field
const validateField = (field: string): string | null => {
  const value = form.value[field as keyof typeof form.value]

  switch (field) {
    case 'username':
      if (!value || value.trim().length === 0) {
        return 'Username is required'
      }
      if (value.length < 3) {
        return 'Username must be at least 3 characters'
      }
      break
    case 'password':
      if (!value || value.length === 0) {
        return 'Password is required'
      }
      break
  }
  return null
}

// Validate all fields
const validateForm = (): boolean => {
  const newErrors: Record<string, string> = {}

  const usernameError = validateField('username')
  if (usernameError) newErrors.username = usernameError

  const passwordError = validateField('password')
  if (passwordError) newErrors.password = passwordError

  errors.value = newErrors
  return Object.keys(newErrors).length === 0
}

// Handle field blur
const handleBlur = (field: string) => {
  touched.value[field] = true
  const error = validateField(field)
  if (error) {
    errors.value[field] = error
  } else {
    delete errors.value[field]
  }
}

// Check if field has error
const hasError = (field: string) => {
  return touched.value[field] && errors.value[field]
}

const isFormValid = computed(() => {
  return form.value.username.trim().length > 0 &&
         form.value.password.length > 0 &&
         Object.keys(errors.value).length === 0
})

const handleLogin = async () => {
  // Mark all fields as touched
  touched.value = { username: true, password: true }

  // Validate form
  if (!validateForm()) {
    return
  }

  loading.value = true
  authStore.clearError()
  const success = await authStore.login(form.value)
  loading.value = false

  if (success) {
    router.push('/dashboard')
  }
}

// Watch for store errors and display them
import { watch } from 'vue'
watch(() => authStore.error, (newError) => {
  if (newError) {
    // Could add field-specific error parsing here
    console.error('Login error:', newError)
  }
})
</script>

<template>
  <div class="login-container">
    <div class="login-card">
      <h1>Login</h1>
      <form @submit.prevent="handleLogin" novalidate>
        <div class="form-group" :class="{ 'has-error': hasError('username') }">
          <label for="username">Username</label>
          <input
            id="username"
            v-model="form.username"
            type="text"
            placeholder="Enter your username"
            @blur="handleBlur('username')"
            :disabled="loading"
            autocomplete="username"
          />
          <span v-if="hasError('username')" class="error-message">
            {{ errors.username }}
          </span>
        </div>

        <div class="form-group" :class="{ 'has-error': hasError('password') }">
          <label for="password">Password</label>
          <input
            id="password"
            v-model="form.password"
            type="password"
            placeholder="Enter your password"
            @blur="handleBlur('password')"
            :disabled="loading"
            autocomplete="current-password"
          />
          <span v-if="hasError('password')" class="error-message">
            {{ errors.password }}
          </span>
        </div>

        <div v-if="authStore.error" class="form-error">
          {{ authStore.error }}
        </div>

        <button type="submit" :disabled="loading || !isFormValid" class="submit-btn">
          <span v-if="loading" class="loading-spinner"></span>
          {{ loading ? 'Logging in...' : 'Login' }}
        </button>
      </form>

      <p class="register-link">
        Don't have an account? <router-link to="/register">Register</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 1rem;
}

.login-card {
  background: white;
  padding: 2.5rem;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  width: 100%;
  max-width: 420px;
}

h1 {
  text-align: center;
  margin-bottom: 2rem;
  color: #333;
  font-size: 1.75rem;
  font-weight: 600;
}

.form-group {
  margin-bottom: 1.25rem;
  position: relative;
}

.form-group.has-error input {
  border-color: #f44336;
  background-color: #fff8f8;
}

label {
  display: block;
  margin-bottom: 0.5rem;
  color: #555;
  font-weight: 500;
  font-size: 0.9rem;
}

input {
  width: 100%;
  padding: 0.75rem 1rem;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 1rem;
  transition: all 0.3s ease;
  box-sizing: border-box;
}

input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

input:disabled {
  background-color: #f5f5f5;
  cursor: not-allowed;
}

.error-message {
  display: block;
  color: #f44336;
  font-size: 0.85rem;
  margin-top: 0.4rem;
}

.form-error {
  background-color: #ffebee;
  color: #c62828;
  padding: 0.75rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.9rem;
  text-align: center;
  border: 1px solid #ffcdd2;
}

.submit-btn {
  width: 100%;
  padding: 0.875rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  margin-top: 0.5rem;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
}

.submit-btn:disabled {
  background: linear-gradient(135deg, #b0b0b0 0%, #909090 100%);
  cursor: not-allowed;
  transform: none;
}

.loading-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.register-link {
  text-align: center;
  margin-top: 1.5rem;
  color: #666;
  font-size: 0.95rem;
}

.register-link a {
  color: #667eea;
  text-decoration: none;
  font-weight: 600;
  transition: color 0.3s ease;
}

.register-link a:hover {
  color: #764ba2;
  text-decoration: underline;
}
</style>
