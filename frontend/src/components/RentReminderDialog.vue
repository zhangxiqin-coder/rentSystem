<script setup lang="ts">
defineProps<{
  modelValue: boolean
  preview: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'copy': []
}>()
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="📢 催租消息预览"
    width="600px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="rent-reminder-preview">
      <el-input
        :model-value="preview"
        type="textarea"
        :rows="10"
        readonly
      />
    </div>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">关闭</el-button>
      <el-button type="primary" @click="emit('copy')">
        📋 复制消息
      </el-button>
    </template>
  </el-dialog>
</template>
