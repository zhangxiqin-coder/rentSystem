# 统一数据模型 - 快速参考

## 📋 任务完成清单

### ✅ 已完成
- [x] 分析前后端数据模型差异
- [x] 设计统一的数据模型
- [x] 明确业务逻辑（房租计算、水电费计算）
- [x] 设计 API 端点清单
- [x] 更新后端 models.py
- [x] 更新后端 schemas.py
- [x] 更新前端 types.ts
- [x] 创建数据库迁移脚本

### ⚠️ 待实施
- [ ] 运行数据库迁移脚本
- [ ] 创建 Rooms API 路由
- [ ] 创建 Payments API 路由
- [ ] 创建 Utilities API 路由
- [ ] 创建 Users API 路由
- [ ] 创建 Statistics API 路由
- [ ] 前端页面适配新字段名

---

## 🗂️ 文件结构

### 设计文档（docs/design/）
```
unified-data-model.md      # 统一数据模型定义
business-logic.md          # 业务逻辑说明
api-endpoints.md           # API 端点清单
IMPLEMENTATION_GUIDE.md    # 实施指南（本文档）
```

### 后端代码（backend/app/）
```
models.py                  # ✅ 已更新（统一数据模型）
schemas.py                 # ✅ 已更新（Pydantic schemas）
database.py                # 无需修改
api/auth.py                # ✅ 已存在
api/rooms.py               # ⚠️ 需要创建
api/payments.py            # ⚠️ 需要创建
api/utilities.py           # ⚠️ 需要创建
api/users.py               # ⚠️ 需要创建
api/stats.py               # ⚠️ 需要创建
```

### 前端代码（frontend/src/）
```
types/index.ts             # ✅ 已更新（TypeScript 类型）
api/room.ts                # ✅ 已存在
api/payment.ts             # ✅ 已存在
api/utility.ts             # ✅ 已存在
```

### 迁移脚本（backend/migrations/）
```
migrate_to_v2.sql          # SQL 迁移脚本
migrate_to_v2.py           # Python 迁移脚本（推荐）
```

---

## 🔄 数据库迁移步骤

### 1️⃣ 备份数据库
```bash
cd backend
cp rent_management.db rent_management_backup_$(date +%Y%m%d_%H%M%S).db
```

### 2️⃣ 运行迁移（Python 脚本推荐）
```bash
python migrations/migrate_to_v2.py
```

### 3️⃣ 验证结果
```bash
sqlite3 rent_management.db ".schema rooms"
sqlite3 rent_management.db "SELECT COUNT(*) FROM rooms;"
```

---

## 📊 主要字段变更对照表

### Room 模型
| 旧字段 | 新字段 | 类型 | 说明 |
|--------|--------|------|------|
| `name` | `room_number` | String(50) | 房间号（重命名） |
| - | `building` | String(50) | 楼栋号（新增） |
| - | `floor` | Integer | 楼层（新增） |
| - | `area` | Decimal(10,2) | 面积（新增） |
| - | `deposit_amount` | Decimal(10,2) | 押金（新增） |
| - | `status` | String(20) | 状态（新增） |
| - | `description` | Text | 描述（新增） |
| - | `updated_at` | DateTime | 更新时间（新增） |

### Payment 模型
| 旧字段 | 新字段 | 类型 | 说明 |
|--------|--------|------|------|
| - | `payment_type` | String(20) | 支付类型（新增） |
| - | `due_date` | Date | 应付日期（新增） |
| - | `status` | String(20) | 状态（新增） |
| - | `updated_at` | DateTime | 更新时间（新增） |
| `note` | `description` | Text | 备注（重命名） |

### UtilityReading 模型
| 旧字段 | 新字段 | 类型 | 说明 |
|--------|--------|------|------|
| - | `previous_reading` | Decimal(10,2) | 上次读数（新增） |
| - | `usage` | Decimal(10,2) | 用量（新增） |
| - | `amount` | Decimal(10,2) | 费用（新增） |
| - | `rate_used` | Decimal(10,4) | 使用费率（新增） |
| - | `recorded_by` | Integer | 记录人（新增） |
| - | `updated_at` | DateTime | 更新时间（新增） |
| `note` | `notes` | Text | 备注（重命名） |

