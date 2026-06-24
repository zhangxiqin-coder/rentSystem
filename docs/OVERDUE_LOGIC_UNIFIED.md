# 逾期判断逻辑统一说明

## 📋 概述

本文档说明了租房管理系统中**未交房租逾期判断**的统一逻辑,确保前后端使用相同的计算规则。

---

## 🎯 核心原则

### 1. 统一的计算函数

**后端**: `get_payment_due_context(db, room)` in [reminders.py](file:///d:/codespace/rentSystem_repo/backend/app/api/reminders.py)  
**前端**: `getPaymentDueContext(room)` in [useOverdueManagement.ts](file:///d:/codespace/rentSystem_repo/frontend/src/composables/useOverdueManagement.ts)

两个函数实现完全相同的逻辑,确保判断结果一致。

### 2. 关键概念

- **锚点日期 (Anchor Date)**: 计算应交日期的起点,优先使用 `lease_start`,其次 `last_payment_date`
- **付款周期 (Payment Cycle)**: 月付=1, 季付=3, 半年付=6
- **应交日 (Due Date)**: 每个周期的租金应交日期
- **目标日期 (Target Due)**: 当前需要关注的收租日期(可能是当前周期或下一周期)
- **距离天数 (Days to Due)**: 距离目标日期的天数
  - **正数**: 还未到期
  - **0**: 当天到期
  - **负数**: 已逾期

---

## 🔧 核心算法

### 步骤 1: 确定锚点和应交日

```python
anchor_source = room.lease_start or room.last_payment_date
due_day = anchor_source.day  # 例如: 每月5号交租
```

### 步骤 2: 推算所有应交日期

从锚点开始,按付款周期递增,直到超过今天:

```python
cursor = build_due_date(anchor_year, anchor_month, due_day)
while cursor <= today:
    previous_due = cursor
    cursor = add_months_by_due_day(cursor, cycle_months, due_day)
```

**示例**:
- 锚点: 2024-01-05 (lease_start)
- 周期: 3个月 (季付)
- 推算: 2024-01-05 → 2024-04-05 → 2024-07-05 → 2024-10-05 → ...

### 步骤 3: 判断当前周期是否已支付

满足以下**任一条件**即视为已支付:

1. **近期有支付记录**: 
   ```python
   has_recent_rent_payment(room_id, cycle_months)
   # 阈值 = cycle_months * 30 - 5
   # 月付: 25天, 季付: 85天
   ```

2. **last_payment_date 在窗口期内**:
   ```python
   abs(last_paid - current_cycle_due) <= 14天
   ```

3. **租赁记录中有支付**:
   - 如果有上一个周期(prev_prev_due),检查在其后是否有支付
   - 否则检查是否有任何支付记录

4. **特殊豁免** (历史数据):
   ```python
   room_number != '502-2' and current_cycle_due < cutoff_date
   ```

### 步骤 4: 确定目标日期和距离天数

```python
if paid_current_cycle:
    target_due = next_due  # 当前周期已付,关注下一周期
else:
    target_due = current_cycle_due  # 当前周期未付,这就是目标

days_to_due = (target_due - today).days
```

---

## 📊 逾期判定规则

### 后端 API (`/api/v1/reminders/upcoming`)

```python
# 跳过租期未开始的房间
if room.lease_start > today:
    continue

# 获取上下文
due_context = get_payment_due_context(db, room)
days_to_due = due_context['days_to_due']
paid_current_cycle = due_context['paid_current_cycle']

# 已支付的房间不生成提醒
if paid_current_cycle:
    continue

# 判定逻辑
if days_to_due < 0:
    # 已逾期
    type = "payment_overdue"
    overdue_days = -days_to_due
    
elif days_to_due <= advance_rent_days:
    # 在提前收租范围内 (默认0,即到期当天)
    type = "payment_due"
    
elif 0 <= days_to_due <= days_ahead:
    # 即将到期 (默认7天内)
    type = "payment_due"
```

### 前端 Composable (`useOverdueManagement.ts`)

```typescript
// 逾期房间列表
overdueRooms = allRooms.filter(room => {
  if (room.status !== 'occupied') return false
  if (hasPaidThisMonth(room)) return false
  if (hasRecentRentPayment(room.id)) return false
  if (lease_start > today) return false
  
  const { daysToDue } = getPaymentDueContext(room)
  
  // 如果距离应交日 <= 提前收租天数,计入欠租
  if (daysToDue <= advanceRentDays.value) {
    const overdueDays = Math.max(0, -daysToDue)
    return true
  }
})

// 即将到期房间列表
expiringRooms = allRooms.filter(room => {
  const days = getNextPaymentDays(room)
  return days > advanceRentDays.value && days <= expiringDays.value
})
```

---

## 💰 欠费金额计算

```python
cycle = room.payment_cycle or 1
rent_due = room.monthly_rent * cycle

# 获取最近未支付的水电费
utility_amount = get_latest_unpaid_utility_amount(room_id)

total_overdue = rent_due + utility_amount
```

---

## ⚙️ 配置参数

### 前端配置 ([useOverdueConfig.ts](file:///d:/codespace/rentSystem_repo/frontend/src/composables/useOverdueConfig.ts))

```typescript
overdueCutoffDate: '2026-04-22'  // 逾期截止日期(历史数据豁免)
advanceRentDays: 0                // 提前几天开始催租(0=到期当天)
expiringDays: 7                   // 即将到期的天数范围
recentPaymentDays: 7              // 近期支付的天数范围
recentReadingDays: 45             // 近期抄表的天数范围
```

### 后端参数

```python
@router.get("/upcoming")
async def get_upcoming_reminders(
    days_ahead: int = 7,           # 提前几天提醒
    include_overdue: bool = True,  # 是否包含逾期
    advance_rent_days: int = 0,    # 提前收租天数
    ...
):
```

---

## 🔍 示例场景

### 场景 1: 正常月付,已逾期

```
房间: 101
月租: 1000元
周期: 1个月
lease_start: 2024-01-05
last_payment_date: 2024-03-05
today: 2024-05-10

推算应交日期:
- 2024-01-05 (第1期)
- 2024-02-05 (第2期)
- 2024-03-05 (第3期, 已支付 ✓)
- 2024-04-05 (第4期, 未支付) ← current_cycle_due
- 2024-05-05 (第5期) ← next_due

判断:
- paid_current_cycle = False (4月5日至今已超过25天)
- target_due = 2024-04-05
- days_to_due = (2024-04-05 - 2024-05-10).days = -35

结果: 已逾期35天,欠费1000元
```

### 场景 2: 季付,即将到期

```
房间: 202
月租: 1500元
周期: 3个月
lease_start: 2024-01-10
last_payment_date: 2024-04-10
today: 2024-07-05

推算应交日期:
- 2024-01-10 (第1期)
- 2024-04-10 (第2期, 已支付 ✓)
- 2024-07-10 (第3期) ← current_cycle_due & target_due
- 2024-10-10 (第4期) ← next_due

判断:
- paid_current_cycle = False (7月10日还未到)
- target_due = 2024-07-10
- days_to_due = (2024-07-10 - 2024-07-05).days = 5

结果: 5天后到期,应付4500元 (1500×3)
```

### 场景 3: 刚支付,不算逾期

```
房间: 303
月租: 1200元
周期: 1个月
lease_start: 2024-01-15
last_payment_date: 2024-05-18
today: 2024-05-20

推算应交日期:
- 2024-05-15 (本期) ← current_cycle_due
- 2024-06-15 (下期) ← next_due

判断:
- has_recent_rent_payment() = True (5月18日在25天窗口内)
- paid_current_cycle = True
- target_due = 2024-06-15
- days_to_due = 26

结果: 本月已支付,不计入逾期或即将到期
```

---

## ⚠️ 注意事项

### 1. last_payment_date 的更新时机

**重要**: 每次成功收款后,必须更新房间的 `last_payment_date` 字段,否则会导致误判。

```python
# 在支付成功后
room.last_payment_date = date.today()
db.commit()
```

### 2. 月末日期处理

如果锚点是31号,但某些月份只有30天或28天:

```python
def build_due_date(year, month, day):
    days_in_month = calendar.monthrange(year, month)[1]
    actual_day = min(day, days_in_month)  # 自动调整
    return date(year, month, actual_day)
```

**示例**:
- 锚点: 1月31日
- 2月应交日: 2月28日 (或29日)
- 3月应交日: 3月31日

### 3. 历史数据豁免

对于导入的历史数据,可能没有完整的支付记录。使用 `overdueCutoffDate` 进行豁免:

```python
if current_cycle_due < date(2026, 4, 22):
    paid_current_cycle = True  # 视为已支付
```

### 4. 特殊房间标记

硬编码的房间号豁免不够灵活,建议改为:

```python
# TODO: 从数据库读取豁免配置
exempt_rooms = db.query(RoomExemption).filter(...).all()
if room.id in exempt_rooms:
    paid_current_cycle = True
```

---

## 🔄 前后端同步

### 保持一致的关键点

1. ✅ 使用相同的锚点选择逻辑 (`lease_start` > `last_payment_date`)
2. ✅ 使用相同的周期递增算法
3. ✅ 使用相同的"已支付"判断条件
4. ✅ 使用相同的日期边界处理 (build_due_date)
5. ✅ 使用相同的距离天数计算公式

### 差异说明

| 项目 | 后端 | 前端 |
|------|------|------|
| 数据源 | 数据库查询 | Pinia Store |
| 支付方式检查 | Payment 表 | payments.value |
| 水电费获取 | UtilityReading 表 | mergedReadings |
| 配置读取 | 函数参数 | localStorage |

尽管数据源不同,但**核心算法完全一致**,确保判断结果相同。

---

## 📝 待优化项

1. **TODO**: 拆分水电费明细 (目前合并显示)
2. **TODO**: 配置化特殊房间豁免 (替代硬编码)
3. **TODO**: 配置化逾期截止日期 (从环境变量读取)
4. **TODO**: 添加单元测试验证前后端逻辑一致性
5. **TODO**: 优化性能 (缓存 due_context 计算结果)

---

## 🧪 测试建议

### 单元测试用例

```python
def test_overdue_calculation():
    # 测试各种场景
    scenarios = [
        {"cycle": 1, "days_since_due": -5, "expected": "overdue"},
        {"cycle": 1, "days_since_due": 0, "expected": "due_today"},
        {"cycle": 1, "days_since_due": 3, "expected": "upcoming"},
        {"cycle": 3, "days_since_due": -10, "expected": "overdue"},
        # ...
    ]
    
    for scenario in scenarios:
        result = get_payment_due_context(...)
        assert result['days_to_due'] == scenario['days_since_due']
```

### 集成测试

1. 创建测试房间和支付记录
2. 调用后端 API 获取提醒列表
3. 前端加载相同数据
4. 对比前后端的逾期房间列表是否一致

---

## 📚 相关代码文件

- 后端逻辑: [backend/app/api/reminders.py](file:///d:/codespace/rentSystem_repo/backend/app/api/reminders.py)
- 前端逻辑: [frontend/src/composables/useOverdueManagement.ts](file:///d:/codespace/rentSystem_repo/frontend/src/composables/useOverdueManagement.ts)
- 配置管理: [frontend/src/composables/useOverdueConfig.ts](file:///d:/codespace/rentSystem_repo/frontend/src/composables/useOverdueConfig.ts)
- 业务服务: [backend/app/service/business.py](file:///d:/codespace/rentSystem_repo/backend/app/service/business.py)

---

**最后更新**: 2026-06-23  
**版本**: v2.0 (统一逻辑)
