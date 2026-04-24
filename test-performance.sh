#!/bin/bash

# 性能测试脚本
# 用途：测试前端加载性能和 API 响应时间

echo "🔍 租户管理系统 - 性能测试"
echo "======================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 测试函数
test_url() {
    local url=$1
    local name=$2

    echo -n "📊 测试 $name ... "

    # 使用 curl 测试响应时间
    response=$(curl -o /dev/null -s -w "%{http_code}|%{time_total}|%{size_download}" "$url" 2>&1)

    if [ $? -eq 0 ]; then
        IFS='|' read -r http_code time_total size_download <<< "$response"

        # 判断性能
        if (( $(echo "$time_total < 1.0" | bc -l) )); then
            color=$GREEN
            status="优秀"
        elif (( $(echo "$time_total < 2.0" | bc -l) )); then
            color=$YELLOW
            status="良好"
        else
            color=$RED
            status="慢"
        fi

        echo -e "${color}HTTP $http_code | ${time_total}s | ${(size_download/1024)}KB ($status)${NC}"
        return 0
    else
        echo -e "${RED}连接失败${NC}"
        return 1
    fi
}

# 1. 测试前端首页
echo "🌐 前端性能测试"
echo "----------------"
test_url "http://43.134.40.91:5173/" "前端首页（开发环境）"
test_url "http://43.134.40.91/" "前端首页（生产环境，如果配置了 Nginx）"
echo ""

# 2. 测试静态资源
echo "📦 静态资源测试"
echo "----------------"
test_url "http://43.134.40.91:5173/favicon.svg" "Favicon"
test_url "http://43.134.40.91:5173/src/main.ts" "主入口文件"
echo ""

# 3. 测试 API
echo "🔌 API 性能测试"
echo "----------------"
test_url "http://43.134.40.91:8000/api/health/" "健康检查"
test_url "http://43.134.40.91:8000/docs" "API 文档"
echo ""

# 4. 并发测试（如果有 Apache Bench）
if command -v ab &> /dev/null; then
    echo "⚡ 并发性能测试（100 请求，10 并发）"
    echo "------------------------------------"
    echo "测试前端首页..."
    ab -n 100 -c 10 -q http://43.134.40.91:5173/ | grep -E "Requests per second|Time per"
    echo ""
    echo "测试 API 健康检查..."
    ab -n 100 -c 10 -q http://43.134.40.91:8000/api/health/ | grep -E "Requests per second|Time per"
    echo ""
fi

# 5. 网络延迟测试
echo "🌐 网络延迟测试"
echo "----------------"
ping -c 5 43.134.40.91 | tail -1
echo ""

# 6. 端口检查
echo "🔍 端口状态检查"
echo "----------------"
for port in 8000 5173 80; do
    if nc -z -w 2 43.134.40.91 $port 2>/dev/null; then
        echo -e "${GREEN}✅ 端口 $port 开放${NC}"
    else
        echo -e "${RED}❌ 端口 $port 关闭或无法访问${NC}"
    fi
done
echo ""

# 7. 构建产物大小检查
echo "📏 构建产物分析"
echo "----------------"
if [ -d "/home/agentuser/rent-management-system/frontend/dist" ]; then
    echo "前端构建产物大小："
    du -sh /home/agentuser/rent-management-system/frontend/dist
    echo ""
    echo "最大的 5 个文件："
    find /home/agentuser/rent-management-system/frontend/dist -type f -exec du -h {} + | sort -rh | head -5
else
    echo "⚠️  未找到构建产物，请先运行 ./build-frontend.sh"
fi
echo ""

echo "======================================"
echo "✅ 性能测试完成！"
echo ""
echo "💡 优化建议："
echo "   - 首屏加载应 < 2秒"
echo "   - API 响应应 < 500ms"
echo "   - 静态资源应使用 CDN"
echo "   - 启用 gzip 压缩"
echo "   - 配置缓存策略"
echo ""
