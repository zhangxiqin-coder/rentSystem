import { ref } from 'vue'

const STORAGE_KEY = 'hide_sensitive_amounts'

const getInitialValue = () => {
  if (typeof window === 'undefined') return false
  return window.localStorage.getItem(STORAGE_KEY) === '1'
}

const hideAmounts = ref(getInitialValue())

const setHideAmounts = (value: boolean) => {
  hideAmounts.value = value
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_KEY, value ? '1' : '0')
  }
}

const toggleHideAmounts = () => {
  setHideAmounts(!hideAmounts.value)
}

const formatAmount = (value: number, currency = '¥') => {
  if (hideAmounts.value) return '****'
  return `${currency}${Number(value || 0).toFixed(2)}`
}

export function useAmountVisibility() {
  return {
    hideAmounts,
    setHideAmounts,
    toggleHideAmounts,
    formatAmount,
  }
}
