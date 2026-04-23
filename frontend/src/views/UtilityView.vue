<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { utilityApi } from '@/api/utility'
import type { UtilityReading, UtilityRate } from '@/types'

const readings = ref<UtilityReading[]>([])
const rates = ref<UtilityRate[]>([])
const loading = ref(false)

const loadData = async () => {
  loading.value = true
  try {
    const [readingsRes, ratesRes] = await Promise.all([
      utilityApi.getReadings({ page: 1, size: 10 }),
      utilityApi.getActiveRates(),
    ])
    readings.value = readingsRes.data.data.items
    rates.value = ratesRes.data.data
  } catch (error) {
    console.error('Failed to load utility data:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="utility-view">
    <header class="view-header">
      <h1>Utilities</h1>
    </header>

    <main class="view-content">
      <div v-if="loading" class="loading">Loading...</div>
      <div v-else>
        <section class="utility-section">
          <h2>Current Rates</h2>
          <div class="rates-list">
            <div v-for="rate in rates" :key="rate.id" class="rate-card">
              <h3>{{ rate.utility_type }}</h3>
              <p>${{ rate.rate_per_unit }} per unit</p>
              <p>Effective from: {{ rate.effective_date }}</p>
            </div>
          </div>
        </section>

        <section class="utility-section">
          <h2>Recent Readings</h2>
          <div class="readings-list">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Type</th>
                  <th>Usage</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="reading in readings" :key="reading.id">
                  <td>{{ reading.reading_date }}</td>
                  <td>{{ reading.utility_type }}</td>
                  <td>{{ reading.usage }}</td>
                  <td>${{ reading.amount }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.utility-view {
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

.utility-section {
  margin-bottom: 2rem;
}

.utility-section h2 {
  margin: 0 0 1rem 0;
  color: #333;
}

.rates-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.rate-card {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.rate-card h3 {
  margin: 0 0 0.5rem 0;
  color: #4caf50;
  text-transform: capitalize;
}

.rate-card p {
  margin: 0.25rem 0;
  color: #666;
}

.readings-list {
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
</style>
