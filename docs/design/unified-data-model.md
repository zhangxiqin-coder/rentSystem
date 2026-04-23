# 统一数据模型设计文档

## 1. Room 模型（房间）

### 最终字段列表（合并前后端需求）

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | Integer | 是 | 主键（自增） |
| room_number | String(50) | 是 | 房间号（如"101"、"A-201"），唯一索引 |
| building | String(50) | 否 | 楼栋号（如"1号楼"、"A栋"） |
| floor | Integer | 否 | 楼层 |
| area | Decimal(10,2) | 否 | 面积（平方米） |
| monthly_rent | Decimal(10,2) | 是 | 月租金 |
| deposit_amount | Decimal(10,2) | 否 | 押金金额 |
| payment_cycle | Integer | 是 | 支付周期（月数），默认1 |
| status | String(20) | 是 | 房间状态：available/occupied/maintenance |
| tenant_name | String(100) | 否 | 租客姓名 |
| tenant_phone | String(20) | 否 | 租客电话（正则：^1[3-9]\d{9}$） |
| lease_start | Date | 否 | 租约开始日期 |
| lease_end | Date | 否 | 租约结束日期（必须 > lease_start） |
| last_payment_date | Date | 否 | 最后交租日期 |
| description | Text | 否 | 房间描述/备注 |
| created_at | DateTime | 是 | 创建时间 |
| updated_at | DateTime | 是 | 更新时间 |

### 字段说明
- **room_number**: 替代原来的 `name`，更语义化
- **building, floor, area**: 新增，方便管理大型物业
- **deposit_amount**: 新增，押金管理
- **status**: 新增，房间状态管理
- **payment_cycle**: 保留，用于计算租金总额
- **tenant_name, tenant_phone**: 保留，简单租客信息（暂不做租客关联表）
- **lease_start, lease_end**: 保留，租约管理
- **description**: 新增，用于存储额外信息

### 约束
- `room_number` 全局唯一
- `lease_end > lease_start`（数据库约束）
- `tenant_phone` 格式验证（手机号）

---

## 2. Payment 模型（支付记录）

### 最终字段列表

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | Integer | 是 | 主键（自增） |
| room_id | Integer | 是 | 外键 → rooms.id（CASCADE） |
| amount | Decimal(10,2) | 是 | 支付金额 |
| payment_type | String(20) | 是 | 支付类型：rent/deposit/utility/other |
| payment_date | Date | 是 | 支付日期 |
| due_date | Date | 否 | 应付日期 |
| status | String(20) | 是 | 状态：pending/completed/overdue/cancelled，默认completed |
| payment_method | String(50) | 否 | 支付方式：现金/银行转账/支付宝/微信支付 |
| description | Text | 否 | 描述/备注 |
| receipt_image | String(255) | 否 | 收据图片URL |
| created_at | DateTime | 是 | 创建时间 |
| updated_at | DateTime | 是 | 更新时间 |

### 字段说明
- **payment_type**: 新增，区分租金/押金/水电费/其他
- **due_date**: 新增，应付日期（用于判断overdue）
- **status**: 新增，支付状态
- **description**: 替代原来的 `note`
- 保留 `payment_method`, `receipt_image`

---

## 3. UtilityReading 模型（水电表读数）

### 最终字段列表

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | Integer | 是 | 主键（自增） |
| room_id | Integer | 是 | 外键 → rooms.id（CASCADE） |
| utility_type | String(10) | 是 | 类型：water/electricity/gas |
| reading | Decimal(10,2) | 是 | 本次读数 |
| reading_date | Date | 是 | 抄表日期 |
| previous_reading | Decimal(10,2) | 否 | 上次读数（冗余字段，便于查询） |
| usage | Decimal(10,2) | 否 | 用量 = reading - previous_reading |
| amount | Decimal(10,2) | 否 | 费用 = usage × rate（冗余字段） |
| rate_used | Decimal(10,4) | 否 | 使用的费率（冗余字段，便于追溯） |
| recorded_by | Integer | 否 | 记录人ID（外键 → users.id） |
| notes | Text | 否 | 备注 |
| created_at | DateTime | 是 | 创建时间 |
| updated_at | DateTime | 是 | 更新时间 |

### 字段说明
- **utility_type**: 扩展支持 gas（燃气）
- **previous_reading**: 冗余存储，避免每次查询都要计算
- **usage, amount, rate_used**: 冗余存储，提高查询性能
- **recorded_by**: 新增，记录操作人
- **notes**: 替代原来的 `note`

### 约束
- `utility_type IN ('water', 'electricity', 'gas')`
- 同一房间+类型+日期只能有一条记录（唯一约束）

---

## 4. UtilityRate 模型（水电费率）

### 最终字段列表

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | Integer | 是 | 主键（自增） |
| utility_type | String(10) | 是 | 类型：water/electricity/gas |
| rate_per_unit | Decimal(10,4) | 是 | 单价（元/单位） |
| effective_date | Date | 是 | 生效日期 |
| is_active | Boolean | 是 | 是否激活，默认true |
| description | Text | 否 | 描述/备注 |
| created_at | DateTime | 是 | 创建时间 |
| updated_at | DateTime | 是 | 更新时间 |

### 字段说明
- **utility_type**: 扩展支持 gas
- **rate_per_unit**: 重命名（原来是 unit_price），更语义化
- **is_active**: 新增，软删除机制
- **description**: 新增

### 默认费率
- **水费（water）**: 5.0 元/吨
- **电费（electricity）**: 1.0 元/度
- **燃气费（gas）**: 暂未设置

### 约束
- 同一类型在同一时间只能有一个激活费率
- `effective_date` 必须递增

---

## 5. User 模型（用户）

### 最终字段列表

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | Integer | 是 | 主键（自增） |
| username | String(50) | 是 | 用户名（唯一） |
| password_hash | String(255) | 是 | 密码哈希 |
| email | String(100) | 否 | 邮箱 |
| full_name | String(100) | 否 | 全名 |
| role | String(20) | 是 | 角色：admin/landlord/tenant，默认landlord |
| is_active | Boolean | 是 | 是否激活，默认true |
| created_at | DateTime | 是 | 创建时间 |
| updated_at | DateTime | 是 | 更新时间 |

### 字段说明
- **full_name**: 新增，用于显示
- **role**: 新增，角色权限控制
- **is_active**: 新增，软删除机制

---

## 数据关系图

```
User (用户)
  ├─ id
  └─ recorded_utility_readings (记录的抄表) → UtilityReading.recorded_by

Room (房间)
  ├─ id
  ├─ tenant_name (简单租客信息)
  └─ 1:N → Payment (支付记录)
      └─ 1:N → UtilityReading (抄表记录)
          └─ N:1 → User (记录人)

UtilityRate (费率)
  └─ 独立表，按类型+日期查询
```

---

## 索引设计

### Room 表
- PRIMARY KEY: id
- UNIQUE INDEX: room_number
- INDEX: status
- INDEX: tenant_name
- INDEX: lease_start, lease_end

### Payment 表
- PRIMARY KEY: id
- INDEX: room_id
- INDEX: payment_date
- INDEX: payment_type
- INDEX: status
- INDEX: (room_id, payment_date)

### UtilityReading 表
- PRIMARY KEY: id
- INDEX: room_id
- INDEX: (room_id, utility_type, reading_date) DESC
- INDEX: reading_date
- INDEX: utility_type

### UtilityRate 表
- PRIMARY KEY: id
- INDEX: (utility_type, effective_date) DESC
- INDEX: is_active

### User 表
- PRIMARY KEY: id
- UNIQUE INDEX: username
- INDEX: email
- INDEX: role
