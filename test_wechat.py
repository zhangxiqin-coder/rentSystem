#!/usr/bin/env python3
"""
测试微信发送功能
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.expanduser('~/rent-management-system/backend'))
sys.path.insert(0, os.path.expanduser('~/.hermes'))

from app.utils.wechat import send_wechat_message, generate_rent_notification


async def test_wechat_send():
    """测试微信发送"""
    print("=" * 50)
    print("测试微信发送功能")
    print("=" * 50)

    # 生成测试消息
    test_message = """🏠 收租通知

📦 房号：102
👤 租客：测试租客

🏠 房租：¥1500.00

💧 水费
   读数：358 吨
   费用：¥45.00

⚡ 电费
   读数：12551 度
   费用：¥230.50

💰 总计
   应付：¥1775.50

请及时缴纳房租，感谢配合！"""

    print("\n发送的消息内容：")
    print("-" * 50)
    print(test_message)
    print("-" * 50)

    print("\n正在发送...")
    result = await send_wechat_message(test_message)

    print("\n发送结果：")
    print(f"  成功: {result.get('success')}")
    print(f"  消息: {result.get('message')}")

    if result.get('success'):
        print("\n✅ 微信发送测试成功！")
    else:
        print(f"\n❌ 微信发送测试失败: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(test_wechat_send())
