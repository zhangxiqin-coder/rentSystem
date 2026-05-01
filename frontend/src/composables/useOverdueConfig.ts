import { ref, type Ref } from 'vue'

const config = {
  overdueCutoffDate: { key: 'overdue_cutoff_date', default: '2026-04-22' },
  advanceRentDays: { key: 'advance_rent_days', default: 1 },
  expiringDays: { key: 'expiring_days', default: 7 },
  recentPaymentDays: { key: 'recent_payment_days', default: 7 },
  recentReadingDays: { key: 'recent_reading_days', default: 2 },
} as const

function loadVal<T>(key: string, defaultVal: T, parse: (v: string) => T): T {
  const stored = localStorage.getItem(key)
  return stored !== null ? parse(stored) : defaultVal
}

const overdueCutoffDate = ref(loadVal(config.overdueCutoffDate.key, config.overdueCutoffDate.default, String))
const advanceRentDays = ref(loadVal(config.advanceRentDays.key, config.advanceRentDays.default, Number))
const expiringDays = ref(loadVal(config.expiringDays.key, config.expiringDays.default, Number))
const recentPaymentDays = ref(loadVal(config.recentPaymentDays.key, config.recentPaymentDays.default, Number))
const recentReadingDays = ref(loadVal(config.recentReadingDays.key, config.recentReadingDays.default, Number))

function makeSetter<T extends string | number>(ref_: Ref<T>, key: string) {
  return (val: T) => {
    ref_.value = val
    localStorage.setItem(key, String(val))
  }
}

export function useOverdueConfig() {
  return {
    overdueCutoffDate,
    setOverdueCutoffDate: makeSetter(overdueCutoffDate, config.overdueCutoffDate.key),
    advanceRentDays,
    setAdvanceRentDays: makeSetter(advanceRentDays, config.advanceRentDays.key),
    expiringDays,
    setExpiringDays: makeSetter(expiringDays, config.expiringDays.key),
    recentPaymentDays,
    setRecentPaymentDays: makeSetter(recentPaymentDays, config.recentPaymentDays.key),
    recentReadingDays,
    setRecentReadingDays: makeSetter(recentReadingDays, config.recentReadingDays.key),
    // Reset all to defaults
    resetDefaults: () => {
      overdueCutoffDate.value = config.overdueCutoffDate.default
      advanceRentDays.value = config.advanceRentDays.default
      expiringDays.value = config.expiringDays.default
      recentPaymentDays.value = config.recentPaymentDays.default
      recentReadingDays.value = config.recentReadingDays.default
      Object.values(config).forEach(c => localStorage.removeItem(c.key))
    },
    // All defaults for display
    defaults: {
      overdueCutoffDate: config.overdueCutoffDate.default,
      advanceRentDays: config.advanceRentDays.default,
      expiringDays: config.expiringDays.default,
      recentPaymentDays: config.recentPaymentDays.default,
      recentReadingDays: config.recentReadingDays.default,
    },
  }
}
