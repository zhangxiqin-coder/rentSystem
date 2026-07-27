import { ref } from 'vue'

const STORAGE_KEY = 'privacy_mode'

const getInitialValue = () => {
  if (typeof window === 'undefined') return false
  return window.localStorage.getItem(STORAGE_KEY) === '1'
}

const privacyMode = ref(getInitialValue())

const setPrivacyMode = (value: boolean) => {
  privacyMode.value = value
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_KEY, value ? '1' : '0')
  }
}

const togglePrivacyMode = () => {
  setPrivacyMode(!privacyMode.value)
}

// 脱敏工具函数
const maskName = (name: string): string => {
  if (!name) return '-'
  if (name.length <= 1) return name
  return name[0] + '*'.repeat(name.length - 1)
}

const maskPhone = (phone: string): string => {
  if (!phone) return '-'
  if (phone.length < 7) return phone
  return phone.slice(0, 3) + '****' + phone.slice(-4)
}

const maskIdCard = (idCard: string): string => {
  if (!idCard) return '-'
  if (idCard.length < 6) return '******'
  return idCard.slice(0, 3) + '***********' + idCard.slice(-4)
}

const maskAmount = (amount: any): string => {
  if (amount === null || amount === undefined || amount === '') return '-'
  return '****'
}

export function usePrivacyMode() {
  return {
    privacyMode,
    setPrivacyMode,
    togglePrivacyMode,
    maskName,
    maskPhone,
    maskIdCard,
    maskAmount,
  }
}
