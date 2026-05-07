import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { utilityApi } from '@/api/utility'
import type { UtilityReading } from '@/types'

interface UseReadingEditDeps {
  loadReadings: () => Promise<void>
  autoGenerateAndSendWechat: (roomId: number, readings: any[]) => Promise<void>
}

export function useReadingEdit(deps: UseReadingEditDeps) {
  const { loadReadings, autoGenerateAndSendWechat } = deps

  // 编辑对话框显示状态
  const editDialogVisible = ref(false)
  const editLoading = ref(false)

  // 编辑表单
  const editForm = ref<UtilityReading>({
    id: 0,
    room_id: 0,
    utility_type: 'water',
    reading_date: '',
    current_reading: 0,
    previous_reading: 0,
    amount: 0,
    notes: '',
  })

  // 显示编辑对话框
  const showEditDialog = (reading: UtilityReading) => {
    editForm.value = { ...reading }
    editDialogVisible.value = true
  }

  // 保存编辑
  const saveEdit = async () => {
    editLoading.value = true
    try {
      await utilityApi.updateReading(editForm.value.id!, {
        current_reading: editForm.value.current_reading,
        previous_reading: editForm.value.previous_reading,
        amount: editForm.value.amount,
        notes: editForm.value.notes,
      })

      ElMessage.success('保存成功')
      editDialogVisible.value = false

      // 刷新列表
      await loadReadings()

      // 如果需要，自动发送微信通知
      // await autoGenerateAndSendWechat(editForm.value.room_id, [editForm.value])
    } catch (error) {
      console.error('Failed to save reading:', error)
      ElMessage.error('保存失败')
    } finally {
      editLoading.value = false
    }
  }

  // 删除记录
  const handleDelete = async (readingId: number) => {
    try {
      await utilityApi.deleteReading(readingId)
      ElMessage.success('删除成功')
      await loadReadings()
    } catch (error) {
      console.error('Failed to delete reading:', error)
      ElMessage.error('删除失败')
    }
  }

  return {
    editDialogVisible,
    editLoading,
    editForm,
    showEditDialog,
    saveEdit,
    handleDelete,
  }
}
