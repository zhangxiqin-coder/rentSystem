# 前端逾期逻辑简化迁移指南

## 📋 概述

既然后端已经实现了统一的智能逾期判断逻辑,前端可以简化为**直接调用后端API**,无需在本地重复计算。

---

## 🎯 优化目标

### 之前的问题:
- ❌ 前端 `useOverdueManagement.ts` (470行) 重复实现复杂的逾期计算逻辑
- ❌ 前后端逻辑可能不一致
- ❌ 维护成本高,修改需要同步两处

### 优化后的方案:
- ✅ 前端 `useOverdueManagementSimple.ts` (97行) 直接调用后端API
- ✅ 单一数据源,保证一致性
- ✅ 代码量减少80%,易于维护

---

## 📦 新增文件

### 1. 后端 API
**文件**: [backend/app/api/reminders.py](file:///d:/codespace/rentSystem_repo/backend/app/api/reminders.py)

**新增接口**: `GET /api/v1/reminders/overdue-rooms`

**返回数据结构**:
```json
{
  "overdue": [
    {
      "room_id": 1,
      "room_number": "101",
      "tenant_name": "张三",
      "monthly_rent": 1000,
      "payment_cycle": 1,
      "rent_due": 1000,
      "utility_amount": 130,
      "total_amount": 1130,
      "target_due": "2024-04-05",
      "days_to_due": -35,
      "overdue_days": 35,
      "last_payment_date": "2024-03-05",
      "lease_start": "2024-01-05"
    }
  ],
  "expiring": [...],
  "overdue_count": 5,
  "expiring_count": 3
}
```

### 2. 前端 API 封装
**文件**: [frontend/src/api/reminders.ts](file:///d:/codespace/rentSystem_repo/frontend/src/api/reminders.ts)

**主要接口**:
```typescript
export const remindersApi = {
  // 获取逾期房间列表(推荐使用)
  getOverdueRooms: (params?: { advance_rent_days?: number }) => 
    request.get<OverdueRoomsResponse>('/api/v1/reminders/overdue-rooms', { params }),
  
  // 获取即将到期的提醒
  getUpcomingReminders: (params?: {...}) => ...,
  
  // 获取提醒摘要统计
  getRemindersSummary: () => ...,
  
  // 发送提醒通知
  sendReminderNotifications: (params?: {...}) => ...,
  
  // 为单个房间发送催租通知
  sendRentReminder: (roomId: number) => ...,
}
```

### 3. 简化版 Composable
**文件**: [frontend/src/composables/useOverdueManagementSimple.ts](file:///d:/codespace/rentSystem_repo/frontend/src/composables/useOverdueManagementSimple.ts)

**使用方法**:
```typescript
import { useOverdueManagementSimple } from '@/composables/useOverdueManagementSimple'

const {
  overdueRooms,      // 已逾期房间列表
  expiringRooms,     // 即将到期房间列表
  loading,           // 加载状态
  advanceRentDays,   // 提前收租天数
  
  loadOverdueRooms,  // 加载数据
  refresh,           // 刷新数据
  sendReminder,      // 发送催租消息
  markExpiringRoomPaid,  // 标记已支付
  canMarkExpiringRoomPaid,
  getNextPaymentDays,
} = useOverdueManagementSimple()
```

---

## 🔄 迁移步骤

### Step 1: 更新 UtilityView.vue

**当前代码** (第104-112行):
```typescript
// 旧的复杂 composable
const {
  overdueRooms, expiringRooms,
  canMarkExpiringRoomPaid, markExpiringRoomPaid,
  sendReminder, getNextPaymentDays,
} = useOverdueManagement({
  allRooms, payments, allReadings, roomOptions, formatAmount, formatAmountForNotification,
  mergedReadings, showPaymentDialog,
})
```

**替换为**:
```typescript
// 新的简化 composable
import { useOverdueManagementSimple } from '@/composables/useOverdueManagementSimple'

const {
  overdueRooms, expiringRooms,
  canMarkExpiringRoomPaid, markExpiringRoomPaid,
  sendReminder, getNextPaymentDays,
  loading: overdueLoading,  // 添加加载状态
} = useOverdueManagementSimple()
```

**移除不再需要的依赖**:
```typescript
// 删除这些导入(如果其他地方不需要)
// import { useOverdueManagement } from '@/composables/useOverdueManagement'
// import { usePaymentData } from '@/composables/usePaymentData'
```

### Step 2: 处理支付对话框

由于简化的 composable 不再接收 `showPaymentDialog`,需要单独处理:

```typescript
// 保留原有的 payment composable
const {
  showPaymentDialog,
  // ...其他方法
} = usePaymentData({ formatAmount, loadReadings, loadRooms })

// 重写 markExpiringRoomPaid
const handleMarkExpiringRoomPaid = async (room: OverdueRoom) => {
  // 获取最近的水电记录
  const reading = await utilityApi.getLatestUnpaidReading(room.room_id)
  if (reading) {
    showPaymentDialog(reading)
  } else {
    ElMessage.warning('暂无未支付的水电记录')
  }
}
```

### Step 3: 处理催租消息生成

```typescript
// 保留 message generation composable
const {
  generateMessageText,
  showCopyFallback,
  // ...其他方法
} = useMessageGeneration({...})

// 重写 sendReminder
const handleSendReminder = async (room: OverdueRoom, type: 'overdue' | 'upcoming') => {
  try {
    const message = await generateMessageText(room.room_id)
    const success = await copyToClipboard(message)
    
    if (success) {
      ElMessage.success('✅ 催租消息已复制,可直接粘贴发送')
    } else {
      ElMessage.error('复制失败,请手动复制消息')
    }
  } catch (error) {
    console.error('Failed to generate message:', error)
    ElMessage.error('生成催租消息失败')
  }
}
```

### Step 4: 更新模板绑定

**RentManagementCard 组件的props保持不变**,因为数据结构兼容:

```vue
<RentManagementCard
  :overdue-rooms="overdueRooms"
  :expiring-rooms="expiringRooms"
  :hide-amounts="hideAmounts"
  :format-amount="formatAmount"
  :masked-amount="maskedAmount"
  :get-next-payment-days="getNextPaymentDays"
  :can-mark-expiring-room-paid="canMarkExpiringRoomPaid"
  @send-reminder="handleSendReminder"
  @mark-paid="handleMarkExpiringRoomPaid"
  @open-utility-form="openUtilityForm"
/>
```

---

## 📊 数据结构对比

### 旧结构 (前端计算)
```typescript
interface OverdueRoom {
  room: Room              // 完整的Room对象
  overdueDays: number
  overdueAmount: number
  lastPaymentDate: string
  nextPaymentDate: string
}
```

### 新结构 (后端返回)
```typescript
interface OverdueRoom {
  room_id: number
  room_number: string
  tenant_name: string | null
  monthly_rent: number
  payment_cycle: number
  rent_due: number
  utility_amount: number
  total_amount: number
  target_due: string
  days_to_due: number
  overdue_days?: number
  days_until_due?: number
  last_payment_date: string | null
  lease_start: string | null
}
```

**优势**:
- ✅ 扁平化结构,更易使用
- ✅ 包含所有必要信息,无需额外查询
- ✅ 类型安全,有明确的TypeScript定义

---

## ⚙️ 配置参数

### 前端配置 (可选)

如果需要自定义提前收租天数:

```typescript
const { setAdvanceRentDays } = useOverdueManagementSimple()

// 从 localStorage 读取配置
const savedDays = localStorage.getItem('advance_rent_days')
if (savedDays) {
  setAdvanceRentDays(Number(savedDays))
}
```

### 后端参数

```python
@router.get("/overdue-rooms")
async def get_overdue_rooms(
    advance_rent_days: int = 0,  # 可配置
    ...
):
```

---

## 🧪 测试清单

### 功能测试
- [ ] 逾期房间列表正确显示
- [ ] 即将到期房间列表正确显示
- [ ] 逾期天数计算准确
- [ ] 欠费金额(房租+水电)正确
- [ ] 排序正确(逾期按天数降序,即将到期按天数升序)

### 边界情况
- [ ] 租期未开始的房间不显示
- [ ] 本月已支付的房间不显示
- [ ] 特殊房间豁免生效
- [ ] 历史数据 cutoff_date 生效

### 性能测试
- [ ] API响应时间 < 500ms (100个房间)
- [ ] 页面加载流畅,无卡顿
- [ ] 刷新数据时显示loading状态

---

## 📝 注意事项

### 1. 兼容性

**保持向后兼容**: 旧的 `useOverdueManagement.ts` 暂时保留,逐步迁移。

```typescript
// 可以并行使用一段时间
// import { useOverdueManagement } from '@/composables/useOverdueManagement'  // 旧
import { useOverdueManagementSimple } from '@/composables/useOverdueManagementSimple'  // 新
```

### 2. 数据刷新时机

需要在以下时机调用 `refresh()`:

```typescript
// 1. 支付成功后
const onPaymentSuccess = () => {
  refresh()  // 刷新逾期列表
}

// 2. 录入水电后
const onReadingSuccess = () => {
  refresh()
}

// 3. 修改房间信息后
const onRoomUpdate = () => {
  refresh()
}
```

### 3. 错误处理

```typescript
const loadOverdueRooms = async () => {
  try {
    const response = await remindersApi.getOverdueRooms()
    // ...
  } catch (error) {
    // 网络错误
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 401) {
        // 未授权,跳转登录
        router.push('/login')
      } else {
        ElMessage.error('加载失败,请检查网络连接')
      }
    } else {
      ElMessage.error('未知错误')
    }
  }
}
```

### 4. 缓存优化 (可选)

如果数据变化不频繁,可以添加缓存:

```typescript
const CACHE_KEY = 'overdue_rooms_cache'
const CACHE_DURATION = 5 * 60 * 1000  // 5分钟

const loadOverdueRooms = async () => {
  // 检查缓存
  const cached = localStorage.getItem(CACHE_KEY)
  if (cached) {
    const { data, timestamp } = JSON.parse(cached)
    if (Date.now() - timestamp < CACHE_DURATION) {
      overdueRooms.value = data.overdue
      expiringRooms.value = data.expiring
      return
    }
  }
  
  // 从API加载
  const response = await remindersApi.getOverdueRooms()
  
  // 保存缓存
  localStorage.setItem(CACHE_KEY, JSON.stringify({
    data: response.data,
    timestamp: Date.now(),
  }))
}
```

---

## 🚀 后续优化建议

### 1. WebSocket 实时更新 (高级)

如果有多人同时操作,可以考虑WebSocket推送更新:

```typescript
// 伪代码
const ws = new WebSocket('ws://localhost:8000/ws/overdue-updates')
ws.onmessage = (event) => {
  const update = JSON.parse(event.data)
  if (update.type === 'payment_completed') {
    refresh()  // 自动刷新
  }
}
```

### 2. 增量更新

只更新变化的房间,而非全量刷新:

```python
# 后端返回增量数据
{
  "updated_rooms": [...],  # 变化的房间
  "timestamp": 1234567890
}
```

### 3. 分页支持

如果房间数量很多(>500),考虑分页:

```typescript
getOverdueRooms: (params?: {
  advance_rent_days?: number
  page?: number
  size?: number
}) => ...
```

---

## 📚 相关文档

- [逾期逻辑统一说明](./OVERDUE_LOGIC_UNIFIED.md)
- [后端 API 文档](../../docs/design/api-endpoints.md)
- [前端架构说明](../../README.md)

---

## ✅ 迁移完成检查

- [x] 后端新增 `/api/v1/reminders/overdue-rooms` API
- [x] 前端创建 `reminders.ts` API封装
- [x] 前端创建 `useOverdueManagementSimple.ts` composable
- [ ] 更新 `UtilityView.vue` 使用新的 composable
- [ ] 测试所有功能正常
- [ ] 删除旧的 `useOverdueManagement.ts` (确认无其他引用后)
- [ ] 更新文档

---

**最后更新**: 2026-06-23  
**版本**: v1.0 (简化方案)
