<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const handleLogout = async () => {
  await authStore.logout()
  router.push('/login')
}
</script>

<template>
  <div class="dashboard">
    <header class="dashboard-header">
      <h1>Dashboard</h1>
      <div class="user-info">
        <span>Welcome, {{ authStore.user?.full_name || authStore.user?.username }}</span>
        <button @click="handleLogout">Logout</button>
      </div>
    </header>

    <main class="dashboard-content">
      <div class="welcome-card">
        <h2>Welcome to Rent Management System</h2>
        <p>Your role: {{ authStore.userRole }}</p>
      </div>

      <nav class="quick-nav">
        <router-link to="/rooms" class="nav-card">
          <h3>Rooms</h3>
          <p>Manage your rooms</p>
        </router-link>
        <router-link to="/payments" class="nav-card">
          <h3>Payments</h3>
          <p>View payment history</p>
        </router-link>
        <router-link to="/utility" class="nav-card">
          <h3>Utilities</h3>
          <p>Utility readings and rates</p>
        </router-link>
      </nav>
    </main>
  </div>
</template>

<style scoped>
.dashboard {
  min-height: 100vh;
  background-color: #f5f5f5;
}

.dashboard-header {
  background: white;
  padding: 1rem 2rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dashboard-header h1 {
  margin: 0;
  color: #333;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.user-info button {
  padding: 0.5rem 1rem;
  background-color: #f44336;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.user-info button:hover {
  background-color: #d32f2f;
}

.dashboard-content {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.welcome-card {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  margin-bottom: 2rem;
}

.quick-nav {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
}

.nav-card {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  text-decoration: none;
  color: inherit;
  transition:
    transform 0.2s,
    box-shadow 0.2s;
}

.nav-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.nav-card h3 {
  margin: 0 0 0.5rem 0;
  color: #4caf50;
}

.nav-card p {
  margin: 0;
  color: #666;
}
</style>
