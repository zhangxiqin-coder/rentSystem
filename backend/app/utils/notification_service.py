"""
Centralized notification service - eliminates duplicated notification logic
"""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Room
from app.utils.wechat import (
    check_if_both_utilities_recorded,
    generate_rent_notification,
    send_wechat_message,
)


async def send_rent_notification_if_complete(
    db: Session,
    room: Room,
    reading_date: date,
    include_utilities: bool = True,
) -> dict:
    """
    Send rent notification if conditions are met.

    1. Skip 2501 rooms (when include_utilities=True)
    2. Check both water and electricity recorded (when include_utilities=True)
    3. Generate notification message
    4. Send via wechat/feishu

    Returns:
        {"sent": bool, "reason": str}
    """
    try:
        if include_utilities and room.room_number.startswith('2501'):
            return {"sent": False, "reason": "2501 room skipped"}

        tenant_name = room.tenant_name or room.room_number

        if include_utilities:
            utility_status = check_if_both_utilities_recorded(
                db, room.id, reading_date
            )

            if not utility_status['both_recorded']:
                return {"sent": False, "reason": "Both utilities not yet recorded"}

            message = generate_rent_notification(
                room_number=room.room_number,
                tenant_name=tenant_name,
                monthly_rent=float(room.monthly_rent),
                payment_cycle=room.payment_cycle or 1,
                water_amount=utility_status['water_amount'],
                electricity_amount=utility_status['electricity_amount'],
                water_reading=utility_status['water_reading'],
                electricity_reading=utility_status['electricity_reading'],
                water_usage=utility_status.get('water_usage', 0),
                electricity_usage=utility_status.get('electricity_usage', 0),
                last_month_data=utility_status.get('last_month'),
                include_utilities=True,
            )
        else:
            message = generate_rent_notification(
                room_number=room.room_number,
                tenant_name=tenant_name,
                monthly_rent=float(room.monthly_rent),
                payment_cycle=room.payment_cycle or 1,
                include_utilities=False,
            )

        await send_wechat_message(message)
        return {"sent": True, "reason": "Notification sent"}

    except Exception as e:
        print(f"[Warning] Failed to send rent notification for {room.room_number}: {e}")
        return {"sent": False, "reason": "Send failed", "error": str(e)}
