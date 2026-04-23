<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const goHome = () => {
  router.push('/')
}
</script>

<template>
  <div class="not-found">
    <div class="content">
      <h1>404</h1>
      <h2>Page Not Found</h2>
      <p>The page you are looking for does not exist.</p>
      <button @click="goHome">Go Home</button>
    </div>
  </div>
</template>

<style scoped>
.not-found {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f5f5f5;
}

.content {
  text-align: center;
}

h1 {
  font-size: 8rem;
  margin: 0;
  color: #4caf50;
}

h2 {
  font-size: 2rem;
  margin: 1rem 0;
  color: #333;
}

p {
  color: #666;
  margin-bottom: 2rem;
}

button {
  padding: 0.75rem 2rem;
  background-color: #4caf50;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  cursor: pointer;
}

button:hover {
  background-color: #45a049;
}
</style>
