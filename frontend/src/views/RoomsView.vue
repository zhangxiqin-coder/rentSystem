<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { roomApi } from '@/api/room'
import type { Room } from '@/types'

const rooms = ref<Room[]>([])
const loading = ref(false)

const loadRooms = async () => {
  loading.value = true
  try {
    const response = await roomApi.getRooms({ page: 1, size: 10 })
    rooms.value = response.data.data.items
  } catch (error) {
    console.error('Failed to load rooms:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadRooms()
})
</script>

<template>
  <div class="rooms-view">
    <header class="view-header">
      <h1>Rooms</h1>
      <button class="add-button">Add Room</button>
    </header>

    <main class="view-content">
      <div v-if="loading" class="loading">Loading...</div>
      <div v-else class="rooms-list">
        <div v-for="room in rooms" :key="room.id" class="room-card">
          <h3>{{ room.room_number }}</h3>
          <p>Building: {{ room.building || 'N/A' }}</p>
          <p>Rent: ${{ room.rent_amount }}</p>
          <p>Status: {{ room.status }}</p>
          <router-link :to="`/rooms/${room.id}`">View Details</router-link>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.rooms-view {
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

.add-button {
  padding: 0.75rem 1.5rem;
  background-color: #4caf50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
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

.rooms-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
}

.room-card {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.room-card h3 {
  margin: 0 0 1rem 0;
  color: #333;
}

.room-card p {
  margin: 0.5rem 0;
  color: #666;
}

.room-card a {
  display: inline-block;
  margin-top: 1rem;
  color: #4caf50;
  text-decoration: none;
}

.room-card a:hover {
  text-decoration: underline;
}
</style>
