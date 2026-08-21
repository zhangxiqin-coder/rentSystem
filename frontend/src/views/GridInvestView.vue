<script setup lang="ts">
import { ref, computed } from 'vue'

const fundName = ref('')
const basePrice = ref(1.0)
const lotAmount = ref(10000)
const gridLevels = ref(5)

interface GridRow {
  level: number
  price: number
  pct: number
  amount: number
  cumLots?: number
  avgCost?: number
  totalCost?: number
  profit?: number
  buyPrice?: number
}

const buyGrid = computed<GridRow[]>(() => {
  const rows: GridRow[] = []
  let totalCost = lotAmount.value
  let totalShares = lotAmount.value / basePrice.value
  for (let i = 1; i <= gridLevels.value; i++) {
    const price = basePrice.value * Math.pow(0.96, i)
    const amount = lotAmount.value
    const shares = amount / price
    totalCost += amount
    totalShares += shares
    const avgCost = totalCost / totalShares
    rows.push({
      level: i,
      price: Math.round(price * 10000) / 10000,
      pct: -Math.round((1 - Math.pow(0.96, i)) * 10000) / 100,
      amount,
      cumLots: i + 1,
      avgCost: Math.round(avgCost * 10000) / 10000,
      totalCost: Math.round(totalCost * 100) / 100,
    })
  }
  return rows
})

// 卖出网格：每手独立，买入价×1.04=卖出目标
const sellGrid = computed<GridRow[]>(() => {
  const rows: GridRow[] = []
  // 初始持仓（第0手）
  const initBuy = basePrice.value
  const initSell = initBuy * 1.04
  rows.push({
    level: 1,
    buyPrice: initBuy,
    price: Math.round(initSell * 10000) / 10000,
    pct: 4.0,
    amount: lotAmount.value,
    profit: Math.round(lotAmount.value * 0.04 * 100) / 100,
  })
  // 每个补仓层对应一个卖出目标
  for (let i = 1; i <= gridLevels.value; i++) {
    const buyPrice = basePrice.value * Math.pow(0.96, i)
    const sellPrice = buyPrice * 1.04
    rows.push({
      level: i + 1,
      buyPrice: Math.round(buyPrice * 10000) / 10000,
      price: Math.round(sellPrice * 10000) / 10000,
      pct: 4.0,
      amount: lotAmount.value,
      profit: Math.round(lotAmount.value * 0.04 * 100) / 100,
    })
  }
  return rows
})

const totalBuyCapital = computed(() => {
  return lotAmount.value * (gridLevels.value + 1)
})

const formatMoney = (v: number) => '¥' + v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const formatPrice = (v: number) => v.toFixed(4)
const formatPct = (v: number) => (v >= 0 ? '+' : '') + v.toFixed(1) + '%'
</script>

