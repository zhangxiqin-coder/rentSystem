<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, User, Search } from '@element-plus/icons-vue'
import { tenantsApi } from '@/api/tenants'
import { roomApi } from '@/api/room'
import { useAuthStore } from '@/stores/auth'
import { useOverdueConfig } from '@/composables/useOverdueConfig'
import type { Tenant } from '@/types'
import type { Room } from '@/types'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const tenants = ref<Tenant[]>([])
const rooms = ref<Room[]>([])
const activeTab = ref('active')  // active: 在租, inactive: 已搬走
const searchKeyword = ref('')
const { leaseExpiryWarningDays } = useOverdueConfig()

// 合同到期提醒接口
interface LeaseExpiryWarning {
  roomId: number
  roomNumber: string
  tenantName: string
  leaseEnd: string
  daysLeft: number
}

// 计算即将到期租客
const leaseExpiryWarnings = computed<LeaseExpiryWarning[]>(() => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const warningDays = leaseExpiryWarningDays.value
  const warnings: LeaseExpiryWarning[] = []

  rooms.value.forEach(room => {
    if (room.status !== 'occupied') return
    if (!room.lease_end) return
    if (!room.tenant_name) return

    const leaseEnd = new Date(room.lease_end)
    leaseEnd.setHours(0, 0, 0, 0)
    const diffMs = leaseEnd.getTime() - today.getTime()
    const daysLeft = Math.ceil(diffMs / (1000 * 60 * 60 * 24))

    // 包含已过期和即将在warningDays天内到期的
    if (daysLeft <= warningDays) {
      warnings.push({
        roomId: room.id,
        roomNumber: room.room_number,
        tenantName: room.tenant_name,
        leaseEnd: room.lease_end.toString().split('T')[0],
        daysLeft
      })
    }
  })

  // 按剩余天数升序排列（最紧急的在前）
  warnings.sort((a, b) => a.daysLeft - b.daysLeft)
  return warnings
})

// 获取房间列表
const fetchRooms = async () => {
  try {
    rooms.value = await roomApi.list()
  } catch (error) {
    console.error('获取房间列表失败:', error)
  }
}

