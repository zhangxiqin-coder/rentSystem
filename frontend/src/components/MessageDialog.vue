<script setup lang="ts">
defineProps<{
  modelValue: boolean
  message: string
  sendingWechat: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'copy': []
}>()
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="📱 收租消息（已自动推送到微信）"
    width="600px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-alert
      title="消息已生成"
      type="success"
      :closable="false"
      style="margin-bottom: 15px"
    >
      消息已自动推送到企业微信群，并复制到剪贴板
    </el-alert>

    <el-input
      :model-value="message"
      type="textarea"
      :rows="15"
      readonly
      style="font-family: 'Courier New', monospace; font-size: 14px"
    />

    <template #footer>
      <el-button type="primary" @click="emit('copy')">
        📋 复制消息
      </el-button>
      <el-button @click="emit('update:modelValue', false)">
        关闭
      </el-button>
    </template>
  </el-dialog>
</template>
