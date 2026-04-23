<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { roomApi } from '@/api/room'
import type { Room } from '@/types'

const props = defineProps<{
  id: string
}>()

const room = ref<Room | null>(null)
const loading = ref(false)

const loadRoom = async () => {
  loading.value = true
  try {
    const response = await roomApi.getRoom(Number(props.id))
    room.value = response.data.data
  } catch (error) {
    console.error('Failed to load room:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadRoom()
})
</script>

<template>
  <div class="room-detail-view">
    <header class="view-header">
      <h1>Room Details</h1>
      <router-link to="/rooms" class="back-button">Back to Rooms</router-link>
    </header>

    <main class="view-content">
      <div v-if="loading" class="loading">Loading...</div>
      <div v-else-if="room" class="room-detail-card">
        <h2>{{ room.room_number }}</h2>
        <div class="detail-grid">
          <div class="detail-item">
            <label>Building:</label>
            <span>{{ room.building || 'N/A' }}</span>
          </div>
          <div class="detail-item">
            <label>Floor:</label>
            <span>{{ room.floor || 'N/A' }}</span>
          </div>
          <div class="detail-item">
            <label>Area:</label>
            <span>{{ room.area || 'N/A' }} m²</span>
          </div>
          <div class="detail-item">
            <label>Rent:</label>
            <span>${{ room.rent_amount }}</span>
          </div>
          <div class="detail-item">
            <label>Deposit:</label>
            <span>${{ room.deposit_amount }}</span>
          </div>
          <div class="detail-item">
            <label>Status:</label>
            <span :class="`status-${room.status}`">{{ room.status }}</span>
          </div>
        </div>
        <div v-if="room.description" class="description">
          <label>Description:</label>
          <p>{{ room.description }}</p>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.room-detail-view {
  min-height: 100vh;
  background-color: #f5f5f5;
}

.view-header {
  background: white;
  padding: 1.5rem 2rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.view-header h1 {
  margin: 0;
  color: #333;
}

.back-button {
  padding: 0.75rem 1.5rem;
  background-color: #666;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  text-decoration: none;
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

.room-detail-card {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.room-detail-card h2 {
  margin: 0 0 2rem 0;
  color: #333;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.detail-item {
  display: flex;
  flex-direction: column;
}

.detail-item label {
  font-weight: 600;
  color: #555;
  margin-bottom: 0.5rem;
}

.detail-item span {
  color: #333;
}

.status-available {
  color: #4caf50;
}

.status-occupied {
  color: #2196f3;
}

.status-maintenance {
  color: #ff9800;
}

.description {
  margin-top: 1rem;
}

.description label {
  font-weight: 600;
  color: #555;
  display: block;
  margin-bottom: 0.5rem;
}

.description p {
  color: #333;
  line-height: 1.6;
}
</style>
