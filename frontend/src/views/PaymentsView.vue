<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { paymentApi } from '@/api/payment'
import { roomApi } from '@/api/room'
import type { Payment } from '@/types'
import type { Room } from '@/types'

const payments = ref<Payment[]>([])
const rooms = ref<Room[]>([])
const loading = ref(false)
const selectedRoomId = ref<number | null>(null)

// 合并同一次收租的记录（按 room_id + payment_date 分组）
const groupedPayments = computed(() => {
  const groups: { [key: string]: any } = {}
  
  payments.value.forEach(payment => {
    // 如果选择了房号，只显示该房间的记录
    if (selectedRoomId.value !== null && payment.room_id !== selectedRoomId.value) {
      return
    }
    
    const key = `${payment.room_id}_${payment.payment_date}`
    
    if (!groups[key]) {
      const room = rooms.value.find(r => r.id === payment.room_id)
      groups[key] = {
        room_id: payment.room_id,
        room_number: room?.room_number || `Room ${payment.room_id}`,
        payment_date: payment.payment_date,
        status: payment.status,
        rent: 0,
        water: 0,
        electricity: 0,
        total: 0
      }
    }
    
    // 根据payment_type累加金额
    if (payment.payment_type === 'rent') {
      groups[key].rent += Number(payment.amount) || 0
    } else if (payment.payment_type === 'utility') {
      // 通过description判断是水费还是电费
      const desc = (payment.description || '').toLowerCase()
      if (desc.includes('水') || desc.includes('water')) {
        groups[key].water += Number(payment.amount) || 0
      } else if (desc.includes('电') || desc.includes('electricity')) {
        groups[key].electricity += Number(payment.amount) || 0
      } else {
        // 如果无法区分，根据金额判断（通常水费较小）
        if (Number(payment.amount) < 50) {
          groups[key].water += Number(payment.amount) || 0
        } else {
          groups[key].electricity += Number(payment.amount) || 0
        }
      }
    }
    
    groups[key].total += Number(payment.amount) || 0
  })
  
  // 转为数组并按日期降序排序
  return Object.values(groups).sort((a, b) => 
    new Date(b.payment_date).getTime() - new Date(a.payment_date).getTime()
  )
})

// 检测漏交月份的提醒
const missedPaymentWarnings = computed(() => {
  const warnings: string[] = []
  
  // 按房间分组检查
  const roomPayments: { [roomId: number]: any[] } = {}
  payments.value.forEach(payment => {
    if (payment.payment_type === 'rent') {
      if (!roomPayments[payment.room_id]) {
        roomPayments[payment.room_id] = []
      }
      roomPayments[payment.room_id].push(payment)
    }
  })
  
  // 对每个房间检查是否漏交
  Object.keys(roomPayments).forEach(roomId => {
    const room = rooms.value.find(r => r.id === Number(roomId))
    if (!room) return
    
    const roomRentPayments = roomPayments[Number(roomId)]
      .sort((a, b) => new Date(b.payment_date).getTime() - new Date(a.payment_date).getTime())
    
    if (roomRentPayments.length < 2) return
    
    // 检查连续两次收租之间的月份间隔
    for (let i = 0; i < roomRentPayments.length - 1; i++) {
      const currentDate = new Date(roomRentPayments[i].payment_date)
      const prevDate = new Date(roomRentPayments[i + 1].payment_date)
      
      // 计算月份差异
      const monthDiff = (currentDate.getFullYear() - prevDate.getFullYear()) * 12 + 
                       (currentDate.getMonth() - prevDate.getMonth())
      
      // 如果间隔超过2个月，说明可能漏交了
      if (monthDiff > 1) {
        const missedMonths = monthDiff - 1
        warnings.push(
          `${room.room_number} 可能有 ${missedMonths} 个月未交租 ` +
          `(${prevDate.toISOString().split('T')[0]} → ${currentDate.toISOString().split('T')[0]})`
        )
      }
    }
  })
  
  return warnings
})

