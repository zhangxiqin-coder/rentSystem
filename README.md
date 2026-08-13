# 🏠 租房小能手 — 租赁 + 资产管理系统

一套为房东量身打造的全栈管理系统，涵盖租赁管理（房间 / 租约 / 收租 / 水电）、个人投资资产追踪和合同自动生成。线上运行于腾讯云，手机随时操作。

> **线上地址**：[fangdong.fun](https://fangdong.fun)

---

## ✨ 功能总览

### 🏘️ 租赁管理

| 模块 | 核心能力 |
|------|---------|
| **房间管理** | 多楼栋多房间、批量导入、初始水电读数、退租 / 入住流转 |
| **租客管理** | 租客档案、身份证信息、多租客（主租客 + 同住亲友）|
| **租约管理** | 租期跟踪、月 / 季 / 半年付周期、按合同日自动算逾期 |
| **水电管理** | 抄表录入、自动计费、OCR 拍照识别读数、防重复录入 |
| **收租管理** | 自动生成收租通知、一键标记已收、防止重复收租 |
| **催租提醒** | 可配置催租日（`notify_after_day`），到期前自动提醒 |
| **合同生成** | 多模板（果岭 / 登新公寓）、HTML → PDF 导出 |
| **数据导出** | 收租记录、水电数据、房间列表导出 Excel |

### 💰 个人资产管理

| 模块 | 核心能力 |
|------|---------|
| **投资平台** | 多平台管理（8+ 平台 44+ 标的），余额上报 + 转入转出记录 |
| **资产快照** | 定期记录资产总览，追踪变化趋势 |
| **固定资产** | 房产等固定资产登记与管理 |
| **报表统计** | 收入统计（以实际收款日为准）、资产分布可视化 |

### 🔔 自动化 & 通知

- **飞书群通知**：水电录入后自动推送收租消息到飞书群
- **微信通知**：收租提醒通过微信推送
- **Sync 重试队列**：Turso 云数据库写入失败自动重试，5 次失败微信告警
- **定时备份**：每 3 天自动备份云端数据库

---

## 🛠️ 技术栈

### 后端

- **框架**：FastAPI 0.104
- **数据库**：Turso (libSQL) 云数据库 — embedded replica 模式，本地缓存 + 云端同步
- **ORM**：SQLAlchemy 2.0
- **认证**：JWT + CSRF 双重防护
- **数据验证**：Pydantic v2
- **PDF**：WeasyPrint（HTML → PDF）
- **OCR**：智谱 GLM-4V 视觉模型（水电表读数识别）
- **生产保护**：`prod_guard.py` 拦截直接 ORM 操作生产库

### 前端

- **框架**：Vue 3.5 (Composition API)
- **构建**：Vite 8 + TypeScript 6
- **UI**：Element Plus
- **图表**：ECharts（资产分布、收入统计）
- **路由**：Vue Router 4
- **状态管理**：Pinia
- **移动端适配**：响应式设计 + vConsole 调试

### 基础设施

- **服务器**：腾讯云 CVM（Ubuntu 22.04，2C4G）
- **域名**：fangdong.fun
- **Web 服务器**：Nginx（反向代理 + SSL）
- **进程管理**：systemd user service（`rent-backend` + `rent-frontend`）
- **数据库备份**：Cron 定时 dump Turso 云库

---

## 📊 数据模型

```
User           用户（多用户隔离，owner_id 行级安全）
Room           房间（楼栋 / 房号 / 租金 / 初始水电读数）
Tenant         租客（身份证 / 电话 / 催租日）
RoomOccupant   房间居住人（多租客：主租客 + 同住亲友）
LeaseRecord    租约记录（租期 / 月租 / 付款周期）
Payment        收租记录（收入以 payment_date 为准）
UtilityReading 水电抄表记录
UtilityRate    水电费率（水 5 元/吨、电 1 元/度，可自定义）
UtilityBill    水电账单
Deposit        押金记录
AssetPlatform  投资平台
AssetItem      投资标的
AssetRecord    资产余额上报记录
AssetSnapshot  资产快照
FixedAsset     固定资产
```

---

## 📁 项目结构

```
rent-management-system/
├── backend/                      # 后端
│   ├── app/
│   │   ├── api/                  # 16 个 API 模块
│   │   │   ├── auth.py           # 认证
│   │   │   ├── rooms.py          # 房间
│   │   │   ├── tenants.py        # 租客
│   │   │   ├── payments.py       # 收租
│   │   │   ├── utility_*.py      # 水电（抄表/费率/账单）
│   │   │   ├── lease_records.py  # 租约
│   │   │   ├── room_occupants.py # 多租客
│   │   │   ├── contracts.py      # 合同生成
│   │   │   ├── ocr.py            # OCR 识别
│   │   │   ├── assets.py         # 资产管理
│   │   │   ├── statistics.py     # 统计报表
│   │   │   ├── reminders.py      # 催租提醒
│   │   │   ├── export.py         # Excel 导出
│   │   │   └── users.py          # 用户管理
│   │   ├── models.py             # ORM 模型（15 张表）
│   │   ├── schemas.py            # Pydantic Schema
│   │   ├── database.py           # Turso libSQL 连接 + 自动同步
│   │   ├── prod_guard.py         # 生产库保护
│   │   ├── sync_queue.py         # Sync 失败重试队列
│   │   └── core/                 # 安全 / 配置
│   ├── tests/                    # E2E 集成测试
│   ├── tools/                    # 运维工具脚本
│   ├── venv/                     # Python 虚拟环境（含 libsql_experimental）
│   └── requirements.txt
├── frontend/                     # 前端
│   ├── src/
│   │   ├── views/                # 15 个页面
│   │   │   ├── DashboardView     # 仪表盘
│   │   │   ├── RoomsView         # 房间列表
│   │   │   ├── RoomDetailView    # 房间详情（含居住人 Tab）
│   │   │   ├── TenantsView       # 租客列表
│   │   │   ├── UtilityView       # 水电管理
│   │   │   ├── PaymentsView      # 收租记录
│   │   │   ├── ReportsView       # 报表统计
│   │   │   ├── AssetsView        # 资产管理
│   │   │   ├── GridInvestView    # 投资组合
│   │   │   ├── SettingsView      # 系统设置
│   │   │   └── ...
│   │   ├── api/                  # API 调用层
│   │   ├── components/           # 公共组件
│   │   └── router/               # 路由
│   └── package.json
├── .githooks/                    # Git hooks（pre-commit 自动跑测试）
├── docs/                         # 文档
└── README.md
```

---

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- Turso 账号（免费额度够用）

### 1. 克隆项目

```bash
git clone https://github.com/zhangxiqin-coder/rentSystem.git
cd rentSystem
```

### 2. 后端设置

```bash
cd backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install libsql_experimental  # Turso libSQL 驱动

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 Turso 数据库 URL 和 Token：
#   TURSO_DATABASE_URL=libsql://your-db.turso.io
#   TURSO_AUTH_TOKEN=your-token
#   SECRET_KEY=your-secret-key

# 初始化数据库
python -c "from app.database import create_tables; create_tables()"

# 启动后端
uvicorn app.main:app --reload --port 8000
```

### 3. 前端设置

```bash
cd frontend

# 安装依赖
npm install

# 配置 API 地址
echo "VITE_API_BASE_URL=http://localhost:8000" > .env.development

# 启动开发服务器
npm run dev
```

### 4. 访问系统

- 前端：http://localhost:5173
- API 文档：http://localhost:8000/docs

---

## 📦 生产部署

### 方式：systemd + Nginx（线上方案）

```bash
# 构建前端
cd frontend && npm run build

# 后端配置
cd backend
cp .env.example .env  # 填入生产环境配置

# 安装 systemd user service
# rent-backend.service  → uvicorn app.main:app --port 8000
# rent-frontend.service → serve dist/ --port 5173

# Nginx 反向代理
# /api  → localhost:8000（后端）
# /     → localhost:5173（前端）
```

**服务管理**：
```bash
systemctl --user restart rent-backend.service
systemctl --user restart rent-frontend.service
systemctl --user status rent-backend.service
```

**安全组配置**（腾讯云）：
- 开放端口：80（HTTP）、443（HTTPS）
- SSH 端口：22 + 2222

---

## 🔐 安全特性

- ✅ JWT 令牌认证 + CSRF 双重防护
- ✅ 密码 bcrypt 加密
- ✅ 多用户数据隔离（`owner_id` 行级安全）
- ✅ 生产库保护（拦截脚本直接 ORM 操作）
- ✅ Turso 云数据库自动同步 + 失败重试
- ✅ E2E 集成测试 + pre-commit hook 自动运行
- ✅ 定时数据库备份

---

## 🧪 测试

```bash
cd backend

# 运行全部测试（使用独立测试数据库，不影响生产数据）
pytest

# 核心业务 E2E 测试（12 个用例：增房间 / 增租客 / 录入水电 / 收租）
pytest tests/test_e2e_core_flows.py -v
```

测试通过 pre-commit hook 自动触发（`.githooks/pre-commit`），不通过则阻止提交。

---

## 📖 使用指南

### 收租流程

1. **每月抄水电** → 水电管理页面，选择房间录入读数（或拍照 OCR 识别）
2. **自动生成通知** → 水电录入后系统自动算费，生成收租消息
3. **推送通知** → 自动发送到飞书群 / 微信
4. **标记已收** → 实际收到租金后，点击「标记已收」

### 收租通知格式

```
🏠 2-1801 本月收租：1850 元

💧 水费：上月 120 → 本月 135（15吨 × 5元 = 75元）
⚡ 电费：上月 580 → 本月 630（50度 × 1元 = 50元）
🔑 房租：1725元
```

---

## 📄 许可证

MIT License

---

## 👤 作者

zhangxiqin-coder

---

**最后更新**：2026年8月
