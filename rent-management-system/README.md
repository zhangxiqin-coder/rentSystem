# 合租房屋管理系统

> **技术栈**: Vue 3 + FastAPI + SQLite  
> **部署**: Railway/Render + GitHub Actions

## 项目介绍

为房东打造的合租房屋管理系统，支持多房间管理、租金记录、水电费计算等功能。

## 核心功能

- 👤 用户认证（登录/注册）
- 🏠 房间管理（增删改查）
- 💰 租金管理（交租记录、到期提醒）
- 💡 水电管理（抄表录入、费用计算）
- 📊 统计分析（费用趋势图表）
- 📤 数据导出（Excel 导出）

## 快速开始

### 后端启动

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 前端启动

```bash
cd frontend
npm install
npm run dev
```

## 项目结构

```
rent-management-system/
├── backend/          # FastAPI 后端
├── frontend/         # Vue 3 前端
└── .github/          # GitHub Actions CI/CD
```

## 开发状态

- [x] 项目初始化
- [ ] 用户认证模块
- [ ] 房间管理模块
- [ ] 租金管理模块
- [ ] 水电管理模块
- [ ] 统计分析模块
- [ ] 自动部署配置

## 许可证

MIT
