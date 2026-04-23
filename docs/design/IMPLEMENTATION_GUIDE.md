# 统一数据模型 - 实施指南

## 文档概述

本文档提供了统一前后端数据模型的完整设计方案和实施指南。

**设计文档：**
1. [统一数据模型设计](./unified-data-model.md) - 完整的数据模型定义
2. [业务逻辑说明](./business-logic.md) - 房租计算、水电费计算等业务规则
3. [API 端点清单](./api-endpoints.md) - 所有需要的 API 端点

**代码文件：**
1. `backend/app/models.py` - 更新后的 SQLAlchemy 模型
2. `frontend/src/types/index.ts` - 更新后的 TypeScript 类型定义

**迁移脚本：**
1. `backend/migrations/migrate_to_v2.sql` - SQL 迁移脚本
2. `backend/migrations/migrate_to_v2.py` - Python 迁移脚本（推荐）

---

## 主要变更

### 1. Room 模型变更

**字段重命名：**
- `name` → `room_number`（更语义化）

**新增字段：**
- `building` - 楼栋号
- `floor` - 楼层
- `area` - 面积
- `deposit_amount` - 押金金额
- `status` - 房间状态（available/occupied/maintenance）
- `description` - 房间描述
- `updated_at` - 更新时间

**保留字段：**
- `monthly_rent` - 月租金
- `payment_cycle` - 支付周期（月数）
- `tenant_name` - 租客姓名
- `tenant_phone` - 租客电话
- `lease_start`, `lease_end` - 租约日期
- `last_payment_date` - 最后交租日期

### 2. Payment 模型变更

**新增字段：**
- `payment_type` - 支付类型（rent/deposit/utility/other）
- `due_date` - 应付日期
- `status` - 状态（pending/completed/overdue/cancelled）
- `updated_at` - 更新时间

**字段重命名：**
- `note` → `description`

### 3. UtilityReading 模型变更

**新增字段（冗余存储）：**
- `previous_reading` - 上次读数
- `usage` - 用量
- `amount` - 费用
- `rate_used` - 使用的费率
- `recorded_by` - 记录人ID（外键）
- `updated_at` - 更新时间

**字段重命名：**
- `note` → `notes`
- `utility_type` 扩展支持 `gas`（燃气）

### 4. UtilityRate 模型变更

**字段重命名：**
- `unit_price` → `rate_per_unit`（更语义化）

**新增字段：**
- `is_active` - 是否激活（软删除）
- `description` - 描述
- `updated_at` - 更新时间

**支持类型：**
- `water`（水费）
- `electricity`（电费）
- `gas`（燃气）

### 5. User 模型变更

**新增字段：**
- `full_name` - 全名
- `role` - 角色（admin/landlord/tenant）
- `is_active` - 是否激活
- `updated_at` - 更新时间

---

## 业务逻辑

### 房租计算
```
应付租金 = monthly_rent × payment_cycle
```

### 水电费计算
```
用量 = current_reading - previous_reading
费用 = 用量 × rate_per_unit
```

**查询逻辑：**
- 上次读数：按房间+类型，倒序取最新
- 有效费率：按类型，按生效日期取最新（≤抄表日期）

---

## 数据库迁移

### 方法 1: Python 脚本（推荐）

```bash
cd backend

# 备份数据库
cp rent_management.db rent_management_backup_$(date +%Y%m%d).db

# 运行迁移脚本
python migrations/migrate_to_v2.py
```

**优点：**
- 自动检测是否已迁移
- 自动备份数据库
- 详细的进度提示
- 事务安全，失败自动回滚

### 方法 2: SQL 脚本

```bash
cd backend

# 备份数据库
cp rent_management.db rent_management_backup_$(date +%Y%m%d).db

# 运行 SQL 脚本
sqlite3 rent_management.db < migrations/migrate_to_v2.sql
```

**注意：** SQL 脚本需要手动检查每一步的结果。

### 方法 3: 删除重建（仅开发环境）

```python
from app.database import create_tables

# 删除所有表并重建（⚠️ 会丢失所有数据！）
# Base.metadata.drop_all(bind=engine)
create_tables()
```

