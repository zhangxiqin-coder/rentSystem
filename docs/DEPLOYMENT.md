# 部署指南

本文档详细说明如何将租房小能手系统部署到生产环境。

## 📋 目录

- [服务器要求](#服务器要求)
- [部署方式](#部署方式)
- [云服务部署（腾讯云CVM）](#云服务部署腾讯云cvm)
- [Nginx配置](#nginx配置)
- [HTTPS配置](#https配置)
- [进程管理](#进程管理)
- [维护监控](#维护监控)
- [常见问题](#常见问题)

## 服务器要求

### 最低配置
- CPU：2核
- 内存：2GB
- 硬盘：20GB
- 操作系统：Ubuntu 22.04 LTS / CentOS 7+

### 推荐配置
- CPU：4核
- 内存：4GB
- 硬盘：40GB SSD
- 带宽：5Mbps

### 软件要求
- Python 3.11+
- Node.js 18+
- Nginx 1.20+
- Git

## 部署方式

### 方式1：自动化部署脚本（推荐）

```bash
# 克隆项目
git clone https://github.com/lengyubing/rentSystem.git
cd rentSystem

# 执行部署脚本
chmod +x deploy-production.sh
./deploy-production.sh
```

### 方式2：手动部署

参见下方详细步骤。

## 云服务部署（腾讯云CVM）

### 1. 购买服务器

1. 登录腾讯云控制台
2. 选择"云服务器CVM"
3. 配置服务器：
   - 镜像：Ubuntu 22.04 LTS
   - 实例：2核4GB
   - 网络：按量计费，带宽5Mbps
4. 设置安全组规则（见下方）
5. 购买并启动

### 2. 配置安全组

**入站规则**：
| 协议 | 端口 | 来源 | 说明 |
|------|------|------|------|
| TCP | 22 | 0.0.0.0/0 | SSH |
| TCP | 80 | 0.0.0.0/0 | HTTP |
| TCP | 443 | 0.0.0.0/0 | HTTPS |
| TCP | 8000 | 0.0.0.0/0 | 后端API |

**出站规则**：允许全部

### 3. 登录服务器

```bash
# 使用SSH登录
ssh root@your_server_ip

# 或使用密钥
ssh -i /path/to/key.pem ubuntu@your_server_ip
```

### 4. 安装系统依赖

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装Python 3.11
sudo apt install python3.11 python3.11-venv python3-pip -y

# 安装Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs -y

# 安装Nginx
sudo apt install nginx -y

# 安装Git
sudo apt install git -y

# 安装Supervisor（进程管理）
sudo apt install supervisor -y
```

### 5. 克隆代码

```bash
# 克隆仓库
cd /opt
sudo git clone https://github.com/lengyubing/rentSystem.git
cd rentSystem

# 设置权限
sudo chown -R $USER:$USER /opt/rentSystem
```

### 6. 后端部署

```bash
cd /opt/rentSystem/backend

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python -c "from app.models import Base; from app.core.database import engine; Base.metadata.create_all(bind=engine)"

# 创建管理员账号（替换为你的密码）
python -c "from app.core.security import create_admin_user; create_admin_user('admin', 'your_secure_password')"

# 测试启动
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

访问 `http://your_server_ip:8000/docs` 验证API是否正常运行。

### 7. 前端构建

```bash
cd /opt/rentSystem/frontend

# 安装依赖
npm install

# 配置API地址
echo "VITE_API_BASE_URL=http://your_server_ip:8000" > .env.production

# 构建生产版本
npm run build
```

构建完成后，`dist` 目录包含所有静态文件。

### 8. 配置Nginx

创建Nginx配置文件：

```bash
sudo nano /etc/nginx/sites-available/rentSystem
```

添加以下内容：

```nginx
server {
    listen 80;
    server_name your_domain.com;  # 替换为你的域名或服务器IP

    # 前端静态文件
    location / {
        root /opt/rentSystem/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端API代理
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # CORS支持
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS";
        add_header Access-Control-Allow-Headers "Content-Type, Authorization";
    }

    # API文档
    location /docs {
        proxy_pass http://127.0.0.1:8000;
    }

    # Gzip压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/rentSystem /etc/nginx/sites-enabled/
sudo nginx -t  # 测试配置
sudo systemctl restart nginx
```

### 9. 配置Supervisor（后端进程管理）

创建Supervisor配置：

```bash
sudo nano /etc/supervisor/conf.d/rentSystem-backend.conf
```

添加以下内容：

```ini
[program:rentSystem-backend]
command=/opt/rentSystem/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
directory=/opt/rentSystem/backend
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/rentSystem-backend.err.log
stdout_logfile=/var/log/rentSystem-backend.out.log
environment=PYTHONUNBUFFERED="1"
```

启动服务：

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start rentSystem-backend
```

### 10. 配置防火墙

```bash
# UFW防火墙
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# 或使用iptables
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
```

## HTTPS配置

### 使用Let's Encrypt免费证书

```bash
# 安装Certbot
sudo apt install certbot python3-certbot-nginx -y

# 获取证书（自动配置Nginx）
sudo certbot --nginx -d your_domain.com

# 测试自动续期
sudo certbot renew --dry-run
```

Certbot会自动修改Nginx配置，添加HTTPS支持。

### 手动配置SSL证书

如果你有自己的SSL证书：

```nginx
server {
    listen 443 ssl;
    server_name your_domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # SSL配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # ... 其他配置
}

# HTTP重定向到HTTPS
server {
    listen 80;
    server_name your_domain.com;
    return 301 https://$server_name$request_uri;
}
```

## 进程管理

### 使用Supervisor

```bash
# 查看状态
sudo supervisorctl status

# 重启服务
sudo supervisorctl restart rentSystem-backend

# 查看日志
sudo supervisorctl tail -f rentSystem-backend

# 停止服务
sudo supervisorctl stop rentSystem-backend
```

### 使用systemd（可选）

创建systemd服务文件：

```bash
sudo nano /etc/systemd/system/rentSystem-backend.service
```

添加以下内容：

```ini
[Unit]
Description=Rent Management System Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/rentSystem/backend
Environment="PATH=/opt/rentSystem/backend/venv/bin"
ExecStart=/opt/rentSystem/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable rentSystem-backend
sudo systemctl start rentSystem-backend
sudo systemctl status rentSystem-backend
```

## 维护监控

### 日志查看

```bash
# 后端日志
sudo tail -f /var/log/rentSystem-backend.out.log

# Nginx日志
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Supervisor日志
sudo tail -f /var/log/supervisor/rentSystem-backend-*.log
```

### 性能监控

安装监控工具：

```bash
# htop - 进程监控
sudo apt install htop -y

# netdata - 系统监控
bash <(curl -Ss https://my-netdata.io/kickstart.sh)
```

### 数据备份

定期备份数据库：

```bash
# 创建备份脚本
cat > /opt/rentSystem/scripts/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/rentSystem"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# 备份数据库
cp /opt/rentSystem/backend/rent_management.db $BACKUP_DIR/db_$DATE.db

# 保留最近30天的备份
find $BACKUP_DIR -name "db_*.db" -mtime +30 -delete
EOF

chmod +x /opt/rentSystem/scripts/backup.sh

# 添加到crontab（每天凌晨2点备份）
crontab -e
# 添加：0 2 * * * /opt/rentSystem/scripts/backup.sh
```

### 更新部署

```bash
cd /opt/rentSystem

# 拉取最新代码
git pull origin main

# 更新后端
cd backend
source venv/bin/activate
pip install -r requirements.txt
sudo supervisorctl restart rentSystem-backend

# 更新前端
cd ../frontend
npm install
npm run build

# 重启Nginx
sudo nginx -s reload
```

## 常见问题

### 1. 端口被占用

```bash
# 查看端口占用
sudo lsof -i :8000
sudo lsof -i :80

# 杀死进程
sudo kill -9 <PID>
```

### 2. 数据库连接失败

```bash
# 检查数据库文件权限
ls -la /opt/rentSystem/backend/rent_management.db

# 修改权限
sudo chmod 664 /opt/rentSystem/backend/rent_management.db
sudo chown www-data:www-data /opt/rentSystem/backend/rent_management.db
```

### 3. 前端页面404

```bash
# 检查Nginx配置
sudo nginx -t

# 检查前端文件是否存在
ls -la /opt/rentSystem/frontend/dist/

# 查看Nginx错误日志
sudo tail -f /var/log/nginx/error.log
```

### 4. API跨域问题

确保后端CORS配置正确：

```python
# backend/app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应指定具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 5. 服务自动重启

```bash
# 检查服务状态
sudo supervisorctl status

# 查看错误日志
sudo supervisorctl tail -f rentSystem-backend stderr

# 手动重启
sudo supervisorctl restart rentSystem-backend
```

## 性能优化

### 1. 数据库优化

```python
# 使用连接池
# backend/app/core/database.py
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20
)
```

### 2. Nginx缓存

```nginx
# 静态文件缓存
location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### 3. Gzip压缩

已在Nginx配置中启用。

## 安全加固

### 1. 配置防火墙

```bash
sudo ufw enable
sudo ufw status
```

### 2. 限制SSH访问

```bash
# 禁用root登录
sudo nano /etc/ssh/sshd_config
# 修改：PermitRootLogin no

# 禁用密码登录（仅密钥）
# 修改：PasswordAuthentication no

# 重启SSH
sudo systemctl restart sshd
```

### 3. 安装Fail2ban

```bash
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 4. 定期更新

```bash
# 自动安全更新
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

**最后更新**：2026年4月24日