const loadPayments = async () => {
  loading.value = true
  try {
    const [paymentsRes, roomsRes] = await Promise.all([
      paymentApi.getPayments({ page: 1, size: 100 }),
      roomApi.getRooms()
    ])
    payments.value = paymentsRes.data.items
    rooms.value = roomsRes.data.items || roomsRes.data
  } catch (error) {
    console.error('Failed to load payments:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadPayments()
})
</script>

<template>
  <div class="payments-view">
    <header class="view-header">
      <h1>Payments</h1>
    </header>

    <main class="view-content">
      <!-- 漏交提醒 -->
      <div v-if="missedPaymentWarnings.length > 0" class="warning-alert">
        <div class="alert-icon">⚠️</div>
        <div class="alert-content">
          <strong>漏交提醒：</strong>
          <ul>
            <li v-for="(warning, index) in missedPaymentWarnings" :key="index">{{ warning }}</li>
          </ul>
        </div>
      </div>

      <!-- 筛选工具栏 -->
      <div class="filter-toolbar">
        <label class="filter-label">
          筛选房号：
          <select v-model="selectedRoomId" class="room-select">
            <option :value="null">全部房间</option>
            <option v-for="room in rooms" :key="room.id" :value="room.id">
              {{ room.room_number }}
            </option>
          </select>
        </label>
        <span v-if="selectedRoomId" class="filter-info">
          已选择：{{ rooms.find(r => r.id === selectedRoomId)?.room_number }}
          <button @click="selectedRoomId = null" class="clear-btn">清除</button>
        </span>
      </div>

      <div v-if="loading" class="loading">Loading...</div>
      <div v-else class="payments-list">
        <table>
          <thead>
            <tr>
              <th>房号</th>
              <th>收租日期</th>
              <th>房租</th>
              <th>水费</th>
              <th>电费</th>
              <th>合计</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="payment in groupedPayments" :key="`${payment.room_id}_${payment.payment_date}`">
              <td><strong>{{ payment.room_number }}</strong></td>
              <td>{{ payment.payment_date }}</td>
              <td>¥{{ payment.rent.toFixed(2) }}</td>
              <td>¥{{ payment.water.toFixed(2) }}</td>
              <td>¥{{ payment.electricity.toFixed(2) }}</td>
              <td><strong>¥{{ payment.total.toFixed(2) }}</strong></td>
              <td :class="`status-${payment.status}`">{{ payment.status }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </main>
  </div>
</template>

<style scoped>
.payments-view {
  min-height: 100vh;
  background-color: #f5f5f5;
}

.view-header {
  background: white;
  padding: 1.5rem 2rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.view-header h1 {
  margin: 0;
  color: #333;
}

.view-content {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.loading {
  text-align: center;
  padding: 2rem;
  color: #666;
}

.payments-list {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

table {
  width: 100%;
  border-collapse: collapse;
}

thead {
  background-color: #f9f9f9;
}

th {
  padding: 1rem;
  text-align: left;
  font-weight: 600;
  color: #555;
}

td {
  padding: 1rem;
  border-top: 1px solid #eee;
}

.status-pending {
  color: #ff9800;
}

.status-completed {
  color: #4caf50;
}

.status-overdue {
  color: #f44336;
}

.status-cancelled {
  color: #999;
}

/* 漏交提醒样式 */
.warning-alert {
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 8px;
  padding: 1rem 1.5rem;
  margin-bottom: 1.5rem;
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  box-shadow: 0 2px 4px rgba(255, 193, 7, 0.2);
}

.alert-icon {
  font-size: 1.5rem;
  flex-shrink: 0;
}

.alert-content {
  flex: 1;
}

.alert-content strong {
  color: #856404;
  display: block;
  margin-bottom: 0.5rem;
}

.alert-content ul {
  margin: 0;
  padding-left: 1.5rem;
  list-style: disc;
}

.alert-content li {
  color: #856404;
  margin-bottom: 0.25rem;
}

/* 筛选工具栏样式 */
.filter-toolbar {
  background: white;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  margin-bottom: 1.5rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.filter-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #333;
  font-weight: 500;
}

.room-select {
  padding: 0.5rem 2rem 0.5rem 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  font-size: 0.9rem;
  color: #333;
  cursor: pointer;
  min-width: 150px;
}

.room-select:hover {
  border-color: #409eff;
}

.room-select:focus {
  outline: none;
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.1);
}

.filter-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #409eff;
  font-size: 0.9rem;
  background: #ecf5ff;
  padding: 0.5rem 1rem;
  border-radius: 4px;
}

.clear-btn {
  background: #409eff;
  color: white;
  border: none;
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.2s;
}

.clear-btn:hover {
  background: #66b1ff;
}
</style>
