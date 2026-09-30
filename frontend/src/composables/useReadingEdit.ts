import { ref, type Ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { utilityApi } from '@/api/utility'
import type { UtilityReading } from '@/types'
import type { MergedReading } from '@/composables/useMergedReadings'

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

  // 删除合并行（水表+电表记录一起删）
  // 背景：2026-09-27 102A-1 删除失败——表格行是水+电合并行，把整行对象传给
  // 只收 readingId 的 handleDelete，URL 变成 /readings/[object Object] → 422
  const handleDeleteMergedRow = async (row: MergedReading) => {
    const ids: number[] = []
    const parts: string[] = []
    if (row.water_reading?.id) {
      ids.push(row.water_reading.id)
      parts.push(`水表#${row.water_reading.id}`)
    }
    if (row.electricity_reading?.id) {
      ids.push(row.electricity_reading.id)
      parts.push(`电表#${row.electricity_reading.id}`)
    }
    if (ids.length === 0) {
      ElMessage.warning('该行没有可删除的抄表记录')
      return
    }

    try {
      await ElMessageBox.confirm(
        `将删除 ${row.reading_date} 的 ${parts.join('、')}，删除后不可恢复，是否继续？`,
        '删除确认',
        { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
      )
    } catch {
      return // 用户取消
    }

    const failed: string[] = []
    for (const id of ids) {
      try {
        await utilityApi.deleteReading(id)
      } catch (error: any) {
        console.error(`Failed to delete reading ${id}:`, error)
        const detail = error?.response?.data?.detail || ''
        failed.push(detail || `记录#${id}`)
      }
    }
    if (failed.length === 0) {
      ElMessage.success(`已删除 ${parts.join('、')}`)
    } else {
      ElMessage.error(`部分删除失败：${failed.join('；')}`)
    }
    await loadReadings()
  }

  return {
    editDialogVisible,
    editLoading,
    editForm,
    showEditDialog,
    saveEdit,
    handleDelete,
    handleDeleteMergedRow,
  }
}
