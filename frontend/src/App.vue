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
    <!-- 调试标记：看到红色"V2.0"表示新代码已加载 -->
    <div style="position:fixed;top:0;left:0;background:red;color:white;font-size:12px;z-index:9999;padding:2px 5px;">
      🎉 V2.0
    </div>
    <!-- 移动端顶部栏 -->
    <header v-if="showTopTabs" class="mobile-top-nav">
      <div class="brand">{{ authStore.displayName }}</div>
      <div class="actions">
        <el-button type="info" plain size="small" @click="toggleHideAmounts">
          {{ hideAmounts ? '显示金额' : '隐藏金额' }}
        </el-button>
        <router-link to="/settings" class="settings-link">
          <el-button type="info" plain size="small">设置</el-button>
        </router-link>
        <el-button type="danger" size="small" @click="handleLogout">退出</el-button>
      </div>
    </header>

    <!-- 桌面端导航栏 -->
    <header v-if="showTopTabs" class="desktop-nav">
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

    <main class="main-content" :class="{ 'with-mobile-nav': showTopTabs }">
      <router-view />
    </main>

    <!-- 移动端底部导航 -->
    <nav v-if="showTopTabs" class="mobile-bottom-nav">
      <div
        class="nav-item"
        :class="{ active: activeTab === 'rooms' }"
        @click="handleTabChange('rooms')"
      >
        <span class="icon">🏠</span>
        <span class="label">房间</span>
      </div>
      <div
        class="nav-item"
        :class="{ active: activeTab === 'payments' }"
        @click="handleTabChange('payments')"
      >
        <span class="icon">💰</span>
        <span class="label">收租</span>
      </div>
      <div
        class="nav-item"
        :class="{ active: activeTab === 'utility' }"
        @click="handleTabChange('utility')"
      >
        <span class="icon">⚡</span>
        <span class="label">水电</span>
      </div>
    </nav>
  </div>
</template>

<style scoped>
#app {
  min-height: 100vh;
}

/* 移动端顶部栏 */
.mobile-top-nav {
  display: none;
  position: sticky;
  top: 0;
  z-index: 20;
  padding: 8px 12px;
  background: #f5f7fa;
  color: #303133;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.mobile-top-nav .brand {
  font-weight: 600;
  font-size: 16px;
  color: #303133;
}

.mobile-top-nav .actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.mobile-top-nav .el-button {
  border-color: #dcdfe6;
  color: #606266;
}

.mobile-top-nav .el-button:hover {
  background-color: #ecf5ff;
  border-color: #409eff;
  color: #409eff;
}

/* 桌面端导航栏 */
.desktop-nav {
  display: flex;
  position: sticky;
  top: 0;
  z-index: 20;
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

/* 主内容区域 */
.main-content {
  min-height: calc(100vh - 60px);
}

.main-content.with-mobile-nav {
  min-height: calc(100vh - 120px);
  padding-bottom: 60px;
}

/* 移动端底部导航 */
.mobile-bottom-nav {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 100;
  background: white;
  border-top: 1px solid #ebeef5;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05);
  padding: 8px 0;
  padding-bottom: calc(8px + env(safe-area-inset-bottom));
}

.mobile-bottom-nav .nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  flex: 1;
  padding: 8px 0;
  cursor: pointer;
  transition: all 0.3s ease;
  color: #909399;
}

.mobile-bottom-nav .nav-item.active {
  color: #667eea;
}

.mobile-bottom-nav .nav-item .icon {
  font-size: 24px;
  line-height: 1;
}

.mobile-bottom-nav .nav-item .label {
  font-size: 12px;
  line-height: 1;
}

/* 响应式：移动端 */
@media (max-width: 768px) {
  .mobile-top-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .desktop-nav {
    display: none;
  }

  .mobile-bottom-nav {
    display: flex;
  }

  .main-content.with-mobile-nav {
    padding-bottom: env(safe-area-inset-bottom);
  }
}

/* 小屏幕手机优化 */
@media (max-width: 375px) {
  .mobile-top-nav {
    padding: 6px 10px;
  }

  .mobile-top-nav .brand {
    font-size: 14px;
  }

  .mobile-bottom-nav .nav-item .icon {
    font-size: 22px;
  }

  .mobile-bottom-nav .nav-item .label {
    font-size: 11px;
  }
}
</style>
