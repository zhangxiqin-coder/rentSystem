<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useOverdueConfig } from '@/composables/useOverdueConfig'
import { authApi } from '@/api/auth'

const authStore = useAuthStore()
const {
  overdueCutoffDate, setOverdueCutoffDate,
  advanceRentDays, setAdvanceRentDays,
  expiringDays, setExpiringDays,
  recentPaymentDays, setRecentPaymentDays,
  recentReadingDays, setRecentReadingDays,
  lookbackMonths, setLookbackMonths,
  leaseExpiryWarningDays, setLeaseExpiryWarningDays,
  resetDefaults, defaults,
} = useOverdueConfig()

const tempCutoffDate = ref(overdueCutoffDate.value)
const tempAdvanceRentDays = ref(advanceRentDays.value)
const tempExpiringDays = ref(expiringDays.value)
const tempRecentPaymentDays = ref(recentPaymentDays.value)
const tempRecentReadingDays = ref(recentReadingDays.value)
const tempLookbackMonths = ref(lookbackMonths.value)
const tempLeaseExpiryWarningDays = ref(leaseExpiryWarningDays.value)
const tempSuperAdminMode = ref(authStore.superAdminMode)
const tempShowAssets = ref(authStore.showAssetsPage)

// 预设平台列表
const ALL_PLATFORMS = [
  { key: '支付宝', label: '支付宝' },
  { key: '且慢', label: '且慢' },
  { key: '网商银行', label: '网商银行' },
  { key: '腾讯理财通', label: '腾讯理财通' },
  { key: '雪球', label: '雪球' },
  { key: '京东金融', label: '京东金融' },
  { key: '平安证券', label: '平安证券' },
  { key: '其他', label: '其他' },
]

// 已启用的平台（存localStorage）
const loadEnabledPlatforms = (): string[] => {
  try {
    const saved = localStorage.getItem('asset_enabled_platforms')
    return saved ? JSON.parse(saved) : ALL_PLATFORMS.map(p => p.key)
  } catch {
    return ALL_PLATFORMS.map(p => p.key)
  }
}
const enabledPlatforms = ref<string[]>(loadEnabledPlatforms())

const saveEnabledPlatforms = () => {
  localStorage.setItem('asset_enabled_platforms', JSON.stringify(enabledPlatforms.value))
  ElMessage.success('资产平台配置已保存')
}

const tempDisplayName = ref(authStore.user?.full_name || '')
const savingName = ref(false)

// 甲方（房东）信息
const tempLandlordName = ref(authStore.user?.landlord_name || '张锡琴')
const tempLandlordPhone = ref(authStore.user?.landlord_phone || '13806504936')
const savingLandlordInfo = ref(false)