// 获取租客列表
const fetchTenants = async () => {
  loading.value = true
  try {
    const params: { status?: string; search?: string } = { status: activeTab.value }
    if (searchKeyword.value.trim()) {
      params.search = searchKeyword.value.trim()
    }
    tenants.value = await tenantsApi.list(params)
  } catch (error) {
    ElMessage.error('获取租客列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 切换tab或搜索时重新加载
watch([activeTab, searchKeyword], () => {
  fetchTenants()
})

// 删除租客
const handleDelete = async (tenant: Tenant) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除租客 "${tenant.name}" 吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await tenantsApi.delete(tenant.id)
    ElMessage.success('删除成功')
    await fetchTenants()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

// 查看租客详情
const viewDetail = (tenant: Tenant) => {
  router.push(`/tenants/${tenant.id}`)
}

// 新增租客
const handleAdd = () => {
  router.push('/tenants/create')
}

onMounted(() => {
  fetchRooms()
  fetchTenants()
})
</script>

<template>
  <div class="tenants-page">
    <div class="page-header">
      <h2>租客管理</h2>
      <el-button type="primary" :icon="Plus" @click="handleAdd">新增租客</el-button>
    </div>

    <!-- 合同到期提醒 -->
    <div v-if="leaseExpiryWarnings.length > 0" class="warning-alert">
      <div class="alert-icon">⏰</div>
      <div class="alert-content">
        <strong>合同到期提醒：</strong>
        <ul>
          <li v-for="warning in leaseExpiryWarnings" :key="warning.roomId" class="warning-item">
            <span v-if="warning.daysLeft < 0" class="warning-text warning-overdue">
              {{ warning.roomNumber }} {{ warning.tenantName }} 合同已于 {{ warning.leaseEnd }} 到期（已过期 {{ Math.abs(warning.daysLeft) }} 天）
            </span>
            <span v-else-if="warning.daysLeft === 0" class="warning-text warning-today">
              {{ warning.roomNumber }} {{ warning.tenantName }} 合同今天到期（{{ warning.leaseEnd }}）
            </span>
            <span v-else class="warning-text">
              {{ warning.roomNumber }} {{ warning.tenantName }} 合同将于 {{ warning.leaseEnd }} 到期（还有 {{ warning.daysLeft }} 天）
            </span>
          </li>
        </ul>
      </div>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索姓名、电话或身份证号"
        clearable
        :prefix-icon="Search"
        style="width: 320px"
      />
    </div>

    <!-- tab切换 -->
    <el-tabs v-model="activeTab" class="tenant-tabs">
      <el-tab-pane label="在租租客" name="active" />
      <el-tab-pane label="已搬走" name="inactive" />
    </el-tabs>

    <!-- 电脑端：表格 -->
    <el-table
      v-loading="loading"
      :data="tenants"
      stripe
      style="width: 100%"
      class="hidden-mobile"
    >
      <el-table-column prop="name" label="姓名" width="120" />
      <el-table-column prop="phone" label="电话" width="160" />
      <el-table-column prop="created_at" label="创建时间">
        <template #default="{ row }">
          {{ new Date(row.created_at).toLocaleString('zh-CN') }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right" class-name="action-col">
        <template #default="{ row }">
          <div class="action-btns">
            <el-button
              type="primary"
              :icon="User"
              size="small"
              @click="viewDetail(row)"
            >
              详情
            </el-button>
            <el-button
              v-if="authStore.isSuperAdmin"
              type="danger"
              :icon="Delete"
              size="small"
              @click="handleDelete(row)"
            >
              删除
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- 手机端：卡片列表 -->
    <div v-loading="loading" class="tenant-cards hidden-desktop">
      <div v-for="tenant in tenants" :key="tenant.id" class="tenant-card">
        <div class="card-info">
          <div class="card-row">
            <span class="card-label">姓名</span>
            <span class="card-value">{{ tenant.name }}</span>
          </div>
          <div class="card-row">
            <span class="card-label">电话</span>
            <span class="card-value">{{ tenant.phone }}</span>
          </div>
          <div class="card-row">
            <span class="card-label">创建时间</span>
            <span class="card-value">{{ new Date(tenant.created_at).toLocaleString('zh-CN') }}</span>
          </div>
        </div>
        <div class="card-actions">
          <el-button
            type="primary"
            :icon="User"
            size="small"
            @click="viewDetail(tenant)"
          >
            详情
          </el-button>
          <el-button
            v-if="authStore.isSuperAdmin"
            type="danger"
            :icon="Delete"
            size="small"
            @click="handleDelete(tenant)"
          >
            删除
          </el-button>
        </div>
      </div>
      <el-empty v-if="!loading && tenants.length === 0" description="暂无数据" />
    </div>
  </div>
</template>

<style scoped>
.tenants-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.search-bar {
  margin-bottom: 8px;
}

.tenant-tabs {
  margin-bottom: 8px;
}

/* 电脑端操作按钮一行 */
.action-btns {
  white-space: nowrap;
  display: flex;
  gap: 4px;
}

/* 响应式：默认显示表格、隐藏卡片 */
.hidden-mobile {
  display: block;
}
.hidden-desktop {
  display: none;
}

/* 手机端卡片 */
.tenant-card {
  background: #fff;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 10px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.card-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 14px;
}

.card-label {
  color: #909399;
  flex-shrink: 0;
  margin-right: 12px;
}

.card-value {
  color: #303133;
  text-align: right;
  word-break: break-all;
}

.card-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #ebeef5;
}

/* 合同到期提醒样式 */
.warning-alert {
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 8px;
  padding: 1rem 1.5rem;
  margin-bottom: 1rem;
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  box-shadow: 0 2px 4px rgba(255, 193, 7, 0.2);
}

.alert-icon {
  font-size: 1.5rem;
  flex-shrink: 0;
}

.alert-content {
  flex: 1;
}

.alert-content strong {
  color: #856404;
  display: block;
  margin-bottom: 0.5rem;
}

.alert-content ul {
  margin: 0;
  padding-left: 0;
  list-style: none;
}

.warning-item {
  color: #856404;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.warning-item:last-child {
  margin-bottom: 0;
}

.warning-text.warning-overdue {
  color: #f56c6c;
  font-weight: 600;
}

.warning-text.warning-today {
  color: #e6a23c;
  font-weight: 600;
}

@media (max-width: 768px) {
  .hidden-mobile {
    display: none !important;
  }
  .hidden-desktop {
    display: block !important;
  }
  .tenants-page {
    padding: 12px;
  }
  .page-header h2 {
    font-size: 18px;
  }
  .search-bar .el-input {
    width: 100% !important;
  }
}
</style>
