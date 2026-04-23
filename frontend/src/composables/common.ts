import { ref, computed } from 'vue'

export function usePagination(initialPage = 1, initialSize = 10) {
  const page = ref(initialPage)
  const size = ref(initialSize)

  const offset = computed(() => (page.value - 1) * size.value)

  const nextPage = () => {
    page.value++
  }

  const prevPage = () => {
    if (page.value > 1) {
      page.value--
    }
  }

  const resetPage = () => {
    page.value = initialPage
  }

  return {
    page,
    size,
    offset,
    nextPage,
    prevPage,
    resetPage,
  }
}

export function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount)
}

export function formatNumber(value: number, decimals = 2): string {
  return value.toFixed(decimals)
}