// 修改密码相关
const showPasswordDialog = ref(false)
const changingPassword = ref(false)
const passwordFormRef = ref<FormInstance>()
const passwordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const passwordRules: FormRules = {
  old_password: [
    { required: true, message: '请输入旧密码', trigger: 'blur' }
  ],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '新密码至少8位', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== passwordForm.value.new_password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

const handleSave = async () => {
  setOverdueCutoffDate(tempCutoffDate.value)
  setAdvanceRentDays(tempAdvanceRentDays.value)
  setExpiringDays(tempExpiringDays.value)
  setRecentPaymentDays(tempRecentPaymentDays.value)
  setRecentReadingDays(tempRecentReadingDays.value)
  setLookbackMonths(tempLookbackMonths.value)
  setLeaseExpiryWarningDays(tempLeaseExpiryWarningDays.value)
  ElMessage.success('保存成功，刷新页面后生效')
}

const handleSaveName = async () => {
  if (!authStore.user) return
  savingName.value = true
  try {
    await authApi.updateProfile(authStore.user.id, { full_name: tempDisplayName.value })
    await authStore.getCurrentUser()
    ElMessage.success('显示名称已更新')
  } catch {
    ElMessage.error('更新失败')
  } finally {
    savingName.value = false
  }
}

const handleSaveLandlordInfo = async () => {
  if (!authStore.user) return
  savingLandlordInfo.value = true
  try {
    await authApi.updateProfile(authStore.user.id, { 
      landlord_name: tempLandlordName.value,
      landlord_phone: tempLandlordPhone.value
    })
    await authStore.getCurrentUser()
    ElMessage.success('甲方信息已更新')
  } catch {
    ElMessage.error('更新失败')
  } finally {
    savingLandlordInfo.value = false
  }
}

const handleChangePassword = async () => {
  if (!passwordFormRef.value) return

  try {
    await passwordFormRef.value.validate()
    changingPassword.value = true

    try {
      await authApi.changePassword({
        old_password: passwordForm.value.old_password,
        new_password: passwordForm.value.new_password
      })

      ElMessage.success('密码修改成功，请重新登录')
      showPasswordDialog.value = false

      // 重置表单
      passwordForm.value = {
        old_password: '',
        new_password: '',
        confirm_password: ''
      }

      // 2秒后自动登出
      setTimeout(() => {
        authStore.logout()
        window.location.href = '/login'
      }, 2000)
    } catch (error: any) {
      ElMessage.error(error.response?.data?.detail || '密码修改失败')
    }
  } catch {
    // 表单验证失败
  } finally {
    changingPassword.value = false
  }
}

const handleReset = async () => {
  try {
    await ElMessageBox.confirm('确定恢复所有设置到默认值？', '恢复默认', { type: 'warning' })
    resetDefaults()
    tempCutoffDate.value = defaults.overdueCutoffDate as string
    tempAdvanceRentDays.value = defaults.advanceRentDays as number
    tempExpiringDays.value = defaults.expiringDays as number
    tempRecentPaymentDays.value = defaults.recentPaymentDays as number
    tempRecentReadingDays.value = defaults.recentReadingDays as number
    tempLookbackMonths.value = defaults.lookbackMonths as number
    tempLeaseExpiryWarningDays.value = defaults.leaseExpiryWarningDays as number
    ElMessage.success('已恢复默认值，刷新页面后生效')
  } catch {}
}

const handleToggleSuperAdmin = async () => {
  if (!tempSuperAdminMode.value) {
    // 关闭超级管理员模式
    authStore.toggleSuperAdminMode(false)
    ElMessage.info('超级管理员权限已关闭')
    return
  }

  // 开启超级管理员模式 - 需要确认
  try {
    await ElMessageBox.confirm(
      '超级管理员模式开启后可以删除记录（包括收租记录和水电记录），此操作不可恢复。确定开启吗？',
      '开启超级管理员权限',
      { type: 'warning', confirmButtonText: '确定开启', cancelButtonText: '取消' }
    )
    authStore.toggleSuperAdminMode(true)
    ElMessage.warning('超级管理员权限已开启，请谨慎操作')
  } catch {
    tempSuperAdminMode.value = false
  }
}

const handleToggleAssets = () => {
  authStore.toggleShowAssets(tempShowAssets.value)
  ElMessage.success(tempShowAssets.value ? '资产页面已开启' : '资产页面已关闭')
}
</script>

<template>
  <div class="settings-view">
    <div class="page-header">
      <h1>系统设置</h1>
    </div>

    <el-card>
      <template #header>
        <div class="card-header">
          <span class="card-title">收租提醒设置</span>
          <el-button size="small" @click="handleReset">恢复默认</el-button>
        </div>
      </template>

      <div class="setting-item">
        <div class="setting-info">
          <div class="setting-label">豁免截止日期</div>
          <div class="setting-desc">此日期之前的应交房租视为已收清，不再计入未收租提醒</div>
        </div>
        <el-date-picker
          v-model="tempCutoffDate"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
          style="width: 180px"
        />
      </div>

      <el-divider />

      <div class="setting-item">
        <div class="setting-info">
          <div class="setting-label">提前收租天数</div>
          <div class="setting-desc">应交日前几天开始计入欠租管理（默认 {{ defaults.advanceRentDays }} 天）</div>
        </div>
        <el-input-number v-model="tempAdvanceRentDays" :min="0" :max="10" style="width: 150px" />
      </div>

      <el-divider />

      <div class="setting-item">
        <div class="setting-info">
          <div class="setting-label">到期提醒天数</div>
          <div class="setting-desc">提前多少天显示即将到期提醒（默认 {{ defaults.expiringDays }} 天）</div>
        </div>
        <el-input-number v-model="tempExpiringDays" :min="1" :max="30" style="width: 150px" />
      </div>

      <el-divider />

      <div class="setting-item">
        <div class="setting-info">
          <div class="setting-label">近期缴费天数</div>
          <div class="setting-desc">多少天内有过缴费记录视为"近期已收"，不重复提醒（默认 {{ defaults.recentPaymentDays }} 天）</div>
        </div>
        <el-input-number v-model="tempRecentPaymentDays" :min="1" :max="30" style="width: 150px" />
      </div>

      <el-divider />

      <div class="setting-item">
        <div class="setting-info">
          <div class="setting-label">近期抄表天数</div>
          <div class="setting-desc">到期提醒中，多少天内的水电记录允许"标记已收"（默认 {{ defaults.recentReadingDays }} 天）</div>
        </div>
        <el-input-number v-model="tempRecentReadingDays" :min="1" :max="30" style="width: 150px" />
      </div>

      <el-divider />

      <div class="setting-item">
        <div class="setting-info">
          <div class="setting-label">缴费页回溯月数</div>
          <div class="setting-desc">缴费记录页收租概况显示最近几个月的数据（默认 {{ defaults.lookbackMonths }} 个月，即当月和上月）</div>
        </div>
        <el-input-number v-model="tempLookbackMonths" :min="1" :max="12" style="width: 150px" />
      </div>

      <el-divider />

      <div class="setting-item">
        <div class="setting-info">
          <div class="setting-label">合同到期提醒天数</div>
          <div class="setting-desc">租客管理页面提前多少天显示合同到期提醒（默认 {{ defaults.leaseExpiryWarningDays }} 天，即到期前1个月）</div>
        </div>
        <el-input-number v-model="tempLeaseExpiryWarningDays" :min="1" :max="365" style="width: 150px" />
      </div>

      <div style="margin-top: 20px; text-align: right;">
        <el-button type="primary" @click="handleSave">保存设置</el-button>
      </div>
    </el-card>

    <el-card style="margin-top: 20px;">
      <template #header>
        <span class="card-title">账户信息</span>
      </template>
      <div class="account-info">
        <div class="info-row">
          <span class="info-label">用户名</span>
          <span class="info-value">{{ authStore.user?.username }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">角色</span>
          <span class="info-value">{{ authStore.user?.role }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">显示名称</span>
          <div class="name-edit">
            <el-input v-model="tempDisplayName" placeholder="请输入显示名称" style="width: 200px" />
            <el-button type="primary" size="small" :loading="savingName" @click="handleSaveName">保存</el-button>
          </div>
        </div>
        <el-divider />
        <div style="margin-bottom: 15px; font-weight: 500; color: #409eff;">甲方（房东）信息</div>
        <div class="info-row">
          <span class="info-label">甲方姓名</span>
          <div class="name-edit">
            <el-input v-model="tempLandlordName" placeholder="请输入甲方姓名" style="width: 200px" />
          </div>
        </div>
        <div class="info-row">
          <span class="info-label">甲方电话</span>
          <div class="name-edit">
            <el-input v-model="tempLandlordPhone" placeholder="请输入甲方电话" style="width: 200px" />
            <el-button type="primary" size="small" :loading="savingLandlordInfo" @click="handleSaveLandlordInfo">保存</el-button>
          </div>
        </div>
        <el-divider />
        <div class="info-row">
          <span class="info-label">密码</span>
          <el-button type="primary" size="small" @click="showPasswordDialog = true">修改密码</el-button>
        </div>
      </div>
    </el-card>

    <!-- 修改密码对话框 -->
    <el-dialog
      v-model="showPasswordDialog"
      title="修改密码"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-form :model="passwordForm" :rules="passwordRules" ref="passwordFormRef" label-width="100px">
        <el-form-item label="旧密码" prop="old_password">
          <el-input
            v-model="passwordForm.old_password"
            type="password"
            placeholder="请输入旧密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="passwordForm.new_password"
            type="password"
            placeholder="请输入新密码（至少8位）"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input
            v-model="passwordForm.confirm_password"
            type="password"
            placeholder="请再次输入新密码"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPasswordDialog = false">取消</el-button>
        <el-button type="primary" :loading="changingPassword" @click="handleChangePassword">
          确认修改
        </el-button>
      </template>
    </el-dialog>

    <!-- 资产页面开关 -->
    <el-card style="margin-top: 20px;">
      <template #header>
        <span class="card-title">资产页面</span>
      </template>
      <div class="setting-item">
        <div class="setting-info">
          <div class="setting-label">显示资产页面</div>
          <div class="setting-desc">开启后导航栏显示"资产"入口，可查看和管理个人资产</div>
        </div>
        <el-switch
          v-model="tempShowAssets"
          active-text="已开启"
          inactive-text="已关闭"
          @change="handleToggleAssets"
        />
      </div>
    </el-card>

    <!-- 资产平台配置 -->
    <el-card style="margin-top: 20px;">
      <template #header>
        <span class="card-title">资产平台配置</span>
      </template>
      <div class="setting-desc" style="margin-bottom: 16px;">
        勾选你在使用的资产平台，个人资产页面只会显示已启用的平台
      </div>
      <div class="platform-grid">
        <el-checkbox-group v-model="enabledPlatforms">
          <el-checkbox v-for="p in ALL_PLATFORMS" :key="p.key" :label="p.key">
            {{ p.label }}
          </el-checkbox>
        </el-checkbox-group>
      </div>
      <el-button type="primary" size="small" style="margin-top: 12px;" @click="saveEnabledPlatforms">
        保存配置
      </el-button>
    </el-card>

    <el-card style="margin-top: 20px;">
      <template #header>
        <span class="card-title">超级管理员权限</span>
      </template>
      <div class="setting-item">
        <div class="setting-info">
          <div class="setting-label">启用删除权限</div>
          <div class="setting-desc">开启后可以删除收租记录和水电记录，此操作不可恢复，请谨慎使用</div>
        </div>
        <el-switch
          v-model="tempSuperAdminMode"
          active-text="已启用"
          inactive-text="未启用"
          style="--el-switch-on-color: #f56c6c; --el-switch-off-color: #dcdfe6;"
          @change="handleToggleSuperAdmin"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.settings-view {
  padding: 20px;
  max-width: 800px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-weight: 600;
  font-size: 16px;
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
}

.setting-info {
  flex: 1;
}

.setting-label {
  font-weight: 500;
  font-size: 14px;
  color: #303133;
  margin-bottom: 4px;
}

.setting-desc {
  font-size: 13px;
  color: #909399;
}

.account-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.info-label {
  min-width: 80px;
  color: #909399;
  font-size: 14px;
}

.info-value {
  color: #303133;
  font-size: 14px;
}

.name-edit {
  display: flex;
  gap: 8px;
  align-items: center;
}

.platform-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.platform-checkbox {
  min-width: 120px;
}
</style>
