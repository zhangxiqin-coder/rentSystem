# 租房小能手 - 租赁管理系统

一个功能完整的租赁管理系统，支持房间管理、租约管理、收租记录、水电抄表和自动通知等功能。

## 📋 功能特性

### 核心功能
- **房间管理**：房间增删改查，支持批量操作
- **租约管理**：租期管理、租金设置、租客信息
- **收租记录**：租金收取记录、收租统计、欠租提醒
- **水电管理**：水电抄表、自动计费、费用统计
- **自动通知**：水电录入后自动生成收租通知（飞书群组）
- **数据导出**：支持导出收租记录、水电数据为Excel
- **权限管理**：管理员和租客两种角色权限控制

### 技术亮点
- 🔒 安全认证：JWT令牌 + 密码加密存储
- 📊 数据校验：Pydantic数据验证 + SQLAlchemy ORM
- 🎨 现代UI：Vue 3 + Element Plus响应式设计
- ⚡ 性能优化：前端懒加载、虚拟滚动、缓存优化
- 🔄 自动化：水电录入自动触发收租通知
- 📱 消息推送：飞书群组自动通知

## 🛠️ 技术栈

### 后端
- **框架**：FastAPI 0.104+
- **数据库**：SQLite（可切换PostgreSQL/MySQL）
- **ORM**：SQLAlchemy 2.0+
- **认证**：JWT（PyJWT）
- **数据验证**：Pydantic v2

### 前端
- **框架**：Vue 3.3+ (Composition API)
- **构建工具**：Vite 5.0+
- **UI组件**：Element Plus
- **路由**：Vue Router 4
- **状态管理**：Pinia
- **HTTP客户端**：Axios
- **语言**：TypeScript 5.0+

### 部署
- **服务器**：腾讯云CVM
- **Web服务器**：Nginx（可选）
- **进程管理**：systemd / supervisor

## 📦 快速开始

### 环境要求
- Python 3.11+
- Node.js 18+
- npm 或 pnpm

### 1. 克隆项目

```bash
git clone https://github.com/lengyubing/rentSystem.git
cd rentSystem
```

### 2. 后端设置

```bash
cd backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python -c "from app.models import Base; from app.core.database import engine; Base.metadata.create_all(bind=engine)"

# 创建管理员账号
python -c "from app.core.security import create_admin_user; create_admin_user('admin', 'admin123')"

# 启动后端
uvicorn app.main:app --reload --port 8000
```

### 3. 前端设置

```bash
cd frontend

# 安装依赖
npm install

# 配置API地址（如需要）
echo "VITE_API_BASE_URL=http://localhost:8000" > .env.development

# 启动开发服务器
npm run dev
```

### 4. 访问系统

- 前端地址：http://localhost:5173
- 后端API：http://localhost:8000
- API文档：http://localhost:8000/docs

**默认管理员账号**：
- 用户名：`admin`
- 密码：`admin123`

## 🚀 生产部署

### 方式1：直接部署（推荐）

```bash
# 构建前端
cd frontend
npm run build

# 部署到服务器
cd ..
./deploy-production.sh
```

### 方式2：Docker部署

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d
```

### 方式3：云服务部署

详细步骤请参考 [部署文档](./docs/DEPLOYMENT.md)

**服务器配置**（腾讯云CVM示例）：
- 操作系统：Ubuntu 22.04 LTS
- CPU：2核
- 内存：4GB
- 带宽：5Mbps

**安全组配置**：
- 开放端口：80（HTTP）、443（HTTPS）、8000（后端API）、5173（前端开发）

## 📁 项目结构

```
rent-management-system/
├── backend/                 # 后端项目
│   ├── app/
│   │   ├── api/            # API路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据模型
│   │   ├── schemas/        # Pydantic模式
│   │   ├── service/        # 业务逻辑
│   │   └── utils/          # 工具函数
│   ├── tests/              # 测试代码
│   ├── venv/               # 虚拟环境
│   └── requirements.txt    # Python依赖
├── frontend/               # 前端项目
│   ├── src/
│   │   ├── api/           # API调用
│   │   ├── components/    # Vue组件
│   │   ├── router/        # 路由配置
│   │   ├── stores/        # Pinia状态
│   │   ├── types/         # TypeScript类型
│   │   ├── utils/         # 工具函数
│   │   └── views/         # 页面视图
│   └── package.json       # Node依赖
├── docs/                  # 文档
├── scripts/               # 部署脚本
└── README.md             # 项目说明
```

## 🔧 配置说明

### 后端配置

`backend/.env`（生产环境）：
```bash
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATABASE_URL=sqlite:///./rent_management.db
```

### 前端配置

`frontend/.env.production`（生产环境）：
```bash
VITE_API_BASE_URL=https://your-domain.com/api
```

## 📖 使用指南

### 房间管理
1. 添加房间：填写房号、租金、面积等信息
2. 编辑房间：修改房间信息、租客姓名、租期等
3. 批量操作：选择多个房间进行批量编辑或删除

### 水电抄表
1. 进入"水电管理"页面
2. 选择房间和抄表日期
3. 录入水表和电表读数
4. 系统自动计算用量和费用
5. 水电录入完成后自动发送收租通知到飞书

### 收租管理
1. 录入水电后系统自动生成收租消息
2. 消息包含房租、水费、电费和应付总额
3. 实际收到租金后点击"标记已收"

### 数据导出
- 支持导出收租记录（Excel格式）
- 支持导出水电数据（Excel格式）
- 按日期范围筛选导出

## 🔐 安全特性

- ✅ 密码加密存储（bcrypt）
- ✅ JWT令牌认证
- ✅ CORS跨域保护
- ✅ SQL注入防护（ORM参数化查询）
- ✅ XSS防护（前端转义）
- ✅ 权限控制（角色权限）

## 🐛 常见问题

### 1. 后端启动失败
```bash
# 检查端口占用
lsof -i :8000

# 检查Python版本
python --version  # 需要3.11+
```

### 2. 前端API连接失败
```bash
# 检查后端是否运行
curl http://localhost:8000/api/health

# 检查前端配置
cat frontend/.env.development
```

### 3. 数据库错误
```bash
# 重新初始化数据库
cd backend
rm rent_management.db
python -c "from app.models import Base; from app.core.database import engine; Base.metadata.create_all(bind=engine)"
```

### 4. 消息通知不发送
- 确保飞书群组配置正确
- 检查定时任务是否运行：`cronjob list`
- 查看队列目录：`ls ~/.hermes/wechat_queue/`

## 📚 更多文档

- [部署文档](./docs/DEPLOYMENT.md) - 生产环境部署指南
- [开发文档](./docs/DEVELOPMENT.md) - 开发环境搭建
- [API文档](./docs/API.md) - 接口文档
- [更新日志](./CHANGELOG.md) - 版本更新记录

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

## 👥 作者

lengyubing

---

**最后更新**：2026年4月24日