### UtilityRate 模型
| 旧字段 | 新字段 | 类型 | 说明 |
|--------|--------|------|------|
| `unit_price` | `rate_per_unit` | Decimal(10,4) | 单价（重命名） |
| - | `is_active` | Boolean | 是否激活（新增） |
| - | `description` | Text | 描述（新增） |
| - | `updated_at` | DateTime | 更新时间（新增） |

### User 模型
| 旧字段 | 新字段 | 类型 | 说明 |
|--------|--------|------|------|
| - | `full_name` | String(100) | 全名（新增） |
| - | `role` | String(20) | 角色（新增） |
| - | `is_active` | Boolean | 是否激活（新增） |
| - | `updated_at` | DateTime | 更新时间（新增） |

---

## 💡 核心业务逻辑

### 房租计算
```
应付租金 = monthly_rent × payment_cycle
```
- `payment_cycle`: 1=按月, 3=按季度, 6=按半年, 12=按年

### 水电费计算
```
用量 = current_reading - previous_reading
费用 = 用量 × rate_per_unit
```

**查询逻辑：**
- 上次读数：`SELECT * FROM utility_readings WHERE room_id=? AND utility_type=? AND reading_date < ? ORDER BY reading_date DESC LIMIT 1`
- 有效费率：`SELECT * FROM utility_rates WHERE utility_type=? AND effective_date <= ? AND is_active=true ORDER BY effective_date DESC LIMIT 1`

---

## 🔌 关键 API 端点

### 房间管理
- `GET /api/v1/rooms` - 获取房间列表（分页、搜索、筛选）
- `POST /api/v1/rooms` - 创建房间
- `PUT /api/v1/rooms/{id}` - 更新房间
- `DELETE /api/v1/rooms/{id}` - 删除房间

### 支付管理
- `GET /api/v1/payments` - 获取支付列表
- `POST /api/v1/payments` - 创建支付（自动计算租金）
- `GET /api/v1/rooms/{id}/payments` - 获取房间支付记录

### 水电管理
- `GET /api/v1/utility/readings` - 获取抄表列表
- `POST /api/v1/utility/readings` - 创建抄表（自动计算费用）
- `GET /api/v1/utility/rates` - 获取费率列表
- `POST /api/v1/utility/rates` - 创建费率

**完整端点清单见：** [api-endpoints.md](./api-endpoints.md)

---

## ⚙️ 权限控制

### 角色定义
- **admin**: 系统管理员，所有权限
- **landlord**: 房东，管理房间和租金
- **tenant**: 租客，只读查看自己相关信息

### 权限矩阵
| 操作 | admin | landlord | tenant |
|------|-------|----------|--------|
| 房间 CRUD | ✓ | ✓ | ✗ |
| 支付 CRUD | ✓ | ✓ | ✗ |
| 抄表 CRUD | ✓ | ✓ | ✗ |
| 费率 CRUD | ✓ | ✓ | ✗ |
| 用户管理 | ✓ | ✗ | ✗ |
| 查看数据 | ✓ | ✓ | 仅自己 |

---

## 🐛 常见问题

### Q: 迁移失败怎么办？
```bash
# 恢复备份
cp rent_management_backup_YYYYMMDD_HHMMSS.db rent_management.db
```

### Q: 如何检查迁移是否成功？
```bash
sqlite3 rent_management.db "SELECT COUNT(*) FROM rooms;"
sqlite3 rent_management.db ".schema rooms"
```

### Q: 前端需要修改吗？
类型定义已更新，API 客户端无需修改。只需确保页面使用新字段名：
- `room_number` 而非 `name`
- `payment_type`, `status` 等新字段

---

## 📚 相关文档

- [统一数据模型设计](./unified-data-model.md) - 完整的字段定义
- [业务逻辑说明](./business-logic.md) - 计算逻辑和查询规则
- [API 端点清单](./api-endpoints.md) - 所有 API 端点

---

## 🎯 下一步

1. ✅ 审查本设计文档
2. ⚠️ 运行数据库迁移脚本
3. ⚠️ 创建后端 API 路由（Rooms, Payments, Utilities）
4. ⚠️ 前端页面适配新字段名
5. ⚠️ 测试完整流程

---

**文档版本:** v2.0
**最后更新:** 2024-01-01
**负责人:** Backend Team
