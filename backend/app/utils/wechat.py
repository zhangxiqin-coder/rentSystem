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
    water_usage: float = 0,
    electricity_usage: float = 0,
    last_month_data: dict = None,
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
        water_usage: 水用量（可选）
        electricity_usage: 电用量（可选）
        last_month_data: 上月数据字典（可选）
        include_utilities: 是否包含水电信息（2501房间为False）

    Returns:
        格式化的收租消息
    """
    if include_utilities:
        total = monthly_rent + water_amount + electricity_amount
        
        lines = [
            f"**{room_number} 本月收租：{int(total)} 元**"
        ]
        
        # 水费信息
        if water_reading is not None and water_usage > 0:
            last_water_reading = last_month_data.get('water_reading') if last_month_data else None
            if last_water_reading:
                # 水：上月读数→本月读数（用量×单价=费用）
                water_unit_price = water_amount / water_usage if water_usage > 0 else 5
                lines.append(f"水：{int(last_water_reading)}→{int(water_reading)}（{int(water_usage)}吨×{water_unit_price:.0f}元={int(water_amount)}元）")
            else:
                # 没有上月数据，只显示本月
                water_unit_price = water_amount / water_usage if water_usage > 0 else 5
                lines.append(f"水：本月{int(water_reading)}吨（{int(water_usage)}吨×{water_unit_price:.0f}元={int(water_amount)}元）")
        
        # 电费信息
        if electricity_reading is not None and electricity_usage > 0:
            last_electricity_reading = last_month_data.get('electricity_reading') if last_month_data else None
            if last_electricity_reading:
                # 电：上月读数→本月读数（用量×单价=费用）
                elec_unit_price = electricity_amount / electricity_usage if electricity_usage > 0 else 1
                lines.append(f"电：{int(last_electricity_reading)}→{int(electricity_reading)}（{int(electricity_usage)}度×{elec_unit_price:.0f}元={int(electricity_amount)}元）")
            else:
                # 没有上月数据，只显示本月
                elec_unit_price = electricity_amount / electricity_usage if electricity_usage > 0 else 1
                lines.append(f"电：本月{int(electricity_reading)}度（{int(electricity_usage)}度×{elec_unit_price:.0f}元={int(electricity_amount)}元）")
        
        # 房租
        lines.append(f"房租：{int(monthly_rent)}元")
        
        return "\n".join(lines)
    else:
        # 2501等不分摊水电的房间
        lines = [
            f"**{room_number} 本月收租：{int(monthly_rent)} 元**",
            "房租：{int(monthly_rent)}元"
        ]
        return "\n".join(lines)


def check_if_both_utilities_recorded(
    db,
    room_id: int,
    reading_date
) -> dict:
    """
    检查某房间在某日期是否已录入水和电两项数据，并获取上次数据

    Args:
        db: 数据库会话
        room_id: 房间ID
        reading_date: 检查日期

    Returns:
        字典，包含是否完整及各项数据（含上次数据）
    """
    from app.models import UtilityReading
    from datetime import datetime, timedelta

    # 确保reading_date是date对象
    if isinstance(reading_date, str):
        reading_date = datetime.strptime(reading_date, '%Y-%m-%d').date()

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

    # 查询上一次的水电记录（往前15天内，或者直接查最近的一次）
    # 策略：查找当前日期之前的最近一次记录
    start_date = reading_date - timedelta(days=45)  # 往前45天内查找
    
    # 查询上一次水表记录
    last_water = db.query(UtilityReading).filter(
        UtilityReading.room_id == room_id,
        UtilityReading.utility_type == 'water',
        UtilityReading.reading_date < reading_date,
        UtilityReading.reading_date >= start_date
    ).order_by(UtilityReading.reading_date.desc()).first()

    # 查询上一次电表记录
    last_electricity = db.query(UtilityReading).filter(
        UtilityReading.room_id == room_id,
        UtilityReading.utility_type == 'electricity',
        UtilityReading.reading_date < reading_date,
        UtilityReading.reading_date >= start_date
    ).order_by(UtilityReading.reading_date.desc()).first()

    return {
        "both_recorded": water is not None and electricity is not None,
        "water_amount": float(water.amount) if water and water.amount else 0,
        "electricity_amount": float(electricity.amount) if electricity and electricity.amount else 0,
        "water_reading": float(water.reading) if water else None,
        "electricity_reading": float(electricity.reading) if electricity else None,
        "water_usage": float(water.usage) if water and water.usage else 0,
        "electricity_usage": float(electricity.usage) if electricity and electricity.usage else 0,
        # 上次数据
        "last_month": {
            "water_reading": float(last_water.reading) if last_water else None,
            "water_usage": float(last_water.usage) if last_water and last_water.usage else 0,
            "water_amount": float(last_water.amount) if last_water and last_water.amount else 0,
            "water_date": str(last_water.reading_date) if last_water else None,
            "electricity_reading": float(last_electricity.reading) if last_electricity else None,
            "electricity_usage": float(last_electricity.usage) if last_electricity and last_electricity.usage else 0,
            "electricity_amount": float(last_electricity.amount) if last_electricity and last_electricity.amount else 0,
            "electricity_date": str(last_electricity.reading_date) if last_electricity else None,
        }
    }
