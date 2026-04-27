<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { paymentApi } from '@/api/payment'
import { roomApi } from '@/api/room'
import { useAmountVisibility } from '@/composables/useAmountVisibility'
import type { Room } from '@/types'
import axios from 'axios'

const activeTab = ref('yearly')
const { hideAmounts, formatAmount } = useAmountVisibility()

// 年度统计
const yearlyStats = ref<any[]>([])
const yearlyLoading = ref(false)
const selectedYear = ref(new Date().getFullYear())
const availableYears = computed(() => {
  const years = new Set(yearlyStats.value.map(s => s.year))
  return Array.from(years).sort((a, b) => b - a)
})

// 房间账单
const rooms = ref<Room[]>([])
const selectedRoom = ref<number>()
const roomBilling = ref<any>(null)
const roomBillingLoading = ref(false)
const roomBillingYear = ref(new Date().getFullYear())

// 加载年度统计
const loadYearlyStats = async () => {
  yearlyLoading.value = true
  try {
    const token = localStorage.getItem('access_token')
    const response = await axios.get('/api/v1/payments/stats/yearly', {
      headers: {
        'Authorization': `Bearer ${token}`
      },
      params: { year: selectedYear.value || undefined }
    })
    yearlyStats.value = response.data || []
  } catch (error) {
    console.error('Failed to load yearly stats:', error)
    ElMessage.error('加载年度统计失败')
  } finally {
    yearlyLoading.value = false
  }
}

// 加载房间列表
const loadRooms = async () => {
  try {
    const res = await roomApi.getRooms({ page: 1, size: 100 })
    rooms.value = res.data.items || []
  } catch (error) {
    console.error('Failed to load rooms:', error)
  }
}

// 加载房间账单
const loadRoomBilling = async () => {
  if (!selectedRoom.value) return
  
  roomBillingLoading.value = true
  try {
    const token = localStorage.getItem('access_token')
    const response = await axios.get(`/api/v1/payments/stats/room/${selectedRoom.value}`, {
      headers: {
        'Authorization': `Bearer ${token}`
      },
      params: { year: roomBillingYear.value || undefined }
    })
    roomBilling.value = response.data
  } catch (error) {
    console.error('Failed to load room billing:', error)
    ElMessage.error('加载房间账单失败')
  } finally {
    roomBillingLoading.value = false
  }
}

// 汇总年度数据
const yearlySummary = computed(() => {
  const summary: any = {
    total: 0,
    byType: {
      rent: 0,
      water: 0,
      electricity: 0
    }
  }
  
  yearlyStats.value.forEach(stat => {
    summary.total += stat.total_amount
    summary.byType[stat.type] += stat.total_amount
  })
  
  return summary
})

onMounted(() => {
  loadRooms()
  loadYearlyStats()
})
</script>

