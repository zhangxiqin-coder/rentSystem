import { useAmountVisibility } from '@/composables/useAmountVisibility'

export function useAmountFormatting() {
  const { hideAmounts, formatAmount } = useAmountVisibility()

  const maskedAmount = (value: number | string | null | undefined) => {
    if (value === null || value === undefined || value === '') return '-'
    return formatAmount(Number(value))
  }

  const maskedRate = (value: number | string | null | undefined, unit: string) => {
    if (hideAmounts.value) return `****/${unit}`
    return `¥${Number(value || 0).toFixed(2)}/${unit}`
  }

  return { hideAmounts, formatAmount, maskedAmount, maskedRate }
}
