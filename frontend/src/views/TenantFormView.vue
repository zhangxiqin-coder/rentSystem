<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { tenantsApi } from '@/api/tenants'
import type { Tenant, TenantCreate, TenantUpdate } from '@/types'

const router = useRouter()
const route = useRoute()
const tenantId = computed(() => Number(route.params.id))
const isEdit = computed(() => !!route.params.id)

const loading = ref(false)
const saving = ref(false)

const form = ref<TenantCreate>({
  name: '',
  phone: '',
  id_card: '',
  emergency_contact: '',
  emergency_phone: '',
  notes: ''
})

const rules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  phone: [{ required: true, message: '请输入电话', trigger: 'blur' }],
  id_card: [
    { pattern: /^[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]$/, message: '身份证号格式不正确', trigger: 'blur' }
  ]
}

const formRef = ref()

// 获取租客详情（编辑模式）
const fetchTenantDetail = async () => {
  if (!isEdit.value) return

  loading.value = true
  try {
    const tenant = await tenantsApi.get(tenantId.value)
    form.value = {
      name: tenant.name,
      phone: tenant.phone,
      id_card: tenant.id_card,
      emergency_contact: tenant.emergency_contact || '',
      emergency_phone: tenant.emergency_phone || '',
      notes: tenant.notes || ''
    }
  } catch (error) {
    ElMessage.error('获取租客详情失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 保存
const handleSave = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    if (isEdit.value) {
      await tenantsApi.update(tenantId.value, form.value as TenantUpdate)
      ElMessage.success('更新成功')
    } else {
      await tenantsApi.create(form.value)
      ElMessage.success('创建成功')
    }
    router.push('/tenants')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '保存失败')
    console.error(error)
  } finally {
    saving.value = false
  }
}

// 取消
const handleCancel = () => {
  router.back()
}

onMounted(() => {
  if (isEdit.value) {
    fetchTenantDetail()
  }
})
</script>

<template>
  <div class="tenant-form-page">
    <div v-loading="loading" class="page-content">
      <!-- 头部导航 -->
      <div class="page-header">
        <el-button :icon="ArrowLeft" @click="handleCancel">返回</el-button>
        <h2>{{ isEdit ? '编辑租客' : '新增租客' }}</h2>
        <el-button type="primary" @click="handleSave" :loading="saving">
          保存
        </el-button>
      </div>

      <!-- 表单 -->
      <el-card class="form-card">
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-width="120px"
          label-position="right"
        >
          <el-form-item label="姓名" prop="name">
            <el-input
              v-model="form.name"
              placeholder="请输入姓名"
              maxlength="50"
              show-word-limit
            />
          </el-form-item>

          <el-form-item label="电话" prop="phone">
            <el-input
              v-model="form.phone"
              placeholder="请输入电话号码"
              maxlength="20"
            />
          </el-form-item>

          <el-form-item label="身份证号" prop="id_card">
            <el-input
              v-model="form.id_card"
              placeholder="选填"
              maxlength="18"
            />
          </el-form-item>

          <el-form-item label="紧急联系人">
            <el-input
              v-model="form.emergency_contact"
              placeholder="选填"
              maxlength="50"
              show-word-limit
            />
          </el-form-item>

          <el-form-item label="紧急联系电话">
            <el-input
              v-model="form.emergency_phone"
              placeholder="选填"
              maxlength="20"
            />
          </el-form-item>

          <el-form-item label="备注">
            <el-input
              v-model="form.notes"
              type="textarea"
              :rows="4"
              placeholder="选填，可记录特殊需求或其他信息"
              maxlength="500"
              show-word-limit
            />
          </el-form-item>
        </el-form>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.tenant-form-page {
  padding: 20px;
}

.page-content {
  max-width: 800px;
  margin: 0 auto;
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

.form-card {
  margin-bottom: 20px;
}
</style>
