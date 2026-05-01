<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { 注册Request } from '@/types'

const router = useRouter()
const authStore = useAuthStore()

const form = ref<注册Request & { confirmPassword: string }>({
  username: '',
  email: '',
  password: '',
  full_name: '',
  role: 'landlord',
  confirmPassword: '',
})

// Validation state
const errors = ref<Record<string, string>>({})
const touched = ref<Record<string, boolean>>({})

const loading = ref(false)

interface PasswordStrength {
  score: number
  label: string
  color: string
  percent: number
}

// Password strength calculation
const passwordStrength = computed<PasswordStrength>(() => {
  const password = form.value.password
  if (!password) return { score: 0, label: '', color: '', percent: 0 }

  let score = 0

  // Length check
  if (password.length >= 8) score++
  if (password.length >= 12) score++

  // Complexity checks
  if (/[a-z]/.test(password)) score++
  if (/[A-Z]/.test(password)) score++
  if (/[0-9]/.test(password)) score++
  if (/[^a-zA-Z0-9]/.test(password)) score++

  // Normalize score to 0-3
  const normalizedScore = Math.min(Math.floor(score / 2), 3)

  const strengthMap: Record<number, PasswordStrength> = {
    0: { score: 0, label: '弱', color: '#f44336', percent: 20 },
    1: { score: 1, label: '弱', color: '#f44336', percent: 40 },
    2: { score: 2, label: '中', color: '#ff9800', percent: 60 },
    3: { score: 3, label: '强', color: '#4caf50', percent: 100 },
  }

  return strengthMap[normalizedScore]
})

// Password requirements
const passwordRequirements = computed(() => {
  const password = form.value.password
  return [
    { text: '至少8个字符', met: password.length >= 8 },
    { text: '包含小写字母', met: /[a-z]/.test(password) },
    { text: '包含大写字母', met: /[A-Z]/.test(password) },
    { text: '包含数字', met: /[0-9]/.test(password) },
    { text: '包含特殊字符', met: /[^a-zA-Z0-9]/.test(password) },
  ]
})

// Validate individual field
const validateField = (field: string): string | null => {
  const value = form.value[field as keyof typeof form.value]

  switch (field) {
    case 'username':
      if (!value || value.trim().length === 0) {
        return '请输入用户名'
      }
      if (value.length < 3) {
        return '用户名至少3个字符'
      }
      if (!/^[a-zA-Z0-9_]+$/.test(value)) {
        return '用户名只能包含字母、数字和下划线'
      }
      break

    case 'email':
      if (!value || value.trim().length === 0) {
        return '请输入邮箱'
      }
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
      if (!emailRegex.test(value)) {
        return '请输入有效的邮箱地址'
      }
      break

    case 'password':
      if (!value || value.length === 0) {
        return '请输入密码'
      }
      if (value.length < 8) {
        return '密码至少8个字符'
      }
      if (passwordStrength.value.score === 0) {
        return '密码强度太弱'
      }
      break

    case 'confirmPassword':
      if (!value || value.length === 0) {
        return '请确认密码'
      }
      if (value !== form.value.password) {
        return '两次密码不一致'
      }
      break

    case 'full_name':
      // Optional field, no validation
      break
  }
  return null
}

// Validate all fields
const validateForm = (): boolean => {
  const newErrors: Record<string, string> = {}

  const fields = ['username', 'email', 'password', 'confirmPassword']
  fields.forEach(field => {
    const error = validateField(field)
    if (error) newErrors[field] = error
  })

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
         (form.value.email?.trim()?.length || 0) > 0 &&
         form.value.password.length >= 8 &&
         form.value.confirmPassword === form.value.password &&
         form.value.confirmPassword.length > 0 &&
         Object.keys(errors.value).length === 0
})

// Watch password changes to validate confirm password
watch(() => form.value.password, () => {
  if (touched.value.confirmPassword) {
    const error = validateField('confirmPassword')
    if (error) {
      errors.value.confirmPassword = error
    } else {
      delete errors.value.confirmPassword
    }
  }
})

const handle注册 = async () => {
  // Mark all fields as touched
  touched.value = {
    username: true,
    email: true,
    password: true,
    confirmPassword: true,
    full_name: true,
  }

  // Validate form
  if (!validateForm()) {
    return
  }

  loading.value = true
  authStore.clearError()

  // Remove confirmPassword before sending to API
  const { confirmPassword, ...registerData } = form.value
  const success = await authStore.register(registerData)

  loading.value = false

  if (success) {
    // Show success message or redirect
    router.push('/login')
  }
}
</script>

