<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, User, House } from '@element-plus/icons-vue'
import { tenantsApi } from '@/api/tenants'
import type { Tenant } from '@/types'

const router = useRouter()
const loading = ref(false)
const tenants = ref<Tenant[]>([])

// 获取租客列表
const fetchTenants = async () => {
  loading.value = true
  try {
    tenants.value = await tenantsApi.list()
  } catch (error) {
    ElMessage.error('获取租客列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

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
  fetchTenants()
})
</script>

<template>
  <div class="tenants-page">
    <div class="page-header">
      <h2>租客管理</h2>
      <el-button type="primary" :icon="Plus" @click="handleAdd">新增租客</el-button>
    </div>

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
      <el-table-column label="操作" width="180" fixed="right">
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
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}
</style>