<template>
  <div class="reports-view">
    <div class="page-header">
      <h1>📊 收租报表</h1>
    </div>

    <el-tabs v-model="activeTab">
      <!-- 年度统计 -->
      <el-tab-pane label="年度统计" name="yearly">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>📅 年度收入统计</span>
              <el-select v-model="selectedYear" placeholder="选择年份" @change="loadYearlyStats" style="width: 150px">
                <el-option label="全部年份" :value="0" />
                <el-option v-for="year in availableYears" :key="year" :label="`${year}年`" :value="year" />
              </el-select>
            </div>
          </template>

          <el-skeleton v-if="yearlyLoading" :rows="5" animated />
          
          <div v-else>
            <!-- 汇总卡片 -->
            <div v-if="yearlyStats.length > 0" class="summary-cards">
              <div class="summary-card total">
                <div class="label">总收入</div>
                <div class="amount">{{ formatAmount(yearlySummary.total) }}</div>
              </div>
              <div class="summary-card rent">
                <div class="label">房租收入</div>
                <div class="amount">{{ formatAmount(yearlySummary.byType.rent) }}</div>
              </div>
              <div class="summary-card water">
                <div class="label">水费收入</div>
                <div class="amount">{{ formatAmount(yearlySummary.byType.water) }}</div>
              </div>
              <div class="summary-card electricity">
                <div class="label">电费收入</div>
                <div class="amount">{{ formatAmount(yearlySummary.byType.electricity) }}</div>
              </div>
            </div>

            <!-- 详细数据表格 -->
            <el-table :data="yearlyStats" stripe style="margin-top: 20px">
              <el-table-column prop="year" label="年份" width="100" />
              <el-table-column prop="type" label="类型" width="120">
                <template #default="{ row }">
                  <el-tag v-if="row.type === 'rent'" type="success">房租</el-tag>
                  <el-tag v-else-if="row.type === 'water'" type="primary">水费</el-tag>
                  <el-tag v-else-if="row.type === 'electricity'" type="warning">电费</el-tag>
                  <el-tag v-else>{{ row.type }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="count" label="笔数" width="100" />
              <el-table-column prop="total_amount" label="总金额" width="150">
                <template #default="{ row }">
                  <span class="amount">{{ formatAmount(row.total_amount) }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- 房间账单 -->
      <el-tab-pane label="房间账单" name="room">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>🏠 房间账单明细</span>
              <div style="display: flex; gap: 10px; align-items: center;">
                <el-select v-model="roomBillingYear" placeholder="年份" style="width: 120px" @change="loadRoomBilling">
                  <el-option :label="`${new Date().getFullYear()}年`" :value="new Date().getFullYear()" />
                  <el-option :label="`${new Date().getFullYear() - 1}年`" :value="new Date().getFullYear() - 1" />
                </el-select>
                <el-select v-model="selectedRoom" placeholder="选择房间" style="width: 200px" @change="loadRoomBilling">
                  <el-option v-for="room in rooms" :key="room.id" :label="room.room_number" :value="room.id" />
                </el-select>
              </div>
            </div>
          </template>

          <el-empty v-if="!roomBilling" description="请选择房间查看账单" />
          
          <div v-else>
            <!-- 房间信息 -->
            <div class="room-info">
              <h3>{{ roomBilling.room.room_number }}</h3>
              <p>月租金：{{ hideAmounts ? '****' : formatAmount(roomBilling.room.monthly_rent) }}</p>
            </div>

            <!-- 账单明细 -->
            <el-table :data="roomBilling.billing" stripe style="margin-top: 20px">
              <el-table-column label="月份" width="120">
                <template #default="{ row }">
                  {{ row.year }}-{{ row.month.toString().padStart(2, '0') }}
                </template>
              </el-table-column>
              <el-table-column prop="rent" label="房租" width="120">
                <template #default="{ row }">
                  <span v-if="row.rent > 0" class="amount">{{ formatAmount(row.rent) }}</span>
                  <span v-else class="no-data">-</span>
                </template>
              </el-table-column>
              <el-table-column prop="water" label="水费" width="120">
                <template #default="{ row }">
                  <span v-if="row.water > 0" class="amount">{{ formatAmount(row.water) }}</span>
                  <span v-else class="no-data">-</span>
                </template>
              </el-table-column>
              <el-table-column prop="electricity" label="电费" width="120">
                <template #default="{ row }">
                  <span v-if="row.electricity > 0" class="amount">{{ formatAmount(row.electricity) }}</span>
                  <span v-else class="no-data">-</span>
                </template>
              </el-table-column>
              <el-table-column prop="total" label="总计" width="120">
                <template #default="{ row }">
                  <span class="amount total">{{ formatAmount(row.total) }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.reports-view {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  color: #303133;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.summary-card {
  padding: 20px;
  border-radius: 8px;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: transform 0.2s;
}

.summary-card:hover {
  transform: translateY(-4px);
}

.summary-card .label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}

.summary-card .amount {
  font-size: 24px;
  font-weight: 700;
}

.summary-card.total {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.summary-card.total .amount {
  color: white;
}

.summary-card.rent {
  border-left: 4px solid #67c23a;
}

.summary-card.water {
  border-left: 4px solid #409eff;
}

.summary-card.electricity {
  border-left: 4px solid #e6a23c;
}

.room-info {
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.room-info h3 {
  margin: 0 0 8px 0;
  color: #303133;
}

.room-info p {
  margin: 0;
  color: #606266;
}

.amount {
  color: #f56c6c;
  font-weight: 600;
}

.amount.total {
  font-size: 16px;
}

.no-data {
  color: #c0c4cc;
}
</style>
