# 业务逻辑说明文档

## 1. 房租计算逻辑

### 1.1 计算公式

```
应付租金 = monthly_rent × payment_cycle
```

### 1.2 参数说明
- **monthly_rent**: 月租金（Room.monthly_rent）
- **payment_cycle**: 支付周期，单位为月（Room.payment_cycle）
  - 1 = 按月付
  - 3 = 按季度付
  - 6 = 按半年付
  - 12 = 按年付

### 1.3 示例
- 月租金 1000元，按月付：1000 × 1 = 1000元
- 月租金 1000元，按季度付：1000 × 3 = 3000元
- 月租金 1000元，按年付：1000 × 12 = 12000元

### 1.4 实现位置
- **后端**: API 创建支付记录时自动计算
- **前端**: 显示预览金额，但不依赖前端计算

---

## 2. 水电费计算逻辑

### 2.1 计算公式

```
用量 = current_reading - previous_reading
费用 = 用量 × rate_per_unit
```

### 2.2 参数说明
- **current_reading**: 本次读数（UtilityReading.reading）
- **previous_reading**: 上次读数（查询同房间+同类型的最新记录）
- **rate_per_unit**: 费率（查询 UtilityRate，按 reading_date 取生效日期≤reading_date的最新费率）

### 2.3 计算流程

#### 步骤 1: 获取上次读数
```sql
SELECT reading, reading_date
FROM utility_readings
WHERE room_id = ? AND utility_type = ?
  AND reading_date < ?
ORDER BY reading_date DESC
LIMIT 1
```

#### 步骤 2: 获取有效费率
```sql
SELECT rate_per_unit
FROM utility_rates
WHERE utility_type = ?
  AND effective_date <= ?
  AND is_active = true
ORDER BY effective_date DESC
LIMIT 1
```

#### 步骤 3: 计算并保存
- 计算 `usage = current_reading - previous_reading`
- 计算 `amount = usage × rate_per_unit`
- 保存时冗余存储 `previous_reading, usage, amount, rate_used`

### 2.4 边界情况处理

#### 情况 1: 无上次读数（首次抄表）
- **处理**: `previous_reading = 0`
- **结果**: `usage = current_reading - 0 = current_reading`

#### 情况 2: 当前读数 < 上次读数（异常情况）
- **可能原因**:
  - 换表
  - 读数错误
  - 表反转
- **处理**: 抛出异常，要求人工确认
- **错误信息**: "当前读数不能小于上次读数"

#### 情况 3: 无有效费率
- **处理**: 抛出异常
- **错误信息**: "未找到有效的水电费率"

### 2.5 默认费率

#### 系统初始化费率
- **水费**: 5.0 元/吨
- **电费**: 1.0 元/度
- **燃气费**: 暂未设置

这些默认费率在数据库迁移时自动创建，如果费率表为空。

### 2.6 费率管理

#### 修改费率
- 通过 API 创建新的费率记录（新的 `effective_date`）
- 系统自动选择生效日期 ≤ 查询日期的最新费率
- 支持未来费率预设置（例如：下月1日起调价）

#### 费率变更示例
```python
# 当前费率（2026-01-01 生效）
water_rate = 5.0  # 元/吨

# 修改费率（2026-02-01 起生效）
POST /api/v1/utility-rates
{
    "utility_type": "water",
    "rate_per_unit": 5.5,
    "effective_date": "2026-02-01",
    "description": "2月份起水费调整"
}

# 系统行为：
# - 2026-01-31 的记录仍使用 5.0 元/吨
# - 2026-02-01 及之后的记录使用 5.5 元/吨
```

### 2.7 示例
- 上次读数: 100
- 本次读数: 150
- 费率: 0.5 元/单位
- 用量: 150 - 100 = 50
- 费用: 50 × 0.5 = 25元

---

## 3. 支付状态管理

### 3.1 状态枚举
- **pending**: 待支付
- **completed**: 已完成
- **overdue**: 逾期
- **cancelled**: 已取消

### 3.2 状态转换规则

```
pending → completed  (支付完成)
pending → overdue    (超过 due_date 且未支付)
pending → cancelled  (取消支付)
overdue → completed  (逾期后支付)
completed → (不可变更)
cancelled → (不可变更)
```

### 3.3 自动判断逾期
- **触发时机**: 查询支付记录时
- **判断逻辑**:
  ```
  IF status == 'pending' AND due_date < TODAY:
      status = 'overdue'
  ```
