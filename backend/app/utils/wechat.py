"""
WeChat message sending utility
"""
import os
import requests
import json
from typing import Optional


def send_wechat_webhook(message: str, webhook_url: str = None) -> dict:
    """
    将消息保存到队列，等待Hermes定时任务发送

    Args:
        message: 消息内容
        webhook_url: 忽略此参数（保留兼容性）

    Returns:
        dict with status and result info
    """
    try:
        import json
        from datetime import datetime
        import os

        # 消息队列目录
        queue_dir = os.path.expanduser('~/.hermes/wechat_queue')
        os.makedirs(queue_dir, exist_ok=True)

        # 保存消息到队列文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        queue_file = os.path.join(queue_dir, f'msg_{timestamp}.json')

        with open(queue_file, 'w', encoding='utf-8') as f:
            json.dump({
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'target': 'feishu'  # 改为飞书
            }, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "message": "消息已加入发送队列（飞书）",
            "queue_file": queue_file
        }

    except Exception as e:
        # 如果保存到队列失败，尝试使用企业微信webhook
        url = webhook_url or os.getenv('WECHAT_WEBHOOK_URL')

        if not url:
            return {
                "success": False,
                "message": f"保存队列失败且未配置webhook: {str(e)}",
                "error": str(e)
            }

        # 构建企业微信消息格式
        data = {
            "msgtype": "text",
            "text": {
                "content": message
            }
        }

        # 发送请求
        response = requests.post(
            url,
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            if result.get('errcode') == 0:
                return {
                    "success": True,
                    "message": "消息发送成功",
                    "result": result
                }
            else:
                return {
                    "success": False,
                    "message": f"微信API返回错误: {result.get('errmsg')}",
                    "error": result
                }
        else:
            return {
                "success": False,
                "message": f"HTTP请求失败: {response.status_code}",
                "error": response.text
            }


async def send_wechat_message(message: str, user_id: str = None) -> dict:
    """
    发送微信消息（兼容接口）

    优先级：
    1. 尝试使用配置的webhook
    2. 如果失败，打印日志（开发环境）

    Args:
        message: 消息内容
        user_id: 用户ID（暂未使用）

    Returns:
        dict with status and result info
    """
    # 尝试使用webhook发送
    result = send_wechat_webhook(message)

    if result['success']:
        print(f"[WeChat] ✓ 消息已发送到微信群")
        return result
    else:
        # 如果webhook未配置或失败，打印日志（不阻塞业务）
        print(f"[WeChat] Webhook发送失败: {result['message']}")
        print(f"[WeChat] 消息内容预览: {message[:100]}...")

        # 开发环境：返回成功（不阻塞数据保存）
        # 生产环境：应该配置webhook
        return {
            "success": True,  # 返回成功以不阻塞业务
            "message": "消息已记录（webhook未配置）",
            "logged": True,
            "preview": message[:200]
        }


def generate_rent_notification(
    room_number: str,
    tenant_name: str,
    monthly_rent: float,
    water_amount: float = 0,
    electricity_amount: float = 0,
    water_reading: float = None,
    electricity_reading: float = None,
    include_utilities: bool = True
) -> str:
    """
    生成收租通知消息

    Args:
        room_number: 房号
        tenant_name: 租客姓名
        monthly_rent: 月租金
        water_amount: 水费金额
        electricity_amount: 电费金额
        water_reading: 水表读数（可选）
        electricity_reading: 电表读数（可选）
        include_utilities: 是否包含水电信息（2501房间为False）

    Returns:
        格式化的收租消息
    """
    lines = [
        "🏠 收租通知",
        f"",
        f"📦 房号：{room_number}",
        f"👤 租客：{tenant_name}",
        f"",
        f"🏠 房租：¥{monthly_rent:.2f}"
    ]

    if include_utilities:
        total = monthly_rent + water_amount + electricity_amount

        lines.append("")
        lines.append("💧 水费")
        if water_reading is not None:
            lines.append(f"   读数：{water_reading} 吨")
        lines.append(f"   费用：¥{water_amount:.2f}")

        lines.append("")
        lines.append("⚡ 电费")
        if electricity_reading is not None:
            lines.append(f"   读数：{electricity_reading} 度")
        lines.append(f"   费用：¥{electricity_amount:.2f}")

        lines.append("")
        lines.append("💰 总计")
        lines.append(f"   应付：¥{total:.2f}")
    else:
        lines.append("")
        lines.append("💰 水电已分摊，仅收房租")
        lines.append(f"   应付：¥{monthly_rent:.2f}")

    lines.append("")
    lines.append("请及时缴纳房租，感谢配合！")

    return "\n".join(lines)


def check_if_both_utilities_recorded(
    db,
    room_id: int,
    reading_date
) -> dict:
    """
    检查某房间在某日期是否已录入水和电两项数据

    Args:
        db: 数据库会话
        room_id: 房间ID
        reading_date: 检查日期

    Returns:
        字典，包含是否完整及各项数据
    """
    from app.models import UtilityReading

    # 查询当天的水表记录
    water = db.query(UtilityReading).filter(
        UtilityReading.room_id == room_id,
        UtilityReading.utility_type == 'water',
        UtilityReading.reading_date == reading_date
    ).first()

    # 查询当天的电表记录
    electricity = db.query(UtilityReading).filter(
        UtilityReading.room_id == room_id,
        UtilityReading.utility_type == 'electricity',
        UtilityReading.reading_date == reading_date
    ).first()

    return {
        "both_recorded": water is not None and electricity is not None,
        "water_amount": float(water.amount) if water and water.amount else 0,
        "electricity_amount": float(electricity.amount) if electricity and electricity.amount else 0,
        "water_reading": float(water.reading) if water else None,
        "electricity_reading": float(electricity.reading) if electricity else None
    }