**⚠️ 警告：** 此方法会删除所有数据，仅适用于开发环境！

---

## 验证迁移结果

### 检查表结构
```bash
sqlite3 rent_management.db ".schema rooms"
sqlite3 rent_management.db ".schema payments"
sqlite3 rent_management.db ".schema utility_readings"
```

### 检查数据完整性
```sql
-- 检查房间数
SELECT COUNT(*) FROM rooms;

-- 检查支付记录数
SELECT COUNT(*) FROM payments;

-- 检查抄表记录数
SELECT COUNT(*) FROM utility_readings;

-- 检查费率数据
SELECT * FROM utility_rates;
```

---

## API 端点实施

### 需要创建的路由文件

```
backend/app/api/
├── __init__.py
├── auth.py          # ✅ 已存在
├── rooms.py         # ⚠️ 需要创建
├── payments.py      # ⚠️ 需要创建
├── utilities.py     # ⚠️ 需要创建
├── users.py         # ⚠️ 需要创建
└── stats.py         # ⚠️ 需要创建（统计）
```

### 路由注册（main.py）

```python
from app.api import auth_router, rooms_router, payments_router, utilities_router

app.include_router(auth_router)
app.include_router(rooms_router)
app.include_router(payments_router)
app.include_router(utilities_router)
```

---

## 前端更新

### 类型定义已更新

`frontend/src/types/index.ts` 已统一为：

- ✅ Room - 统一字段
- ✅ Payment - 新增 payment_type, status 等
- ✅ UtilityReading - 新增冗余字段
- ✅ UtilityRate - 重命名字段
- ✅ User - 新增 role 字段

### API 客户端已存在

前端已有 API 客户端：
- `frontend/src/api/room.ts`
- `frontend/src/api/payment.ts`
- `frontend/src/api/utility.ts`

**注意：** 这些 API 客户端与后端端点匹配，无需修改。

---

## 后续开发任务

### 优先级 1（核心功能）

1. **创建 Rooms API** (`backend/app/api/rooms.py`)
   - CRUD 操作
   - 分页、搜索、筛选
   - 获取房间的支付记录和抄表记录

2. **创建 Payments API** (`backend/app/api/payments.py`)
   - CRUD 操作
   - 自动计算租金（monthly_rent × payment_cycle）
   - 逾期状态判断

3. **创建 Utilities API** (`backend/app/api/utilities.py`)
   - 抄表记录 CRUD
   - 费率管理 CRUD
   - 自动计算水电费

### 优先级 2（增强功能）

4. **创建 Users API** (`backend/app/api/users.py`)
   - 用户管理
   - 角色权限控制

5. **创建 Statistics API** (`backend/app/api/stats.py`)
   - 房间统计（出租率）
   - 收入统计
   - 逾期提醒
   - 租约到期提醒

### 优先级 3（优化）

6. **权限控制中间件**
   - 基于 JWT 的角色验证
   - 数据过滤（tenant 只看自己的房间）

7. **单元测试**
   - 测试业务逻辑
   - 测试 API 端点

8. **前端页面**
   - 房间管理页面
   - 支付记录页面
   - 水电抄表页面
   - 统计报表页面

---

## 常见问题

### Q1: 迁移失败怎么办？

**A:** Python 脚本会自动创建备份。如果迁移失败：
```bash
# 恢复备份
cp rent_management_backup_YYYYMMDD.db rent_management.db
```

### Q2: 如何重置数据库？

**A:** 开发环境可以删除重建：
```bash
rm rent_management.db
python -c "from app.database import create_tables; create_tables()"
```

### Q3: 如何添加新的水电类型？

**A:** 修改模型和约束，然后运行迁移：
1. 添加新类型到枚举
2. 更新数据库约束
3. 添加默认费率

### Q4: 前端需要修改吗？

**A:** 类型定义已更新，API 客户端无需修改。只需确保页面组件使用新字段名（如 `room_number` 而非 `name`）。

---

## 联系与支持

如有问题或建议，请查阅相关设计文档或联系开发团队。

**最后更新：** 2024-01-01
**版本：** v2.0