<template>
  <div class="grid-invest-page">
    <div class="page-header">
      <h2>📊 4%网格定投法</h2>
      <p class="subtitle">指数基金估值合理时，每跌4%买一手，每涨4%卖一手</p>
    </div>

    <!-- 输入区 -->
    <el-card class="input-card">
      <div class="input-row">
        <div class="input-item">
          <label>基金名称</label>
          <el-input v-model="fundName" placeholder="如：沪深300ETF" size="default" />
        </div>
        <div class="input-item">
          <label>买入价格</label>
          <el-input-number v-model="basePrice" :precision="4" :step="0.01" :min="0.0001" size="default" controls-position="right" />
        </div>
        <div class="input-item">
          <label>每手金额（元）</label>
          <el-input-number v-model="lotAmount" :precision="0" :step="1000" :min="1" size="default" controls-position="right" />
        </div>
        <div class="input-item">
          <label>网格层数</label>
          <el-input-number v-model="gridLevels" :min="1" :max="10" :step="1" size="default" controls-position="right" />
        </div>
      </div>
    </el-card>

    <!-- 概况 -->
    <el-card v-if="basePrice > 0 && lotAmount > 0" class="summary-card">
      <div class="summary-row">
        <div class="summary-item">
          <span class="summary-label">基准价</span>
          <span class="summary-val">{{ formatPrice(basePrice) }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">首笔买入</span>
          <span class="summary-val">{{ formatMoney(lotAmount) }}</span>
        </div>
        <div class="summary-item buy">
          <span class="summary-label">买入总资金</span>
          <span class="summary-val">{{ formatMoney(totalBuyCapital) }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">步长</span>
          <span class="summary-val">±4%</span>
        </div>
      </div>
    </el-card>

    <!-- 网格表格 -->
    <div class="grid-tables">
      <!-- 买入网格 -->
      <el-card class="grid-card buy-card">
        <template #header>
          <div class="card-header">
            <span>📉 买入网格 — 跌到目标价就买一手</span>
          </div>
        </template>
        <el-table :data="buyGrid" stripe size="small" :empty-text="'请先填写买入价格'">
          <el-table-column label="层级" width="70">
            <template #default="{ row }">
              <el-tag type="danger" size="small">买{{ row.level }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="触发价" width="110" align="right">
            <template #default="{ row }">
              <strong>{{ formatPrice(row.price) }}</strong>
            </template>
          </el-table-column>
          <el-table-column label="跌幅" width="90" align="right">
            <template #default="{ row }">
              <span class="down-pct">{{ formatPct(row.pct) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="买入金额" min-width="120" align="right">
            <template #default="{ row }">{{ formatMoney(row.amount) }}</template>
          </el-table-column>
          <el-table-column label="累计持仓(手)" width="110" align="right">
            <template #default="{ row }">{{ row.cumLots }}</template>
          </el-table-column>
          <el-table-column label="平均成本" min-width="110" align="right">
            <template #default="{ row }">
              <span class="avg-cost">{{ formatPrice(row.avgCost!) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="累计投入" min-width="120" align="right">
            <template #default="{ row }">
              <strong>{{ formatMoney(row.totalCost!) }}</strong>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 卖出网格 -->
      <el-card class="grid-card sell-card">
        <template #header>
          <div class="card-header">
            <span>📈 卖出网格 — 每手买入价涨4%就卖</span>
          </div>
        </template>
        <el-table :data="sellGrid" stripe size="small">
          <el-table-column label="层级" width="70">
            <template #default="{ row }">
              <el-tag type="success" size="small">卖{{ row.level }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="买入价" width="110" align="right">
            <template #default="{ row }">
              <span class="buy-ref">{{ formatPrice(row.buyPrice!) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="卖出价" width="110" align="right">
            <template #default="{ row }">
              <strong>{{ formatPrice(row.price) }}</strong>
            </template>
          </el-table-column>
          <el-table-column label="卖出金额" min-width="120" align="right">
            <template #default="{ row }">{{ formatMoney(row.amount) }}</template>
          </el-table-column>
          <el-table-column label="盈利" min-width="120" align="right">
            <template #default="{ row }">
              <span class="profit">{{ formatMoney(row.profit!) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- 说明 -->
    <el-card class="help-card">
      <template #header>💡 使用说明</template>
      <ul class="help-list">
        <li>选择一只估值合理（不高估）的指数基金，以当前价<strong>买入第1手</strong></li>
        <li>价格跌4% → <strong>再买一手</strong>（拉低平均成本）</li>
        <li>每一手独立管理：该手的<strong>买入价 × 1.04 = 卖出目标价</strong></li>
        <li>涨到哪手的卖出价，就卖哪手。卖完如果继续涨，等下一手的卖出价</li>
        <li>全部卖完=空仓，等跌回买1价再重新入场</li>
      </ul>
    </el-card>
  </div>
</template>

<style scoped>
.grid-invest-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 20px 16px 40px;
}

.page-header {
  text-align: center;
  margin-bottom: 20px;
}
.page-header h2 {
  margin: 0 0 4px;
  font-size: 22px;
}
.subtitle {
  margin: 0;
  color: #909399;
  font-size: 13px;
}

.input-card {
  margin-bottom: 16px;
}
.input-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  align-items: flex-end;
}
.input-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 160px;
  flex: 1;
}
.input-item label {
  font-size: 12px;
  color: #909399;
  font-weight: 500;
}

.summary-card {
  margin-bottom: 16px;
}
.summary-row {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  justify-content: center;
}
.summary-item {
  text-align: center;
}
.summary-label {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-bottom: 2px;
}
.summary-val {
  font-size: 18px;
  font-weight: 700;
  color: #303133;
}
.summary-item.buy .summary-val {
  color: #F56C6C;
}

.grid-tables {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
@media (max-width: 768px) {
  .grid-tables {
    grid-template-columns: 1fr;
  }
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.down-pct { color: #67C23A; font-weight: 600; }
.up-pct { color: #F56C6C; font-weight: 600; }
.buy-ref { color: #909399; }
.avg-cost { color: #E6A23C; font-weight: 600; }
.profit { color: #F56C6C; font-weight: 600; }

.help-card {
  background: #f0f9eb;
}
.help-list {
  margin: 0;
  padding-left: 20px;
  color: #606266;
  font-size: 13px;
  line-height: 1.8;
}
.help-list li {
  margin-bottom: 2px;
}
</style>
