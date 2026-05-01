<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAmountVisibility } from '@/composables/useAmountVisibility'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const { hideAmounts, toggleHideAmounts } = useAmountVisibility()

const showTopTabs = computed(() => {
  if (!authStore.isAuthenticated) return false
  return route.name !== 'Login' && route.name !== 'Register'
})

const activeTab = computed(() => {
  if (route.path.startsWith('/rooms')) return 'rooms'
  if (route.path.startsWith('/payments')) return 'payments'
  if (route.path.startsWith('/utility')) return 'utility'
  return 'rooms'
})

const handleTabChange = (name: string | number) => {
  if (name === 'rooms') router.push('/rooms')
  if (name === 'payments') router.push('/payments')
  if (name === 'utility') router.push('/utility')
}

const handleLogout = async () => {
  await authStore.logout()
  router.push('/login')
}

onMounted(() => {
  authStore.initializeAuth()
})
</script>

<template>
  <div id="app">
    <header v-if="showTopTabs" class="top-nav">
      <div class="brand">租赁管理系统</div>
      <el-tabs :model-value="activeTab" class="nav-tabs" @tab-change="handleTabChange">
        <el-tab-pane label="房间管理" name="rooms" />
        <el-tab-pane label="交租记录" name="payments" />
        <el-tab-pane label="水电管理" name="utility" />
      </el-tabs>
      <div class="actions">
        <el-button type="info" plain size="small" @click="toggleHideAmounts">
          {{ hideAmounts ? '显示金额' : '隐藏金额' }}
        </el-button>
        <span class="username">{{ authStore.displayName }}</span>
        <router-link to="/settings" class="settings-link">
          <el-button type="info" plain size="small">设置</el-button>
        </router-link>
        <el-button type="danger" size="small" @click="handleLogout">退出登录</el-button>
      </div>
    </header>
    <router-view />
  </div>
</template>

<style scoped>
#app {
  min-height: 100vh;
}

.top-nav {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 20px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
}

.brand {
  min-width: 140px;
  font-weight: 600;
  color: #303133;
}

.nav-tabs {
  flex: 1;
}

.actions {
  min-width: 220px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
}

.username {
  color: #606266;
  font-size: 14px;
}

.settings-link {
  text-decoration: none;
}
</style>
