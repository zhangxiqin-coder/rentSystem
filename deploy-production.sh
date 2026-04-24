#!/bin/bash

# 生产环境部署脚本
# 用途：构建前端、配置 Nginx、重启服务

set -e

echo "🚀 租户管理系统 - 生产环境部署"
echo "======================================"
echo ""

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 sudo 运行此脚本"
    exit 1
fi

# 1. 构建前端
echo "📦 步骤 1: 构建前端..."
cd /home/agentuser/rent-management-system
./build-frontend.sh
echo ""

# 2. 检查 Nginx 是否已安装
echo "🔍 步骤 2: 检查 Nginx..."
if ! command -v nginx &> /dev/null; then
    echo "⚠️  Nginx 未安装，正在安装..."
    apt-get update
    apt-get install -y nginx
else
    echo "✅ Nginx 已安装: $(nginx -v 2>&1)"
fi
echo ""

# 3. 配置 Nginx
echo "⚙️  步骤 3: 配置 Nginx..."
cp nginx-config.conf /etc/nginx/sites-available/rent-management-system

# 启用站点配置
if [ ! -L /etc/nginx/sites-enabled/rent-management-system ]; then
    ln -s /etc/nginx/sites-available/rent-management-system /etc/nginx/sites-enabled/
fi

# 删除默认配置（可选）
# rm -f /etc/nginx/sites-enabled/default

# 测试 Nginx 配置
echo "🧪 测试 Nginx 配置..."
if nginx -t; then
    echo "✅ Nginx 配置有效"
else
    echo "❌ Nginx 配置错误，请检查配置文件"
    exit 1
fi
echo ""

# 4. 重启 Nginx
echo "🔄 步骤 4: 重启 Nginx..."
systemctl restart nginx
echo "✅ Nginx 已重启"
echo ""

# 5. 检查后端服务
echo "🔍 步骤 5: 检查后端服务..."
if pgrep -f "uvicorn app.main:app" > /dev/null; then
    echo "✅ 后端服务运行中"
else
    echo "⚠️  后端服务未运行，请手动启动："
    echo "   cd /home/agentuser/rent-management-system/backend"
    echo "   ./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000"
fi
echo ""

# 6. 显示部署信息
echo "======================================"
echo "✅ 部署完成！"
echo ""
echo "📋 访问信息："
echo "   前端: http://43.134.40.91"
echo "   后端: http://43.134.40.91:8000"
echo "   API 文档: http://43.134.40.91:8000/docs"
echo ""
echo "📁 重要文件位置："
echo "   前端构建: /home/agentuser/rent-management-system/frontend/dist"
echo "   Nginx 配置: /etc/nginx/sites-available/rent-management-system"
echo "   Nginx 日志: /var/log/nginx/rent-management-*.log"
echo ""
echo "🔧 常用命令："
echo "   查看前端日志: tail -f /var/log/nginx/rent-management-access.log"
echo "   重启 Nginx: systemctl restart nginx"
echo "   测试 Nginx: nginx -t"
echo ""
echo "⚡ 性能优化已启用："
echo "   ✅ Gzip 压缩"
echo "   ✅ 静态资源缓存（1年）"
echo "   ✅ 代码分割（Vue、Element Plus 单独打包）"
echo "   ✅ 移除 console.log"
echo ""
