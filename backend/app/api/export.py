# Data export endpoints
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
import csv
from io import StringIO

from app.database import get_db
from app.models import Room, Payment, UtilityReading
from app.core.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/utility-readings")
async def export_utility_readings(
    start_date: str = None,
    end_date: str = None,
    room_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export utility readings to CSV format.
    Query params:
    - start_date: Start date filter (YYYY-MM-DD)
    - end_date: End date filter (YYYY-MM-DD)
    - room_id: Filter by room ID
    """
    query = db.query(UtilityReading)

    if start_date:
        query = query.filter(UtilityReading.reading_date >= start_date)
    if end_date:
        query = query.filter(UtilityReading.reading_date <= end_date)
    if room_id:
        query = query.filter(UtilityReading.room_id == room_id)

    readings = query.order_by(UtilityReading.reading_date.desc(), UtilityReading.room_id).all()

    # Create CSV
    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        '房间号', '抄表日期', '类型', '上次读数', '本次读数', '用量',
        '单价', '金额', '备注', '创建时间'
    ])

    # Data rows
    for reading in readings:
        room = db.query(Room).filter(Room.id == reading.room_id).first()
        room_number = room.room_number if room else f"房间{reading.room_id}"

        writer.writerow([
            room_number,
            reading.reading_date,
            '水' if reading.utility_type == 'water' else '电',
            reading.previous_reading,
            reading.reading,
            reading.usage,
            reading.rate,
            f"{reading.amount or 0:.2f}",
            reading.notes or '',
            reading.created_at.strftime('%Y-%m-%d %H:%M:%S') if reading.created_at else ''
        ])

    # Generate filename
    filename = f"utility_readings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/payments")
async def export_payments(
    start_date: str = None,
    end_date: str = None,
    room_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export payment records to CSV format.
    Query params:
    - start_date: Start date filter (YYYY-MM-DD)
    - end_date: End date filter (YYYY-MM-DD)
    - room_id: Filter by room ID
    """
    query = db.query(Payment)

    if start_date:
        query = query.filter(Payment.payment_date >= start_date)
    if end_date:
        query = query.filter(Payment.payment_date <= end_date)
    if room_id:
        query = query.filter(Payment.room_id == room_id)

    payments = query.order_by(Payment.payment_date.desc()).all()

    # Create CSV
    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        '房间号', '收款日期', '房租', '水费', '电费', '总金额',
        '收款方式', '备注', '创建时间'
    ])

    # Data rows
    for payment in payments:
        room = db.query(Room).filter(Room.id == payment.room_id).first()
        room_number = room.room_number if room else f"房间{payment.room_id}"

        # Extract utility charges
        water_amount = 0
        electricity_amount = 0

        if payment.utility_charges:
            for charge in payment.utility_charges:
                if charge.utility_type == 'water':
                    water_amount = charge.amount or 0
                elif charge.utility_type == 'electricity':
                    electricity_amount = charge.amount or 0

        total = (payment.amount or 0) + water_amount + electricity_amount

        writer.writerow([
            room_number,
            payment.payment_date,
            f"{payment.amount or 0:.2f}",
            f"{water_amount:.2f}",
            f"{electricity_amount:.2f}",
            f"{total:.2f}",
            payment.payment_method,
            payment.notes or '',
            payment.created_at.strftime('%Y-%m-%d %H:%M:%S') if payment.created_at else ''
        ])

    # Generate filename
    filename = f"payments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/rooms")
async def export_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export room information to CSV format.
    """
    rooms = db.query(Room).order_by(Room.room_number).all()

    # Create CSV
    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        '房间号', '楼层', '月租金', '付款周期（月）', '租约开始', '租约结束',
        '上次付款日期', '水费率', '电费率', '状态', '创建时间'
    ])

    # Data rows
    for room in rooms:
        status = '已租' if room.is_occupied else '空置'

        writer.writerow([
            room.room_number,
            room.floor,
            f"{room.monthly_rent:.2f}",
            room.payment_cycle,
            room.lease_start,
            room.lease_end,
            room.last_payment_date or '',
            f"{room.water_rate:.2f}",
            f"{room.electricity_rate:.2f}",
            status,
            room.created_at.strftime('%Y-%m-%d %H:%M:%S') if room.created_at else ''
        ])

    # Generate filename
    filename = f"rooms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
