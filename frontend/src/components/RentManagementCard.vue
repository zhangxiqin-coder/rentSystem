<script setup lang="ts">
import type { Room } from '@/types'

interface OverdueItem {
  room: Room
  overdueDays: number
  overdueAmount: number
  lastPaymentDate: string
  nextPaymentDate: string
}

defineProps<{
  overdueRooms: OverdueItem[]
  expiringRooms: Room[]
  hideAmounts: boolean
  formatAmount: (value: number, currency?: string) => string
  maskedAmount: (value: number | string | null | undefined) => string
  getNextPaymentDays: (room: Room) => number
  canMarkExpiringRoomPaid: (room: Room) => boolean
}>()

const emit = defineEmits<{
  'send-reminder': [room: Room, type: 'overdue' | 'upcoming']
  'mark-paid': [room: Room]
  'open-utility-form': [roomId: number]
}>()
</script>

<template>
  <el-card class="expiring-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <span class="title">💰 收租管理</span>
        <div class="tags">
          <el-tag type="danger" size="small">欠租: {{ overdueRooms.length }} 个</el-tag>
          <el-tag type="warning" size="small">即将到期: {{ expiringRooms.length }} 个</el-tag>
        </div>
      </div>
    </template>

    <!-- 欠租房间列表 -->
    <div class="reminder-section">
      <div class="section-header overdue-header">
        <span class="section-title">🚨 欠租房间（已逾期）</span>
      </div>
      <div v-if="overdueRooms.length > 0" class="expiring-list">
        <div v-for="item in overdueRooms" :key="item.room.id" class="expiring-item overdue-item">
          <div class="room-info">
            <span class="room-number">{{ item.room.room_number }}</span>
            <span class="room-rent">{{ hideAmounts ? '****/月' : `¥${item.room.monthly_rent}/月` }}</span>
            <el-tag size="small" type="danger">逾期{{ item.overdueDays }}天</el-tag>
          </div>
          <div class="lease-info">
            <span class="overdue-amount">欠费总额: {{ maskedAmount(item.overdueAmount) }}</span>
            <div class="overdue-actions">
              <el-button
                v-if="canMarkExpiringRoomPaid(item.room)"
                type="success"
                size="small"
                @click="emit('mark-paid', item.room)"
              >
                ✅ 标记已收
              </el-button>
              <el-button
                v-else
                type="primary"
                size="small"
                @click="emit('open-utility-form', item.room.id)"
              >
                录入水电
              </el-button>
              <el-button type="danger" size="small" @click="emit('send-reminder', item.room, 'overdue')">
                📱 催租
              </el-button>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="empty-state">
        <el-text type="info">✅ 暂无欠租房间</el-text>
      </div>
    </div>

    <!-- 即将到期房间列表 -->
    <div class="reminder-section">
      <div class="section-header upcoming-header">
        <span class="section-title">📅 即将到期（7天内需收租）</span>
      </div>
      <div v-if="expiringRooms.length > 0" class="expiring-list">
        <div v-for="room in expiringRooms" :key="room.id" class="expiring-item">
          <div class="room-info">
            <span class="room-number">{{ room.room_number }}</span>
            <span class="room-rent">{{ hideAmounts ? '****/月' : `¥${room.monthly_rent}/月` }}</span>
            <el-tag size="small" type="info">{{ room.payment_cycle === 1 ? '月付' : room.payment_cycle === 3 ? '季付' : '年付' }}</el-tag>
          </div>
          <div class="lease-info">
            <el-tag :type="getNextPaymentDays(room) <= 3 ? 'danger' : 'warning'" size="small">
              {{ getNextPaymentDays(room) }}天后需收租
            </el-tag>
            <el-button
              v-if="canMarkExpiringRoomPaid(room)"
              type="success"
              size="small"
              @click="emit('mark-paid', room)"
            >
              ✅ 标记已收
            </el-button>
            <el-button
              v-else
              type="primary"
              size="small"
              @click="emit('open-utility-form', room.id)"
            >
              录入水电
            </el-button>
          </div>
        </div>
      </div>
      <div v-else class="empty-state">
        <el-text type="info">✅ 暂无即将到期房间</el-text>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.expiring-card {
  margin-bottom: 20px;
  border: 1px solid #e6a23c;
  background: linear-gradient(135deg, #fff7e6 0%, #ffffff 100%);
}

.expiring-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.expiring-card .title {
  font-weight: 600;
  color: #e6a23c;
}

.expiring-card .tags {
  display: flex;
  gap: 8px;
}

.reminder-section {
  margin-bottom: 16px;
}

.reminder-section:last-child {
  margin-bottom: 0;
}

.section-header {
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 12px;
  background: white;
  border-left: 4px solid;
}

.section-header.overdue-header {
  border-left-color: #f56c6c;
  background: linear-gradient(135deg, #fef0f0 0%, #ffffff 100%);
}

.section-header.upcoming-header {
  border-left-color: #e6a23c;
  background: linear-gradient(135deg, #fff7e6 0%, #ffffff 100%);
}

.section-title {
  font-weight: 600;
  font-size: 14px;
  color: #606266;
}

.overdue-item {
  background: linear-gradient(135deg, #fef0f0 0%, #ffffff 100%);
  border-color: #fbc4c4;
}

.overdue-amount {
  font-size: 13px;
  color: #f56c6c;
  font-weight: 600;
  margin-right: 8px;
}

.overdue-actions {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.expiring-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.empty-state {
  padding: 24px;
  text-align: center;
  background: #f9f9f9;
  border-radius: 6px;
  border: 1px dashed #dcdfe6;
}

.expiring-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: white;
  border-radius: 6px;
  border: 1px solid #f5dab1;
  transition: all 0.2s;
}

.expiring-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 2px 8px rgba(230, 162, 60, 0.2);
}

.expiring-item .room-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.expiring-item .room-number {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.expiring-item .room-rent {
  font-size: 13px;
  color: #909399;
}

.expiring-item .lease-info {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}
</style>
