# API 端点清单

## 版本说明
- API 版本: v1
- 基础路径: `/api/v1`
- 认证方式: Bearer Token (JWT)
- 响应格式: JSON

---

## 通用响应格式

### 成功响应
```json
{
  "code": 200,
  "message": "操作成功",
  "data": { ... }
}
```

### 列表响应
```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "items": [ ... ],
    "total": 100,
    "page": 1,
    "size": 10
  }
}
```

### 错误响应
```json
{
  "detail": "错误描述",
  "error_code": "ERROR_001",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

---

## 认证相关 (Authentication)

| 端点 | 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|------|
| 用户注册 | POST | `/api/v1/auth/register` | 否 | 创建新用户 |
| 用户登录 | POST | `/api/v1/auth/login` | 否 | 获取 access_token |
| 获取当前用户 | GET | `/api/v1/auth/me` | 是 | 获取登录用户信息 |
| 修改密码 | POST | `/api/v1/auth/change-password` | 是 | 修改当前用户密码 |
| 刷新令牌 | POST | `/api/v1/auth/refresh-token` | 是 | 获取新的 access_token |
| 用户登出 | POST | `/api/v1/auth/logout` | 是 | 客户端删除 token |
| CSRF令牌 | GET | `/api/v1/auth/csrf-token` | 否 | 获取 CSRF Token |

### 权限说明
- 所有修改操作（POST/PUT/DELETE）需要 CSRF Token
- 登录/注册不需要认证

---

## 房间管理 (Rooms)

| 端点 | 方法 | 路径 | 认证 | 权限 | 说明 |
|------|------|------|------|------|------|
| 获取房间列表 | GET | `/api/v1/rooms` | 是 | all | 支持分页、搜索、筛选 |
| 获取房间详情 | GET | `/api/v1/rooms/{id}` | 是 | all | 获取单个房间信息 |
| 创建房间 | POST | `/api/v1/rooms` | 是 | admin/landlord | 创建新房间 |
| 更新房间 | PUT | `/api/v1/rooms/{id}` | 是 | admin/landlord | 更新房间信息 |
| 删除房间 | DELETE | `/api/v1/rooms/{id}` | 是 | admin/landlord | 删除房间（级联） |
| 获取房间支付记录 | GET | `/api/v1/rooms/{id}/payments` | 是 | all | 获取该房间的所有支付 |
| 获取房间抄表记录 | GET | `/api/v1/rooms/{id}/utility-readings` | 是 | all | 获取该房间的所有抄表 |

### 查询参数（列表）
- `page`: 页码（默认1）
- `size`: 每页数量（默认10，最大50）
- `search`: 搜索关键字（房间号、租客姓名）
- `status`: 状态筛选（available/occupied/maintenance）
- `building`: 楼栋筛选
- `floor`: 楼层筛选
- `sort_by`: 排序字段（room_number/created_at/monthly_rent）
- `order`: 排序方向（asc/desc）

### 权限说明
- **admin**: 所有操作
- **landlord**: 所有操作（自己管理的房间）
- **tenant**: 只读

---

## 支付管理 (Payments)

| 端点 | 方法 | 路径 | 认证 | 权限 | 说明 |
|------|------|------|------|------|------|
| 获取支付列表 | GET | `/api/v1/payments` | 是 | all | 支持分页、搜索、筛选 |
| 获取支付详情 | GET | `/api/v1/payments/{id}` | 是 | all | 获取单条支付记录 |
| 创建支付记录 | POST | `/api/v1/payments` | 是 | admin/landlord | 创建新支付 |
| 更新支付记录 | PUT | `/api/v1/payments/{id}` | 是 | admin/landlord | 更新支付信息 |
| 删除支付记录 | DELETE | `/api/v1/payments/{id}` | 是 | admin/landlord | 删除支付记录 |
| 获取支付统计 | GET | `/api/v1/payments/stats` | 是 | admin/landlord | 收支统计 |

### 查询参数（列表）
- `page`, `size`: 分页参数
- `room_id`: 房间ID筛选
- `payment_type`: 类型筛选（rent/deposit/utility/other）
- `status`: 状态筛选（pending/completed/overdue/cancelled）
- `start_date`: 开始日期（payment_date >=）
- `end_date`: 结束日期（payment_date <=）
- `sort_by`: 排序字段
- `order`: 排序方向

### 业务逻辑
- **创建租金记录**: 自动计算 `amount = monthly_rent × payment_cycle`
- **创建水电费记录**: 从抄表记录获取，不手动创建
- **逾期自动判断**: 查询时动态更新状态

### 权限说明
- **admin**: 所有操作
- **landlord**: 所有操作（自己管理的房间）
- **tenant**: 只读（只能看自己房间的）

---

## 水电抄表管理 (Utility Readings)

| 端点 | 方法 | 路径 | 认证 | 权限 | 说明 |
|------|------|------|------|------|------|
| 获取抄表列表 | GET | `/api/v1/utility/readings` | 是 | all | 支持分页、搜索、筛选 |
| 获取抄表详情 | GET | `/api/v1/utility/readings/{id}` | 是 | all | 获取单条抄表记录 |
| 创建抄表记录 | POST | `/api/v1/utility/readings` | 是 | admin/landlord | 自动计算用量和费用 |
| 更新抄表记录 | PUT | `/api/v1/utility/readings/{id}` | 是 | admin/landlord | 仅允许更新备注 |
| 删除抄表记录 | DELETE | `/api/v1/utility/readings/{id}` | 是 | admin/landlord | 删除抄表记录 |
| 获取房间抄表历史 | GET | `/api/v1/rooms/{room_id}/utility-readings` | 是 | all | 获取某房间的抄表历史 |
| 获取上次读数 | GET | `/api/v1/utility/readings/previous/{room_id}/{type}` | 是 | all | 获取某房间某类型的上次读数 |

### 查询参数（列表）
- `page`, `size`: 分页参数
- `room_id`: 房间ID筛选
- `utility_type`: 类型筛选（water/electricity/gas）
- `start_date`: 开始日期（reading_date >=）
- `end_date`: 结束日期（reading_date <=）
- `sort_by`: 排序字段
- `order`: 排序方向（默认 reading_date DESC）

### 业务逻辑
创建抄表时自动执行：
1. 查询上次读数（同房间+同类型）
2. 查询有效费率（按 reading_date 取最新）
3. 计算 `usage = reading - previous_reading`
4. 计算 `amount = usage × rate`
5. 冗余存储 `previous_reading, usage, amount, rate_used`

### 权限说明
- **admin**: 所有操作
- **landlord**: 所有操作（自己管理的房间）
- **tenant**: 只读（只能看自己房间的）

---

## 水电费率管理 (Utility Rates)

| 端点 | 方法 | 路径 | 认证 | 权限 | 说明 |
|------|------|------|------|------|------|
| 获取费率列表 | GET | `/api/v1/utility/rates` | 是 | all | 支持分页、筛选 |
| 获取费率详情 | GET | `/api/v1/utility/rates/{id}` | 是 | all | 获取单条费率 |
| 创建费率 | POST | `/api/v1/utility/rates` | 是 | admin/landlord | 创建新费率 |
| 更新费率 | PUT | `/api/v1/utility/rates/{id}` | 是 | admin/landlord | 更新费率（禁用） |
| 删除费率 | DELETE | `/api/v1/utility/rates/{id}` | 是 | admin/landlord | 软删除（is_active=false） |
| 获取当前有效费率 | GET | `/api/v1/utility/rates/active` | 是 | all | 获取所有类型的当前费率 |
| 获取某类型费率历史 | GET | `/api/v1/utility/rates/{type}/history` | 是 | all | 获取某类型的历史费率 |

### 查询参数（列表）
- `page`, `size`: 分页参数
- `utility_type`: 类型筛选
- `is_active`: 是否激活（true/false）
- `sort_by`: effective_date
- `order`: desc

### 业务逻辑
- **创建费率**: 同一类型可创建多个（不同生效日期）
- **软删除**: 不物理删除，设置 `is_active=false`
- **费率查询**: 按 `effective_date DESC` 排序，取最新

### 权限说明
- **admin**: 所有操作
- **landlord**: 所有操作
- **tenant**: 只读

---

## 用户管理 (Users)

| 端点 | 方法 | 路径 | 认证 | 权限 | 说明 |
|------|------|------|------|------|------|
| 获取用户列表 | GET | `/api/v1/users` | 是 | admin | 支持分页 |
| 获取用户详情 | GET | `/api/v1/users/{id}` | 是 | admin/自己 | 获取用户信息 |
| 更新用户信息 | PUT | `/api/v1/users/{id}` | 是 | admin/自己 | 更新用户信息 |
| 删除用户 | DELETE | `/api/v1/users/{id}` | 是 | admin | 软删除用户 |
| 修改用户角色 | PUT | `/api/v1/users/{id}/role` | 是 | admin | 修改用户角色 |

### 权限说明
- **admin**: 所有操作
- **landlord**: 仅查看和修改自己
- **tenant**: 仅查看和修改自己

---

## 统计报表 (Statistics)

| 端点 | 方法 | 路径 | 认证 | 权限 | 说明 |
|------|------|------|------|------|------|
| 房间统计 | GET | `/api/v1/stats/rooms` | 是 | admin/landlord | 出租率、空置率 |
| 收入统计 | GET | `/api/v1/stats/revenue` | 是 | admin/landlord | 月度/年度收入 |
| 水电费统计 | GET | `/api/v1/stats/utility` | 是 | admin/landlord | 水电费统计 |
| 逾期提醒 | GET | `/api/v1/stats/overdue` | 是 | admin/landlord | 逾期租约列表 |
| 租约到期提醒 | GET | `/api/v1/stats/expiring` | 是 | admin/landlord | 即将到期租约 |

### 查询参数
- `start_date`: 统计开始日期
- `end_date`: 统计结束日期
- `group_by`: 分组方式（day/month/year）

---

## 系统配置 (System)

| 端点 | 方法 | 路径 | 认证 | 权限 | 说明 |
|------|------|------|------|------|------|
| 系统信息 | GET | `/api/v1/system/info` | 否 | all | 版本信息 |
| 健康检查 | GET | `/api/v1/health` | 否 | all | 健康状态 |

---

## 权限控制总结

### 角色定义
- **admin**: 系统管理员，所有权限
- **landlord**: 房东，管理房间和租金
- **tenant**: 租客，只读查看自己相关信息

### 权限矩阵

| 操作 | admin | landlord | tenant |
|------|-------|----------|--------|
| 登录/注册 | ✓ | ✓ | ✓ |
| 查看房间 | ✓ | ✓ | ✓ |
| 创建/修改/删除房间 | ✓ | ✓ | ✗ |
| 查看支付记录 | ✓ | ✓ | ✓（仅自己） |
| 创建/修改/删除支付 | ✓ | ✓ | ✗ |
| 查看抄表记录 | ✓ | ✓ | ✓（仅自己） |
| 创建/修改/删除抄表 | ✓ | ✓ | ✗ |
| 查看费率 | ✓ | ✓ | ✓ |
| 创建/修改/删除费率 | ✓ | ✓ | ✗ |
| 用户管理 | ✓ | ✗ | ✗ |
| 统计报表 | ✓ | ✓ | ✗ |

### 实现方式
- 使用 FastAPI 的 `Depends(get_current_user)` 获取当前用户
- 在每个端点中检查 `user.role` 权限
- landlord/tenant 查询时自动过滤数据（只显示相关房间）

---

## 错误码定义

| 错误码 | HTTP状态 | 说明 |
|--------|----------|------|
| AUTH_001 | 400 | 用户名已存在 |
| AUTH_002 | 401 | 用户名或密码错误 |
| AUTH_003 | 401 | Token 无效或过期 |
| AUTH_004 | 403 | 权限不足 |
| AUTH_005 | 429 | 登录尝试过多（锁定） |
| AUTH_006 | 400 | 密码强度不够 |
| AUTH_007 | 401 | 旧密码错误 |
| AUTH_008 | 400 | 新旧密码相同 |
| ROOM_001 | 400 | 房间号已存在 |
| ROOM_002 | 400 | 租约日期无效 |
| ROOM_003 | 404 | 房间不存在 |
| PAYMENT_001 | 400 | 支付金额无效 |
| PAYMENT_002 | 404 | 支付记录不存在 |
| UTILITY_001 | 400 | 当前读数小于上次读数 |
| UTILITY_002 | 400 | 未找到有效费率 |
| UTILITY_003 | 404 | 抄表记录不存在 |
| RATE_001 | 400 | 费率已存在 |
| RATE_002 | 404 | 费率不存在 |

---

## 速率限制

| 端点类型 | 限制 | 时间窗口 |
|----------|------|----------|
| 登录 | 5次/IP | 5分钟 |
| 注册 | 3次/IP | 1小时 |
| 普通查询 | 100次/用户 | 1分钟 |
| 修改操作 | 20次/用户 | 1分钟 |