- **实现**: 后端查询时动态计算，或定时任务更新

---

## 4. 房间状态管理

### 4.1 状态枚举
- **available**: 空置
- **occupied**: 已租出
- **maintenance**: 维修中

### 4.2 状态转换规则

```
available → occupied  (签订租约，设置tenant_name)
available → maintenance (开始维修)
maintenance → available (维修完成)
occupied → available   (租约到期，无新租客)
occupied → maintenance (租期内维修)
```

### 4.3 自动更新规则
- **创建租约**: 设置 `tenant_name` 时，自动变更为 `occupied`
- **清空租约**: 清空 `tenant_name` 时，自动变更为 `available`
- **手动维护**: 管理员手动设置

---

## 5. 租约到期提醒

### 5.1 触发条件
- `lease_end` 距离今天 ≤ 30 天

### 5.2 提醒级别
- **30天**: 正常提醒
- **7天**: 重要提醒
- **0天** (已到期): 紧急提醒

### 5.3 实现方式
- **前端**: 房间列表页显示标记
- **后端**: 定时任务发送通知（邮件/短信）

---

## 6. 费率管理规则

### 6.1 费率生效规则
- 同一类型（water/electricity/gas）可设置多个历史费率
- 查询时取 `effective_date ≤ reading_date` 的最新费率

### 6.2 费率变更示例
```
2024-01-01: 水费 2.0 元/吨
2024-07-01: 水费 2.5 元/吨
2024-12-01: 水费 3.0 元/吨

2024-06-15 抄表: 使用 2.0 元/吨
2024-08-15 抄表: 使用 2.5 元/吨
2025-01-15 抄表: 使用 3.0 元/吨
```

### 6.3 费率软删除
- 不物理删除费率记录
- 设置 `is_active = false` 禁用
- 已关联的抄表记录不受影响（因为冗余存储了 `rate_used`）

---

## 7. 数据完整性约束

### 7.1 删除级联
- **删除 Room**: 级联删除其 Payment 和 UtilityReading
- **删除 UtilityRate**: 不影响已使用的 UtilityReading（冗余存储）
- **删除 User**: 不允许删除（或设置为 is_active=false）

### 7.2 修改限制
- **UtilityReading**: 不允许修改（或仅允许备注字段）
- **Payment**: 已完成的不允许修改金额和日期

---

## 8. 业务规则总结

### 8.1 强制规则（数据库约束）
1. lease_end > lease_start
2. room_number 唯一
3. tenant_phone 格式正确
4. utility_type 只能是 water/electricity/gas
5. payment_cycle > 0

### 8.2 业务规则（应用层验证）
1. 当前读数 ≥ 上次读数
2. 必须有有效费率才能抄表
3. 租约开始/结束日期必须合理
4. 支付金额必须 > 0
5. 不能删除已使用的费率（设置 is_active=false）

### 8.3 计算规则
1. 房租 = monthly_rent × payment_cycle
2. 水电费 = (current_reading - previous_reading) × rate
3. 逾期判断: status=pending AND due_date < TODAY

---

## 9. API 实现建议

### 9.1 计算逻辑封装
创建 `service/business.py`:

```python
def calculate_rent(monthly_rent: Decimal, payment_cycle: int) -> Decimal:
    """计算应付租金"""
    return monthly_rent * payment_cycle

def get_previous_reading(db: Session, room_id: int, utility_type: str, before_date: date) -> Optional[Decimal]:
    """获取上次读数"""
    # 查询逻辑

def get_active_rate(db: Session, utility_type: str, on_date: date) -> Optional[UtilityRate]:
    """获取有效费率"""
    # 查询逻辑

def calculate_utility_cost(current: Decimal, previous: Decimal, rate: Decimal) -> tuple[Decimal, Decimal]:
    """计算水电费用 (usage, amount)"""
    usage = current - previous
    amount = usage * rate
    return usage, amount
```

### 9.2 响应式计算
- 创建抄表时自动计算费用
- 创建租金记录时自动计算总金额
- 前端仅展示，不依赖前端计算

### 9.3 事务处理
- 抄表记录创建：
  1. 查询上次读数
  2. 查询有效费率
  3. 计算用量和费用
  4. 保存记录（包含冗余字段）
- 全部步骤在同一事务中，失败则回滚
