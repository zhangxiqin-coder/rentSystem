import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { utilityApi } from '@/api/utility'
import type { MergedReading } from '@/composables/useMergedReadings'

export function useReadingEdit(deps: {
  loadReadings: () => Promise<void>
  autoGenerateAndSendWechat: (merged: MergedReading) => Promise<void>
}) {
  const { loadReadings, autoGenerateAndSendWechat } = deps

  const editDialogVisible = ref(false)
  const editLoading = ref(false)
  const editForm = ref({
    water_reading_id: null as number | null,
    electricity_reading_id: null as number | null,
    water_reading: 0,
    electricity_reading: 0,
    notes: '',
  })
  const editOriginalData = ref<MergedReading | null>(null)
  const loading = ref(false)

  // 显示编辑对话框
  const showEditDialog = (merged: MergedReading) => {
    editOriginalData.value = merged
    editForm.value = {
      water_reading_id: merged.water_reading?.id || null,
      electricity_reading_id: merged.electricity_reading?.id || null,
      water_reading: Number(merged.water_reading?.reading || 0),
      electricity_reading: Number(merged.electricity_reading?.reading || 0),
      notes: merged.notes || '',
    }
    editDialogVisible.value = true
  }

  // 保存编辑
  const saveEdit = async () => {
    try {
      editLoading.value = true
      const updatePromises: Promise<any>[] = []

      // 更新水表读数
      if (editForm.value.water_reading_id !== null && editForm.value.water_reading > 0) {
        updatePromises.push(
          utilityApi.updateReading(editForm.value.water_reading_id, {
            reading: editForm.value.water_reading,
            notes: editForm.value.notes,
          })
        )
      }

      // 更新电表读数
      if (editForm.value.electricity_reading_id !== null && editForm.value.electricity_reading > 0) {
        updatePromises.push(
          utilityApi.updateReading(editForm.value.electricity_reading_id, {
            reading: editForm.value.electricity_reading,
            notes: editForm.value.notes,
          })
        )
      }

      // 如果只有水或只有电，只更新备注
      if (editForm.value.water_reading_id === null && editForm.value.electricity_reading_id !== null) {
        updatePromises.push(
          utilityApi.updateReading(editForm.value.electricity_reading_id, {
            notes: editForm.value.notes,
          })
        )
      }
      if (editForm.value.electricity_reading_id === null && editForm.value.water_reading_id !== null) {
        updatePromises.push(
          utilityApi.updateReading(editForm.value.water_reading_id, {
            notes: editForm.value.notes,
          })
        )
      }

      await Promise.all(updatePromises)
      ElMessage.success('编辑成功')
      editDialogVisible.value = false

      // 自动生成并发送微信消息
      await autoGenerateAndSendWechat(editOriginalData.value!)
      loadReadings()
    } catch (error: any) {
      console.error('Failed to update reading:', error)
      const errorMsg = error.response?.data?.detail || '编辑失败，请重试'
      ElMessage.error(errorMsg)
    } finally {
      editLoading.value = false
    }
  }

  // 删除水电记录
  const handleDelete = async (row: MergedReading) => {
    const { ElMessageBox } = await import('element-plus')
    try {
      await ElMessageBox.confirm(
        '确定要删除这条水电记录吗？删除后无法恢复。',
        '删除确认',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        }
      )

      loading.value = true

      // 删除水费记录
      if (row.water_reading) {
        await utilityApi.deleteReading(row.water_reading.id)
      }

      // 删除电费记录
      if (row.electricity_reading) {
        await utilityApi.deleteReading(row.electricity_reading.id)
      }

      ElMessage.success('删除成功')
      await loadReadings()
    } catch (error) {
      if (error !== 'cancel') {
        console.error('删除失败:', error)
        ElMessage.error('删除失败')
      }
    } finally {
      loading.value = false
    }
  }

  return {
    editDialogVisible,
    editLoading,
    editForm,
    editOriginalData,
    showEditDialog,
    saveEdit,
    handleDelete,
  }
}
