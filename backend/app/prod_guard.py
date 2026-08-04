"""
生产库保护：禁止直接 import ORM SessionLocal 操作生产 Turso 库

机制：拦截 SessionLocal() 直接调用，如果调用栈没经过 get_db()（API入口），
说明是脚本/命令行直接操作，直接报错。

正确做法：
- 数据维护/批量操作 → 走 API（httpx 调 /api/v1/）
- 脚本确实需要直连 → 设 ALLOW_PROD_DB=1 且 sync_to_cloud()
- 测试 → conftest.py 替换 SessionLocal 为测试库，自动放行
"""
import os
import traceback


def _check_direct_orm_usage():
    """检查是否在直接操作生产库。

    放行条件（满足任一即可）：
    1. TESTING=1 → 测试模式
    2. ALLOW_PROD_DB=1 → 明确授权的脚本
    3. 调用栈来自 conftest.py / test_*.py → 测试框架
    4. 调用栈经过 get_db() → API 正常请求路径
    """
    if os.getenv("TESTING") == "1":
        return

    if os.getenv("ALLOW_PROD_DB") == "1":
        return

    # 检查调用栈
    stack = traceback.extract_stack()
    for frame in stack:
        # 测试框架
        if "conftest" in frame.filename or "test_" in frame.filename:
            return
        # API 正常请求路径（get_db 是 FastAPI 依赖注入入口）
        if frame.name == "get_db":
            return

    # 到这里说明是生产环境下的直接 ORM 调用（脚本/命令行）
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
