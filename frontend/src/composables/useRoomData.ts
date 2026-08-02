import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { roomApi } from '@/api/room'
import { tenantsApi } from '@/api/tenants'
import type { Room } from '@/types'

export function useRoomData() {
  // 所有房间数据
  const allRooms = ref<Room[]>([])
  const roomsLoading = ref(false)

  // 租客通知限制映射: tenant_id → notify_after_day
  const tenantNotifyMap = ref<Map<number, number>>(new Map())

  // 加载房间列表
  const loadRooms = async () => {
    roomsLoading.value = true
    try {
      // 加载所有房间（不限制分页大小）
      const res = await roomApi.getRooms({ size: 1000 })
      allRooms.value = res.data.items || []
    } catch (error) {
      console.error('Failed to load rooms:', error)
      ElMessage.error('加载房间列表失败')
    } finally {
      roomsLoading.value = false
    }
  }

  // 加载租客列表（提取通知限制信息）
  const loadTenantNotifyInfo = async () => {
    try {
      const tenants = await tenantsApi.list()
      const map = new Map<number, number>()
      for (const t of tenants) {
        if (t.notify_after_day) {
          map.set(t.id, t.notify_after_day)
        }
      }
      tenantNotifyMap.value = map
    } catch (error) {
      console.error('Failed to load tenant notify info:', error)
    }
  }

  // 用于下拉选择的房间选项
  const roomOptions = computed(() => allRooms.value)

  // 房间ID到房间对象的映射
  const roomMap = computed(() => {
    const map = new Map<number, Room>()
    allRooms.value.forEach(room => {
      map.set(room.id, room)
    })
    return map
  })

  // 根据房间ID获取房间号
  const getRoomNumber = (roomId: number): string => {
    const room = roomMap.value.get(roomId)
    return room?.room_number || `房间${roomId}`
  }

  // 根据房间ID获取完整房间信息
  const getRoomInfo = (roomId: number): Room | undefined => {
    return roomMap.value.get(roomId)
  }

  // 根据房间ID获取房间对象（别名，与 getRoomInfo 相同）
  const getRoom = (roomId: number): Room | undefined => {
    return roomMap.value.get(roomId)
  }

  // 根据房间ID获取该房间租客的通知限制日（null=无限制）
  const getNotifyAfterDay = (roomId: number): number | null => {
    const room = roomMap.value.get(roomId)
    if (!room?.tenant_id) return null
    return tenantNotifyMap.value.get(room.tenant_id) ?? null
  }

  return {
    allRooms,
    roomOptions,
    roomsLoading,
    roomMap,
    tenantNotifyMap,
    loadRooms,
    loadTenantNotifyInfo,
    getRoomNumber,
    getRoomInfo,
    getRoom,
    getNotifyAfterDay,
  }
}
