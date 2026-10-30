"""
Centralized notification service - eliminates duplicated notification logic
"""
from datetime import date, timedelta
from typing import Optional
from dateutil.relativedelta import relativedelta

from sqlalchemy.orm import Session

from app.models import Room, Payment, Tenant
from app.utils import lease_grid
from app.utils.wechat import (
    check_if_both_utilities_recorded,
    generate_rent_notification,
    send_wechat_message,
)


def _is_tenant_notify_restricted(db: Session, room: Room) -> tuple[bool, str]:
    """
    检查房间关联租客是否有通知日期限制（notify_after_day）。
    返回 (是否被限制, 原因说明)。
    被限制 = 今天还没到该租客约定的可通知日期。
    """
    if not room.tenant_id:
        return (False, "")

    tenant = db.query(Tenant).filter(Tenant.id == room.tenant_id).first()
    if not tenant or tenant.notify_after_day is None:
        return (False, "")

    today_day = date.today().day
    if today_day < tenant.notify_after_day:
        return (True, f"租客{tenant.name}约定每月{tenant.notify_after_day}号后才通知")

    return (False, "")


def _has_paid_for_target_cycle(db: Session, room: Room, cycle: int) -> bool:
    """
    判断当前应收期是否已付（v5 起租日网格引擎，2026-10-02）。

    口径（用户裁决）：应收日从 lease_start 按周期推网格，付款不改变期界；
    付款落在 [期初-14天, 下期初) 内抵付该期。租客惯常提前2-5天预付，
    分配时优先抵付前方14天内即将开始的期。月付同样参与判定。

    引擎：app/utils/lease_grid.py（与 business.py、前端 paymentCycle.ts 一致）。

    历史：
    - v3 ±14天固定窗口：收款日漂移>14天必误判（2-2501-A 事故）。
    - v4 支付锚定：应收日随付款日漂移，2026-10-02 用户否决；且月付
      被排除在判定外（302-4 刚交完仍显示"即将到期"）。
    """
    if not room.lease_start:
        return False  # 无租约开始日，默认未付

    today = date.today()

    # 空置/转租空窗期房间（2026-10-28 302-1 案例）：老租客已退、新租约
    # 未来才生效，此刻没有应收房租，水电通知只含水电。
    room_status = getattr(room, "status", None)
    if room_status and room_status != 'occupied':
        return False

    # 本租约期内有效 rent 实付（换租隔离：起租日前>14天的旧款不算）
    earliest = room.lease_start - timedelta(days=lease_grid.EARLY_PAY_DAYS)
    rows = db.query(Payment.payment_date).filter(
        Payment.room_id == room.id,
        Payment.payment_type == 'rent',
        Payment.status != 'cancelled',
        Payment.payment_date >= earliest,
    ).all()
    pay_dates = [r[0] for r in rows if r[0]]

    paid_through = lease_grid.is_paid_through(
        room.lease_start, cycle, pay_dates, today,
    )
    if not paid_through:
        return False  # 已欠租 → 该催，含房租

    # 已付但应收日临近：进入提前收租窗口（≤EARLY_PAY_DAYS 天）也该催。
    # 租客惯常提前 2-5 天预付（102-2 案例：11-02 到期、10-28 录水电时
    # 催租消息必须含下季度房租；旧逻辑判"已付"把房租行吃掉了）。
    nd = lease_grid.next_due_date(room.lease_start, cycle, pay_dates, today)
    if nd is not None and 0 <= (nd - today).days <= lease_grid.EARLY_PAY_DAYS:
        return False  # 即将到期 → 该催，含房租

    return True


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
    3. For quarterly+ rooms, check if rent already collected this cycle
    4. Generate notification message
    5. Send via wechat/feishu

    Returns:
        {"sent": bool, "reason": str}
    """
    try:
        if include_utilities and room.room_number.startswith('2501'):
            return {"sent": False, "reason": "2501 room skipped"}

        # 检查租客通知日期限制
        restricted, reason = _is_tenant_notify_restricted(db, room)
        if restricted:
            return {"sent": False, "reason": reason}

        tenant_name = room.tenant_name or room.room_number
        cycle = max(1, room.payment_cycle or 1)

        # 判断是否需要包含房租：v5 网格引擎判定当前期是否已付
        # （月付也参与——302-4 刚交完仍被催就是旧版把月付排除所致）
        include_rent = not _has_paid_for_target_cycle(db, room, cycle)

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
                payment_cycle=cycle,
                water_amount=utility_status['water_amount'],
                electricity_amount=utility_status['electricity_amount'],
                water_reading=utility_status['water_reading'],
                electricity_reading=utility_status['electricity_reading'],
                water_usage=utility_status.get('water_usage', 0),
                electricity_usage=utility_status.get('electricity_usage', 0),
                last_month_data=utility_status.get('last_month'),
                include_utilities=True,
                include_rent=include_rent,
            )
        else:
            message = generate_rent_notification(
                room_number=room.room_number,
                tenant_name=tenant_name,
                monthly_rent=float(room.monthly_rent),
                payment_cycle=cycle,
                include_utilities=False,
                include_rent=include_rent,
            )

        await send_wechat_message(message)
        return {"sent": True, "reason": "Notification sent"}

    except Exception as e:
        print(f"[Warning] Failed to send rent notification for {room.room_number}: {e}")
        return {"sent": False, "reason": "Send failed", "error": str(e)}
