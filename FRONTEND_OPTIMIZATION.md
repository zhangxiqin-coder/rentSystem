# 前端性能优化指南

## 问题诊断

中国大陆访问慢的主要原因：
1. **资源加载慢**：npm包体积大，首次加载时间长
2. **HMR WebSocket**：开发环境的热更新会建立WebSocket连接
3. **构建产物未优化**：缺少代码分割和压缩

## 已实施的优化

### 1. Vite 构建优化 (`vite.config.ts`)

✅ **代码分割**：将 Element Plus 和 Vue 生态分离
```typescript
manualChunks: {
  'element-plus': ['element-plus', '@element-plus/icons-vue'],
  'vue-vendor': ['vue', 'vue-router', 'pinia'],
}
```

✅ **生产环境优化**：
- 移除 console.log
- 关闭 source map
- 启用 CSS 代码分割

✅ **预构建优化**：
```typescript
optimizeDeps: {
  include: ['vue', 'vue-router', 'pinia', 'element-plus', 'axios'],
}
```

### 2. HTML 优化 (`index.html`)

✅ **预连接**：提前建立到后端的 TCP 连接
```html
<link rel="preconnect" href="http://43.134.40.91:8000">
```

### 3. 后端确认

✅ **无长连接**：后端不使用 WebSocket 或 SSE，全部基于 HTTP REST API

## 部署优化建议

### 方案 A：国内 CDN（推荐）

将构建产物部署到国内 CDN：

```bash
# 1. 构建生产版本
cd frontend
npm run build

# 2. 部署到国内服务
# 选项 1: 腾讯云 COS + CDN
# 选项 2: 阿里云 OSS + CDN
# 选项 3: 七牛云存储
```

### 方案 B：使用 Nginx 反向代理（当前方案）

在服务器上配置 Nginx：

```nginx
server {
    listen 80;
    server_name 43.134.40.91;

    # 启用 gzip 压缩
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

    # 前端静态资源
    location / {
        root /home/agentuser/rent-management-system/frontend/dist;
        try_files $uri $uri/ /index.html;

        # 缓存策略
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # 后端 API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;

        # 连接优化
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;

        # 禁用缓冲（实时响应）
        proxy_buffering off;
    }
}
```

### 方案 C：使用 unpkg CDN（实验性）

如果想让用户直接从 CDN 加载 Vue/Element Plus：

1. 安装 Vite 插件：
```bash
npm install --save-dev vite-plugin-cdn-import
```

2. 修改 `vite.config.ts`（暂未实施，需要测试）

## 性能监控

### 测试工具

```bash
# Lighthouse（Chrome DevTools）
# lighthouse http://43.134.40.91:5173 --view

# WebPageTest
# https://www.webpagetest.org/

# 国内测试工具
# https://www.itdog.cn/batch/
```

### 当前构建产物大小

构建后检查：
```bash
cd frontend
npm run build
du -sh dist/*
```

预期优化效果：
- 首屏加载时间：< 2秒（国内4G）
- JS 体积：< 500KB（gzip后）
- CSS 体积：< 100KB（gzip后）

## 下一步优化方向

1. ✅ 代码分割（已完成）
2. ✅ 移除 console（已完成）
3. ⏳ 路由懒加载
4. ⏳ 图片优化（WebP 格式）
5. ⏳ Service Worker 缓存
6. ⏳ HTTP/2 推送

## 脚本命令

```bash
# 开发环境（禁用 HMR WebSocket）
npm run dev -- --host 0.0.0.0 --port 5173

# 生产构建
npm run build

# 预览构建产物
npm run preview

# 构建并分析大小
npm run build
npx vite-bundle-visualizer
```
