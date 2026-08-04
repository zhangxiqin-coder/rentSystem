"""
生产库保护：禁止直接 import ORM SessionLocal 操作生产 Turso 库

机制：拦截 SessionLocal() 和 SessionLocal.configure()，如果检测到连接的是
生产 Turso 库（而非测试库），直接报错。

正确做法：
- 数据维护/批量操作 → 写临时脚本走 API（httpx 调 /api/v1/）
- 脚本确实需要直连 → 明确加 ALLOW_PROD_DB=1 环境变量，且 sync_to_cloud()
- 测试 → conftest.py 替换 SessionLocal 为测试库，自动放行
"""
import os
import sys
import traceback


def _check_direct_orm_usage():
    """检查是否在直接操作生产库。

    检测逻辑：
    1. TESTING=1 → 测试模式，放行
    2. ALLOW_PROD_DB=1 → 明确授权，放行
    3. 调用栈来自 conftest.py → 测试框架，放行
    4. 其他 → 报错
    """
    if os.getenv("TESTING") == "1":
        return

    if os.getenv("ALLOW_PROD_DB") == "1":
        return

    # 检查调用栈里有没有 conftest（测试环境）
    stack = traceback.extract_stack()
    for frame in stack:
        if "conftest" in frame.filename or "test_" in frame.filename:
            return

    # 到这里说明是生产环境下的直接 ORM 调用
    raise RuntimeError(
        "🚫 禁止直接操作生产数据库！\n"
        "生产环境使用 Turso embedded replica，直接 ORM 操作可能导致：\n"
        "  - ID 冲突（本地缓存和云端主键不一致）\n"
        "  - 缓存损坏（需要重建 turso_cache.db）\n"
        "  - 数据丢失（如 pingfei 被覆盖事件）\n\n"
        "正确做法：\n"
        "  1. 数据维护 → 走 API（httpx 调 /api/v1/）\n"
        "  2. 一次性脚本 → 设 ALLOW_PROD_DB=1 且务必调 sync_to_cloud()\n"
        "  3. 测试 → 用 test_rent_management.db（conftest.py 自动配置）\n"
    )
