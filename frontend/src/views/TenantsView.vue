<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, User, Search } from '@element-plus/icons-vue'
import { tenantsApi } from '@/api/tenants'
import { leaseRecordsApi } from '@/api/leaseRecords'
import { roomApi } from '@/api/room'
import { statisticsApi } from '@/api/statistics'
import { useAuthStore } from '@/stores/auth'
import { useOverdueConfig } from '@/composables/useOverdueConfig'
import type { Tenant } from '@/types'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const tenants = ref<Tenant[]>([])
const activeTab = ref('active')  // active: 入住, unassigned: 未入住, inactive: 搬离
const searchKeyword = ref('')
const { leaseExpiryWarningDays } = useOverdueConfig()

// 合同到期提醒接口（从后端LeaseRecord获取）
interface LeaseExpiryWarning {
  roomId: number
  roomNumber: string
  tenantId: number
  tenantName: string
  leaseEnd: string
  daysLeft: number
  monthlyRent: number
}

const leaseExpiryWarnings = ref<LeaseExpiryWarning[]>([])

// 租客 → 合同到期日映射
const tenantLeaseEndMap = ref<Record<number, string>>({})

// 获取活跃租约，建立 tenantId → leaseEnd 映射
const fetchActiveLeases = async () => {
  try {
    // 拉全部租约（不按日期过滤），取每个租客最远的到期日
    const records = await leaseRecordsApi.list()
    const map: Record<number, string> = {}
    for (const r of records) {
      // 只要 is_active=true 的（排除已退租的），取最远到期日
      if (r.is_active && (!map[r.tenant_id] || r.lease_end > map[r.tenant_id])) {
        map[r.tenant_id] = r.lease_end
      }
    }
    tenantLeaseEndMap.value = map
  } catch (error) {
    console.error('获取租约信息失败:', error)
  }
}

// 格式化日期显示
const formatLeaseEnd = (tenantId: number): string => {
  const end = tenantLeaseEndMap.value[tenantId]
  if (!end) return '-'
  const d = new Date(end)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const daysLeft = Math.ceil((d.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
  const dateStr = d.toLocaleDateString('zh-CN')
  if (daysLeft < 0) return `${dateStr}（已过期${Math.abs(daysLeft)}天）`
  if (daysLeft <= 7) return `${dateStr}（${daysLeft === 0 ? '今天到期' : daysLeft + '天后'}）`
  return dateStr
}

// 从后端获取到期提醒（基于LeaseRecord，以租客为准）
const fetchExpiringLeases = async () => {
  try {
    const days = leaseExpiryWarningDays.value || 30
    const res = await statisticsApi.getExpiringLeases(days)
    // axios response.data 就是后端返回的数据
    const data = res.data || {}
    // 后端返回分类的critical/warning/normal，合并所有
    const all = [
      ...(data.critical || []),
      ...(data.warning || []),
      ...(data.normal || [])
    ]
    leaseExpiryWarnings.value = all.map((item: any) => ({
      roomId: item.room_id,
      roomNumber: item.room_number,
      tenantId: item.tenant_id,
      tenantName: item.tenant_name,
      leaseEnd: item.lease_end,
      daysLeft: item.days_remaining,
      monthlyRent: item.monthly_rent || 0
    })).sort((a: LeaseExpiryWarning, b: LeaseExpiryWarning) => a.daysLeft - b.daysLeft)
  } catch (error) {
    console.error('获取到期提醒失败:', error)
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
  fetchExpiringLeases()
  fetchTenants()
  fetchActiveLeases()
})

// 按合同到期日排序：最近到期的排前面，没有租约的排最后
const sortedTenants = computed(() => {
  return [...tenants.value].sort((a, b) => {
    const ea = tenantLeaseEndMap.value[a.id] || '9999-12-31'
    const eb = tenantLeaseEndMap.value[b.id] || '9999-12-31'
    return ea.localeCompare(eb)
  })
})
</script>

<template>
  <div class="tenants-page">
    <div class="page-header">
      <h2>租客管理</h2>
      <el-button type="primary" :icon="Plus" @click="handleAdd">新增租客</el-button>
    </div>

    <!-- 合同到期提醒 -->
    <div v-if="leaseExpiryWarnings.length > 0" class="expiry-section">
      <div class="expiry-header">
        <span class="expiry-header-icon">📋</span>
        <span class="expiry-header-title">合同到期提醒</span>
        <span class="expiry-header-count">{{ leaseExpiryWarnings.length }} 个租客</span>
      </div>
      <div class="expiry-cards">
        <div
          v-for="warning in leaseExpiryWarnings"
          :key="warning.roomId"
          class="expiry-card"
          :class="{
            'expiry-card-danger': warning.daysLeft < 0,
            'expiry-card-warning': warning.daysLeft >= 0 && warning.daysLeft <= 7,
            'expiry-card-info': warning.daysLeft > 7
          }"
        >
          <div class="expiry-card-left">
            <div class="expiry-room">{{ warning.roomNumber }}</div>
            <div class="expiry-tenant">{{ warning.tenantName }}</div>
          </div>
          <div class="expiry-card-right">
            <div class="expiry-date">到期日：{{ warning.leaseEnd }}</div>
            <div class="expiry-days" v-if="warning.daysLeft < 0">
              已过期 <span class="days-num days-num-danger">{{ Math.abs(warning.daysLeft) }}</span> 天
            </div>
            <div class="expiry-days" v-else-if="warning.daysLeft === 0">
              <span class="days-num days-num-warning">今天到期</span>
            </div>
            <div class="expiry-days" v-else>
              还有 <span class="days-num">{{ warning.daysLeft }}</span> 天
            </div>
          </div>
        </div>
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
      <el-tab-pane label="入住" name="active" />
      <el-tab-pane label="未入住" name="unassigned" />
      <el-tab-pane label="搬离" name="inactive" />
    </el-tabs>

    <!-- 电脑端：表格 -->
    <el-table
      v-loading="loading"
      :data="sortedTenants"
      stripe
      style="width: 100%"
      class="hidden-mobile"
    >
      <el-table-column prop="name" label="姓名" width="120" />
      <el-table-column prop="phone" label="电话" width="160" />
      <el-table-column label="合同到期" min-width="180">
        <template #default="{ row }">
          <span :class="{ 'lease-expired': tenantLeaseEndMap[row.id] && new Date(tenantLeaseEndMap[row.id]) < new Date(), 'lease-soon': tenantLeaseEndMap[row.id] && (() => { const d = new Date(tenantLeaseEndMap[row.id]); const days = Math.ceil((d.getTime() - Date.now()) / 86400000); return days >= 0 && days <= 7 })() }">
            {{ formatLeaseEnd(row.id) }}
          </span>
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
      <div v-for="tenant in sortedTenants" :key="tenant.id" class="tenant-card">
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
            <span class="card-label">合同到期</span>
            <span class="card-value">{{ formatLeaseEnd(tenant.id) }}</span>
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

/* 合同到期样式 */
.lease-expired {
  color: #f56c6c;
  font-weight: 600;
}
.lease-soon {
  color: #e6a23c;
  font-weight: 600;
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
.expiry-section {
  margin-bottom: 1rem;
}

.expiry-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  padding: 0 2px;
}

.expiry-header-icon {
  font-size: 1.2rem;
}

.expiry-header-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.expiry-header-count {
  font-size: 12px;
  background: #e6e8eb;
  color: #606266;
  padding: 2px 8px;
  border-radius: 10px;
}

.expiry-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 10px;
}

