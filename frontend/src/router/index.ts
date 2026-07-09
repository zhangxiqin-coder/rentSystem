import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Home',
    redirect: '/utility',
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/rooms',
    name: 'Rooms',
    component: () => import('@/views/RoomsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/rooms/:id',
    name: 'RoomDetail',
    component: () => import('@/views/RoomDetailView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/rooms/:id/edit',
    name: 'RoomEdit',
    component: () => import('@/views/RoomsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/payments',
    name: 'Payments',
    component: () => import('@/views/PaymentsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/utility',
    name: 'Utility',
    component: () => import('@/views/UtilityView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/reports',
    name: 'Reports',
    component: () => import('@/views/ReportsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/tenants',
    name: 'Tenants',
    component: () => import('@/views/TenantsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/tenants/create',
    name: 'TenantCreate',
    component: () => import('@/views/TenantFormView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/tenants/:id',
    name: 'TenantDetail',
    component: () => import('@/views/TenantDetailView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/tenants/:id/edit',
    name: 'TenantEdit',
    component: () => import('@/views/TenantFormView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/assets',
    name: 'Assets',
    component: () => import('@/views/AssetsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

// Navigation guard
router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()

  // Initialize auth state if not already done
  if (!authStore.isAuthenticated && localStorage.getItem('access_token')) {
    authStore.initializeAuth()
  }

  const requiresAuth = to.meta.requiresAuth !== false

  if (requiresAuth && !authStore.isAuthenticated) {
    // Redirect to login if trying to access protected route
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (to.meta.requiresShowAssets && !authStore.showAssetsPage) {
    // 资产页面未开启时重定向
    next({ name: 'Utility' })
  } else if (to.name === 'Login' && authStore.isAuthenticated) {
    // Redirect to utility page if already logged in
    next({ name: 'Utility' })
  } else {
    next()
  }
})

export default router
