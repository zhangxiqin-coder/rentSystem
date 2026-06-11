<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, User, Search, Refresh } from '@element-plus/icons-vue'
import { tenantsApi } from '@/api/tenants'
import type { Tenant, LeaseRecord } from '@/types'

const router = useRouter()
const loading = ref(false)
const tenants = ref<Tenant[]>([])
const activeTab = ref('active')  // active: 在租, inactive: 已搬走
const searchKeyword = ref('')

// 续租对话框
const renewDialogVisible = ref(false)
const renewLoading = ref(false)
const currentRenewTenant = ref<Tenant | null>(null)
const renewForm = ref({
  months: 1,
  monthly_rent: undefined as number | undefined,
  notes: ''
})

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

// 打开续租对话框
const handleRenew = async (tenant: Tenant) => {
  currentRenewTenant.value = tenant
  renewForm.value = {
    months: 1,
    monthly_rent: undefined,
    notes: ''
  }
  renewDialogVisible.value = true
}

// 提交续租
const submitRenew = async () => {
  if (!currentRenewTenant.value) return
  if (renewForm.value.months <= 0) {
    ElMessage.warning('续租月数必须大于0')
    return
  }

  renewLoading.value = true
  try {
    const data: { months: number; monthly_rent?: number; notes?: string } = {
      months: renewForm.value.months
    }
    if (renewForm.value.monthly_rent) {
      data.monthly_rent = renewForm.value.monthly_rent
    }
    if (renewForm.value.notes.trim()) {
      data.notes = renewForm.value.notes.trim()
    }

    await tenantsApi.renew(currentRenewTenant.value.id, data)
    ElMessage.success(`租客 ${currentRenewTenant.value.name} 续租成功`)
    renewDialogVisible.value = false
    await fetchTenants()
  } catch (error: any) {
    const msg = error?.response?.data?.detail || '续租失败'
    ElMessage.error(msg)
    console.error(error)
  } finally {
    renewLoading.value = false
  }
}

onMounted(() => {
  fetchTenants()
})
</script>

<template>
  <div class="tenants-page">
    <div class="page-header">
      <h2>租客管理</h2>
      <el-button type="primary" :icon="Plus" @click="handleAdd">新增租客</el-button>
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

    <el-table
      v-loading="loading"
      :data="tenants"
      stripe
      style="width: 100%"
    >
      <el-table-column prop="name" label="姓名" width="120" />
      <el-table-column prop="phone" label="电话" width="150" />
      <el-table-column prop="id_card" label="身份证号" width="180" />
      <el-table-column prop="emergency_contact" label="紧急联系人" width="120" />
      <el-table-column prop="emergency_phone" label="紧急联系电话" width="150" />
      <el-table-column prop="notes" label="备注" show-overflow-tooltip />
      <el-table-column prop="created_at" label="创建时间" width="180">
        <template #default="{ row }">
          {{ new Date(row.created_at).toLocaleString('zh-CN') }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="{ row }">
          <el-button
            type="primary"
            :icon="User"
            size="small"
            @click="viewDetail(row)"
          >
            详情
          </el-button>
          <el-button
            v-if="activeTab === 'active'"
            type="success"
            :icon="Refresh"
            size="small"
            @click="handleRenew(row)"
          >
            续租
          </el-button>
          <el-button
            type="danger"
            :icon="Delete"
            size="small"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 续租对话框 -->
    <el-dialog
      v-model="renewDialogVisible"
      title="租客续租"
      width="450px"
      :close-on-click-modal="false"
    >
      <div v-if="currentRenewTenant" class="renew-info">
        <p><strong>租客：</strong>{{ currentRenewTenant.name }}</p>
        <p><strong>电话：</strong>{{ currentRenewTenant.phone }}</p>
      </div>
      <el-form label-width="100px" style="margin-top: 16px">
        <el-form-item label="续租月数">
          <el-input-number
            v-model="renewForm.months"
            :min="1"
            :max="120"
            :step="1"
          />
        </el-form-item>
        <el-form-item label="新月租金">
          <el-input
            v-model.number="renewForm.monthly_rent"
            placeholder="不填则保持原租金"
            type="number"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="renewForm.notes"
            type="textarea"
            :rows="3"
            placeholder="可选备注"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="renewDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="renewLoading" @click="submitRenew">确认续租</el-button>
      </template>
    </el-dialog>
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

.renew-info {
  background: #f5f7fa;
  padding: 12px 16px;
  border-radius: 8px;
}

.renew-info p {
  margin: 4px 0;
}
</style>