.expiry-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-radius: 10px;
  border-left: 4px solid;
  transition: transform 0.15s, box-shadow 0.15s;
}

.expiry-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

/* 默认（>7天）- 蓝色系 */
.expiry-card-info {
  background: linear-gradient(135deg, #e8f4fd 0%, #d6ecfa 100%);
  border-left-color: #409eff;
}

.expiry-card-info .expiry-room { color: #337ecc; }
.expiry-card-info .expiry-tenant { color: #409eff; }
.expiry-card-info .expiry-date { color: #79bbff; }
.expiry-card-info .expiry-days { color: #337ecc; }
.expiry-card-info .days-num { color: #409eff; font-weight: 700; font-size: 1.1em; }

/* 即将到期（0-7天）- 橙色系 */
.expiry-card-warning {
  background: linear-gradient(135deg, #fef6e0 0%, #fdf0c7 100%);
  border-left-color: #e6a23c;
}

.expiry-card-warning .expiry-room { color: #b88230; }
.expiry-card-warning .expiry-tenant { color: #e6a23c; }
.expiry-card-warning .expiry-date { color: #c9a063; }
.expiry-card-warning .expiry-days { color: #b88230; }
.expiry-card-warning .days-num { color: #e6a23c; font-weight: 700; font-size: 1.1em; }
.days-num-warning { color: #e6a23c !important; font-weight: 700; font-size: 1em; }

/* 已过期 - 红色系 */
.expiry-card-danger {
  background: linear-gradient(135deg, #fef0f0 0%, #fde2e2 100%);
  border-left-color: #f56c6c;
}

.expiry-card-danger .expiry-room { color: #c45656; }
.expiry-card-danger .expiry-tenant { color: #f56c6c; }
.expiry-card-danger .expiry-date { color: #c99191; }
.expiry-card-danger .expiry-days { color: #c45656; }
.days-num-danger { color: #f56c6c !important; font-weight: 700; font-size: 1.1em; }

.expiry-card-left {
  flex-shrink: 0;
}

.expiry-room {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 2px;
}

.expiry-tenant {
  font-size: 13px;
  font-weight: 500;
}

.expiry-card-right {
  text-align: right;
}

.expiry-date {
  font-size: 12px;
  margin-bottom: 2px;
}

.expiry-days {
  font-size: 13px;
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
  .expiry-cards {
    grid-template-columns: 1fr;
  }
  .expiry-card {
    padding: 10px 12px;
  }
  .expiry-room {
    font-size: 15px;
  }
}
</style>
