<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, MagicStick } from '@element-plus/icons-vue'
import { tenantsApi } from '@/api/tenants'
import type { Tenant, TenantCreate, TenantUpdate } from '@/types'

const router = useRouter()
const route = useRoute()
const tenantId = computed(() => Number(route.params.id))
const isEdit = computed(() => !!route.params.id)

const loading = ref(false)
const saving = ref(false)
const smartInput = ref('')

// 智能识别：从粘贴的文本中提取姓名、电话、身份证号
const parseSmartInput = () => {
  const text = smartInput.value.trim()
  if (!text) return

  // 提取身份证号：18位，最后一位可能是X/x
  const idCardMatch = text.match(/[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]/)
  if (idCardMatch) {
    const idCard = idCardMatch[0]
    form.value.id_card = idCard.length === 17 ? idCard : idCard.toUpperCase()
  }

  // 提取手机号：11位，1开头
  const phoneMatch = text.match(/1[3-9]\d{9}/)
  if (phoneMatch) {
    form.value.phone = phoneMatch[0]
  }

  // 提取姓名：去除身份证号和手机号后，剩下的中文部分
  let remaining = text
  if (idCardMatch) remaining = remaining.replace(idCardMatch[0], '')
  if (phoneMatch) remaining = remaining.replace(phoneMatch[0], '')
  // 提取连续的中文字符（2-4个字）
  const nameMatch = remaining.match(/[\u4e00-\u9fa5]{2,4}/)
  if (nameMatch) {
    form.value.name = nameMatch[0]
  }

  // 清空智能输入框
  smartInput.value = ''
  ElMessage.success('已自动识别并填入')
}

const form = ref<TenantCreate>({
  name: '',
  phone: '',
  id_card: '',
  emergency_contact: '',
  emergency_phone: '',
  notes: '',
  notify_after_day: null
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
      notes: tenant.notes || '',
      notify_after_day: tenant.notify_after_day ?? null
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
    // 空字符串转null，避免后端min_length校验失败
    const payload = { ...form.value }
    if (!payload.id_card) payload.id_card = undefined
    if (!payload.emergency_contact) payload.emergency_contact = undefined
    if (!payload.emergency_phone) payload.emergency_phone = undefined
    if (!payload.notes) payload.notes = undefined
    // notify_after_day: 空值传null（清除限制），有值传数字
    payload.notify_after_day = form.value.notify_after_day || null

    if (isEdit.value) {
      await tenantsApi.update(tenantId.value, payload as TenantUpdate)
      ElMessage.success('更新成功')
    } else {
      await tenantsApi.create(payload)
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

      <!-- 智能识别（仅新增模式） -->
      <el-card v-if="!isEdit" class="smart-card">
        <template #header>
          <div class="smart-header">
            <el-icon><MagicStick /></el-icon>
            <span>智能识别</span>
          </div>
        </template>
        <div class="smart-input-row">
          <el-input
            v-model="smartInput"
            placeholder="粘贴姓名、电话、身份证号（混合在一起也行），自动识别填入"
            clearable
            @keyup.enter="parseSmartInput"
          />
          <el-button type="primary" @click="parseSmartInput" :disabled="!smartInput.trim()">
            识别
          </el-button>
        </div>
        <div class="smart-tip">支持格式：张三138001380003301002000101001234 或 张三 13800138000 3301002000101001234</div>
      </el-card>

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

          <el-form-item label="催收通知限制">
            <el-input-number
              v-model="form.notify_after_day"
              :min="1"
              :max="31"
              placeholder="无限制"
              controls-position="right"
              style="width: 200px"
            />
            <span class="form-tip">约定每月几号后才能发催收消息，留空=无限制</span>
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

.smart-card {
  margin-bottom: 16px;
}

.smart-card :deep(.el-card__header) {
  padding: 12px 20px;
}

.smart-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 16px;
  font-weight: 600;
  color: #409eff;
}

.smart-input-row {
  display: flex;
  gap: 10px;
}

.smart-input-row .el-input {
  flex: 1;
}

.smart-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

.form-tip {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}
</style>
