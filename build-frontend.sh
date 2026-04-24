#!/bin/bash

# 前端构建和部署脚本
# 用途：优化构建产物，准备部署到生产环境

set -e

echo "🚀 开始前端优化构建..."

# 进入前端目录
cd "$(dirname "$0")/frontend"

# 1. 清理旧的构建产物
echo "🧹 清理旧构建..."
rm -rf dist

# 2. 安装依赖（如果需要）
if [ ! -d "node_modules" ]; then
    echo "📦 安装依赖..."
    npm install
fi

# 3. 生产构建（跳过类型检查以加快构建速度）
echo "🔨 构建生产版本（跳过类型检查）..."
npm run build:only

# 4. 分析构建产物大小
echo ""
echo "📊 构建产物大小："
du -sh dist/*
echo ""

# 5. 检查主要文件
echo "🔍 最大的 10 个文件："
find dist -type f -exec du -h {} + | sort -rh | head -10
echo ""

# 6. 计算总大小
TOTAL_SIZE=$(du -sb dist | cut -f1)
TOTAL_SIZE_MB=$(echo "scale=2; $TOTAL_SIZE / 1024 / 1024" | bc)
echo "📦 总大小: ${TOTAL_SIZE_MB} MB (${TOTAL_SIZE} bytes)"

# 7. 检查是否生成了 .gz 文件（gzip 压缩）
echo ""
echo "🔍 资源类型统计："
echo "  JS 文件: $(find dist -name "*.js" | wc -l)"
echo "  CSS 文件: $(find dist -name "*.css" | wc -l)"
echo "  其他文件: $(find dist -type f ! -name "*.js" ! -name "*.css" | wc -l)"

echo ""
echo "✅ 构建完成！"
echo ""
echo "📋 部署建议："
echo "   1. 将 dist/ 目录上传到服务器"
echo "   2. 配置 Nginx 指向 dist/ 目录"
echo "   3. 启用 gzip 压缩和缓存策略"
echo ""
echo "🚀 快速部署命令："
echo "   sudo ./deploy-production.sh"
echo ""
echo "📊 性能测试："
echo "   ./test-performance.sh"