<template>
  <div class="register-container">
    <div class="register-card">
      <h1>创建账户</h1>
      <form @submit.prevent="handle注册" novalidate>
        <div class="form-group" :class="{ 'has-error': hasError('username') }">
          <label for="username">用户名 *</label>
          <input
            id="username"
            v-model="form.username"
            type="text"
            placeholder="选择用户名"
            @blur="handleBlur('username')"
            :disabled="loading"
            autocomplete="username"
          />
          <span v-if="hasError('username')" class="error-message">
            {{ errors.username }}
          </span>
        </div>

        <div class="form-group" :class="{ 'has-error': hasError('email') }">
          <label for="email">邮箱 *</label>
          <input
            id="email"
            v-model="form.email"
            type="email"
            placeholder="请输入邮箱"
            @blur="handleBlur('email')"
            :disabled="loading"
            autocomplete="email"
          />
          <span v-if="hasError('email')" class="error-message">
            {{ errors.email }}
          </span>
        </div>

        <div class="form-group">
          <label for="fullName">姓名</label>
          <input
            id="fullName"
            v-model="form.full_name"
            type="text"
            placeholder="请输入姓名（选填）"
            :disabled="loading"
            autocomplete="name"
          />
        </div>

        <div class="form-group">
          <label>角色 *</label>
          <div class="role-select">
            <label class="role-option" :class="{ active: form.role === 'landlord' }">
              <input type="radio" v-model="form.role" value="landlord" :disabled="loading" />
              <span class="role-icon">🏠</span>
              <span class="role-label">房东</span>
              <span class="role-desc">管理房屋、收租</span>
            </label>
            <label class="role-option" :class="{ active: form.role === 'tenant' }">
              <input type="radio" v-model="form.role" value="tenant" :disabled="loading" />
              <span class="role-icon">👤</span>
              <span class="role-label">租客</span>
              <span class="role-desc">查看账单、缴费</span>
            </label>
          </div>
        </div>

        <div class="form-group" :class="{ 'has-error': hasError('password') }">
          <label for="password">密码 *</label>
          <input
            id="password"
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            @blur="handleBlur('password')"
            :disabled="loading"
            autocomplete="new-password"
          />
          <span v-if="hasError('password')" class="error-message">
            {{ errors.password }}
          </span>

          <!-- Password strength indicator -->
          <div v-if="form.password" class="password-strength">
            <div class="strength-bar">
              <div
                class="strength-fill"
                :style="{
                  width: passwordStrength.percent + '%',
                  backgroundColor: passwordStrength.color
                }"
              ></div>
            </div>
            <div class="strength-label">
              <span>密码强度：</span>
              <span :style="{ color: passwordStrength.color }">
                {{ passwordStrength.label }}
              </span>
            </div>
          </div>

          <!-- Password requirements -->
          <div v-if="form.password" class="password-requirements">
            <div
              v-for="req in passwordRequirements"
              :key="req.text"
              class="requirement"
              :class="{ met: req.met }"
            >
              <span class="requirement-icon">
                {{ req.met ? '✓' : '○' }}
              </span>
              {{ req.text }}
            </div>
          </div>
        </div>

        <div class="form-group" :class="{ 'has-error': hasError('confirmPassword') }">
          <label for="confirmPassword">确认密码 *</label>
          <input
            id="confirmPassword"
            v-model="form.confirmPassword"
            type="password"
            placeholder="确认密码"
            @blur="handleBlur('confirmPassword')"
            :disabled="loading"
            autocomplete="new-password"
          />
          <span v-if="hasError('confirmPassword')" class="error-message">
            {{ errors.confirmPassword }}
          </span>
        </div>

        <div v-if="authStore.error" class="form-error">
          {{ authStore.error }}
        </div>

        <button type="submit" :disabled="loading || !isFormValid" class="submit-btn">
          <span v-if="loading" class="loading-spinner"></span>
          {{ loading ? '创建中...' : '创建账户' }}
        </button>
      </form>

      <p class="login-link">
        已有账户？ <router-link to="/login">去登录</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.register-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 1rem;
}

.register-card {
  background: white;
  padding: 2.5rem;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  width: 100%;
  max-width: 480px;
  max-height: 90vh;
  overflow-y: auto;
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

.password-strength {
  margin-top: 0.75rem;
}

.strength-bar {
  height: 6px;
  background-color: #e0e0e0;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.strength-fill {
  height: 100%;
  transition: all 0.3s ease;
}

.strength-label {
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
  color: #666;
}

.password-requirements {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background-color: #f9f9f9;
  border-radius: 6px;
}

.requirement {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: #999;
  margin-bottom: 0.4rem;
}

.requirement:last-child {
  margin-bottom: 0;
}

.requirement.met {
  color: #4caf50;
}

.requirement-icon {
  font-weight: bold;
  font-size: 1rem;
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

.login-link {
  text-align: center;
  margin-top: 1.5rem;
  color: #666;
  font-size: 0.95rem;
}

.login-link a {
  color: #667eea;
  text-decoration: none;
  font-weight: 600;
  transition: color 0.3s ease;
}

.login-link a:hover {
  color: #764ba2;
  text-decoration: underline;
}

.role-select {
  display: flex;
  gap: 0.75rem;
}

.role-option {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.75rem;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.role-option:hover {
  border-color: #667eea;
}

.role-option.active {
  border-color: #667eea;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
}

.role-option input[type="radio"] {
  display: none;
}

.role-icon {
  font-size: 1.5rem;
}

.role-label {
  font-weight: 600;
  color: #333;
  font-size: 0.95rem;
}

.role-desc {
  font-size: 0.75rem;
  color: #999;
}

/* Scrollbar styling for the card */
.register-card::-webkit-scrollbar {
  width: 6px;
}

.register-card::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.register-card::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 3px;
}

.register-card::-webkit-scrollbar-thumb:hover {
  background: #555;
}
</style>
