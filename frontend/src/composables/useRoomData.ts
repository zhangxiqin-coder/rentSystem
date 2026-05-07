import { ref, computed, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { roomApi } from '@/api/room'
import type { Room } from '@/types'

export function useRoomData() {
  // 所有房间数据
  const allRooms = ref<Room[]>([])
  const roomsLoading = ref(false)

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

  return {
    allRooms,
    roomOptions,
    roomsLoading,
    roomMap,
    loadRooms,
    getRoomNumber,
    getRoomInfo,
    getRoom,
  }
}
