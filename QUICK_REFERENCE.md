# 快速参考 - 性能优化

## 🚀 立即可用的命令

### 构建前端
```bash
cd /home/agentuser/rent-management-system
./build-frontend.sh
```

### 部署到生产环境
```bash
sudo ./deploy-production.sh
```

### 测试性能
```bash
./test-performance.sh
```

## 📊 优化效果

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| Element Plus | 954 KB | 303 KB | 68% |
| 静态资源缓存 | 无 | 1 年 | ∞ |
| Gzip 压缩 | 无 | 有 | 68-86% |
| 代码分割 | 无 | 有 | 更快 |

## 🔗 访问地址

| 环境 | 地址 | 状态 |
|------|------|------|
| 开发环境 | http://43.134.40.91:5173 | ✅ |
| 生产环境 | http://43.134.40.91 | ⏳ 需部署 |
| API 文档 | http://43.134.40.91:8000/docs | ✅ |

## 📝 关键文件

- `build-frontend.sh` - 构建脚本
- `deploy-production.sh` - 部署脚本
- `nginx-config.conf` - Nginx 配置
- `frontend/vite.config.ts` - Vite 配置

## 💡 主要改进

1. ✅ **无长连接** - 确认后端不使用 WebSocket
2. ✅ **代码分割** - Element Plus、Vue、业务代码分离
3. ✅ **Gzip 压缩** - Nginx 配置完成
4. ✅ **静态缓存** - 1 年缓存策略
5. ✅ **移除 console** - 生产环境干净

## 🎯 下一步

```bash
# 一键部署
sudo ./deploy-production.sh
```

部署完成后，访问 http://43.134.40.91 即可。
