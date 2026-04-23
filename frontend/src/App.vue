<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

onMounted(() => {
  authStore.initializeAuth()
})
</script>

<template>
  <div id="app">
    <router-view />
  </div>
</template>

<style scoped>
#app {
  min-height: 100vh;
}
</style>
