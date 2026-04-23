<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { paymentApi } from '@/api/payment'
import type { Payment } from '@/types'

const payments = ref<Payment[]>([])
const loading = ref(false)

const loadPayments = async () => {
  loading.value = true
  try {
    const response = await paymentApi.getPayments({ page: 1, size: 10 })
    payments.value = response.data.items
  } catch (error) {
    console.error('Failed to load payments:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadPayments()
})
</script>

<template>
  <div class="payments-view">
    <header class="view-header">
      <h1>Payments</h1>
    </header>

    <main class="view-content">
      <div v-if="loading" class="loading">Loading...</div>
      <div v-else class="payments-list">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Type</th>
              <th>Amount</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="payment in payments" :key="payment.id">
              <td>{{ payment.payment_date }}</td>
              <td>{{ payment.payment_type }}</td>
              <td>${{ payment.amount }}</td>
              <td :class="`status-${payment.status}`">{{ payment.status }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </main>
  </div>
</template>

<style scoped>
.payments-view {
  min-height: 100vh;
  background-color: #f5f5f5;
}

.view-header {
  background: white;
  padding: 1.5rem 2rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.view-header h1 {
  margin: 0;
  color: #333;
}

.view-content {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.loading {
  text-align: center;
  padding: 2rem;
  color: #666;
}

.payments-list {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

table {
  width: 100%;
  border-collapse: collapse;
}

thead {
  background-color: #f9f9f9;
}

th {
  padding: 1rem;
  text-align: left;
  font-weight: 600;
  color: #555;
}

td {
  padding: 1rem;
  border-top: 1px solid #eee;
}

.status-pending {
  color: #ff9800;
}

.status-completed {
  color: #4caf50;
}

.status-overdue {
  color: #f44336;
}

.status-cancelled {
  color: #999;
}
</style>
