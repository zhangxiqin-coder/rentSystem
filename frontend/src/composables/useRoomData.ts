import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { roomApi } from '@/api/room'
import type { Room } from '@/types'

export function useRoomData() {
  const allRooms = ref<Room[]>([])
  const roomOptions = ref<Room[]>([])
  const roomsLoading = ref(false)

  const roomMap = computed(() => {
    const map = new Map<number, Room>()
    roomOptions.value.forEach(room => {
      map.set(room.id, room)
    })
    return map
  })

  const loadRooms = async () => {
    roomsLoading.value = true
    try {
      let loadedRooms: Room[] = []
      let page = 1
      let hasMore = true

      while (hasMore) {
        const res = await roomApi.getRooms({ page, size: 100 })
        const items = res.data.items || []
        loadedRooms = [...loadedRooms, ...items]
        hasMore = items.length === 100
        page++
      }

      roomOptions.value = loadedRooms
      allRooms.value = loadedRooms
    } catch (error) {
      console.error('Failed to load rooms:', error)
      ElMessage.error('加载房间列表失败')
    } finally {
      roomsLoading.value = false
    }
  }

  const getRoomNumber = (roomId: number) => {
    const room = roomMap.value.get(roomId)
    return room?.room_number || `房间${roomId}`
  }

  const getRoomInfo = (roomId: number, field: keyof Room) => {
    const room = roomMap.value.get(roomId)
    if (!room) return undefined
    return room[field]
  }

  const getRoom = (roomId: number) => {
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
