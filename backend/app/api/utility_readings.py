"""
水电抄表管理 API 路由
"""
from typing import Optional
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.core.deps import get_db, get_current_user
from app.core.permissions import apply_utility_reading_filter
from app.models import User, UtilityReading, Room
from app.schemas import (
    UtilityReadingCreate, UtilityReadingUpdate, UtilityReadingResponse,
    BatchUtilityReadingCreate, BatchUtilityReadingResponse, PaginatedResponse
)
from app.service.business import create_utility_reading, get_previous_reading

router = APIRouter(prefix="/utility/readings", tags=["utility-readings"])


def check_utility_permission(user: User):
    """检查水电权限"""
    if user.role == "tenant":
        raise HTTPException(status_code=403, detail="租客无权操作")
    return True


@router.get("", response_model=PaginatedResponse[UtilityReadingResponse])
def list_utility_readings(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    room_id: Optional[int] = None,
    utility_type: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    sort_by: str = "created_at",  # 改为按创建时间排序，更准确
    order: str = "desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取水电抄表记录列表

    支持分页、筛选和排序

    默认按创建时间降序排序（最新的在前）
    """
    query = db.query(UtilityReading)

    # 用户权限过滤（房东姐姐可以看到所有，其他房东只能看到自己的）
    query = apply_utility_reading_filter(query, current_user)

    # 筛选
    if room_id:
        query = query.filter(UtilityReading.room_id == room_id)
    if utility_type:
        query = query.filter(UtilityReading.utility_type == utility_type)
    if start_date:
        query = query.filter(UtilityReading.reading_date >= start_date)
    if end_date:
        query = query.filter(UtilityReading.reading_date <= end_date)

    # 排序 - 使用白名单验证
    ALLOWED_SORT_FIELDS = {
        'reading_date', 'reading', 'amount', 'usage', 'utility_type', 'created_at', 'id'
    }
    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = 'created_at'  # 默认按创建时间排序
    sort_column = getattr(UtilityReading, sort_by, UtilityReading.created_at)
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # 分页
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }


@router.get("/{reading_id}", response_model=UtilityReadingResponse)
def get_utility_reading(
    reading_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取水电抄表记录详情
    """
    reading = db.query(UtilityReading).filter(UtilityReading.id == reading_id).first()
    if not reading:
        raise HTTPException(status_code=404, detail="抄表记录不存在")
    
    # 租客只能查看自己房间的抄表
    if current_user.role == "tenant":
        if reading.room.tenant_name != current_user.full_name:
            raise HTTPException(status_code=403, detail="无权查看此抄表记录")
    
    return reading


@router.post("", response_model=UtilityReadingResponse, status_code=201)
async def create_utility_reading_record(
    reading_data: UtilityReadingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建水电抄表记录

    自动执行：
    1. 查询上次读数
    2. 查询有效费率
    3. 计算用量和费用
    4. 冗余存储相关数据
    5. 如果水和电都已录入，自动发送微信收租通知
    """
    check_utility_permission(current_user)

    try:
        # 获取房间信息（用于获取正确的owner_id）
        room = db.query(Room).filter(Room.id == reading_data.room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="房间不存在")
        
        reading = create_utility_reading(
            db,
            room_id=reading_data.room_id,
            utility_type=reading_data.utility_type,
            reading=reading_data.reading,
            reading_date=reading_data.reading_date,
            recorded_by=current_user.id,
            notes=reading_data.notes,
            owner_id=room.owner_id  # 设置为房间的owner_id，而不是当前用户
        )

        # 检查是否需要发送微信通知（2501开头的房间不发送水电通知）
        if room and not room.room_number.startswith('2501'):
            from app.utils.wechat import check_if_both_utilities_recorded, generate_rent_notification, send_wechat_message

            # 检查水和电是否都已录入
            utility_status = check_if_both_utilities_recorded(
                db,
                reading_data.room_id,
                reading_data.reading_date
            )

            # 如果水和电都已录入，发送微信通知（无需租客姓名检查）
            if utility_status['both_recorded']:
                # 如果没有租客姓名，使用房间号代替
                tenant_name = room.tenant_name or room.room_number
                message = generate_rent_notification(
                    room_number=room.room_number,
                    tenant_name=tenant_name,
                    monthly_rent=float(room.monthly_rent),
                    water_amount=utility_status['water_amount'],
                    electricity_amount=utility_status['electricity_amount'],
                    water_reading=utility_status['water_reading'],
                    electricity_reading=utility_status['electricity_reading'],
                    water_usage=utility_status.get('water_usage', 0),
                    electricity_usage=utility_status.get('electricity_usage', 0),
                    last_month_data=utility_status.get('last_month'),
                    include_utilities=True
                )

                # 异步发送微信消息（不阻塞响应）
                try:
                    await send_wechat_message(message)
                except Exception as e:
                    # 发送失败不影响数据保存，只记录日志
                    print(f"[Warning] Failed to send WeChat message: {str(e)}")

        return reading
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{reading_id}", response_model=UtilityReadingResponse)
async def update_utility_reading(
    reading_id: int,
    reading_data: UtilityReadingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新水电抄表记录

    允许更新：
    - reading: 读数（允许修改，但需要重新计算费用）
    - notes: 备注

    更新后检查水和电是否都已录入，如果都已录入则发送催收消息
    """
    check_utility_permission(current_user)

    reading = db.query(UtilityReading).filter(UtilityReading.id == reading_id).first()
    if not reading:
        raise HTTPException(status_code=404, detail="抄表记录不存在")

    # 更新读数（如果提供）
    if hasattr(reading_data, 'reading') and reading_data.reading is not None:
        old_reading = reading.reading
        reading.reading = reading_data.reading

        # 重新计算用量和费用
        if reading.previous_reading is not None:
            reading.usage = reading.reading - reading.previous_reading
            # 费用已经存储，保持不变或根据需要重新计算
        else:
            reading.usage = None

    # 更新备注（如果提供）
    if hasattr(reading_data, 'notes') and reading_data.notes is not None:
        reading.notes = reading_data.notes

    db.commit()
    db.refresh(reading)

    # 检查是否需要发送催收消息
    # 查询同一房间、同一日期的水电记录
    room = db.query(Room).filter(Room.id == reading.room_id).first()
    if room:
        from app.utils.wechat import check_if_both_utilities_recorded, generate_rent_notification, send_wechat_message

        result = check_if_both_utilities_recorded(
            db, reading.room_id, reading.reading_date
        )
        water_reading = result.get('water_reading')
        electricity_reading = result.get('electricity_reading')

        # 如果水和电都已录入，发送催收消息
        if water_reading and electricity_reading:
            try:
                # 获取房间号
                room_number = room.room_number
                monthly_rent = room.monthly_rent or 0

                # 从result中获取费用和读数信息
                water_amount = result.get('water_amount', 0)
                electricity_amount = result.get('electricity_amount', 0)
                water_reading_value = result.get('water_reading', 0)
                electricity_reading_value = result.get('electricity_reading', 0)
                water_usage = result.get('water_usage', 0)
                electricity_usage = result.get('electricity_usage', 0)

                # 查询实际的水电记录对象以获取previous_reading
                from app.models import UtilityReading
                water_record = db.query(UtilityReading).filter(
                    UtilityReading.room_id == reading.room_id,
                    UtilityReading.utility_type == 'water',
                    UtilityReading.reading_date == reading.reading_date
                ).first()
                electricity_record = db.query(UtilityReading).filter(
                    UtilityReading.room_id == reading.room_id,
                    UtilityReading.utility_type == 'electricity',
                    UtilityReading.reading_date == reading.reading_date
                ).first()

                # 生成消息（使用正确的参数）
                message = generate_rent_notification(
                    room_number=room_number,
                    tenant_name=room.tenant_name or "租户",
                    monthly_rent=float(monthly_rent),
                    water_amount=float(water_amount),
                    electricity_amount=float(electricity_amount),
                    water_reading=float(water_reading_value),
                    electricity_reading=float(electricity_reading_value),
                    water_usage=float(water_usage),
                    electricity_usage=float(electricity_usage),
                    last_month_data=result.get('last_month')
                )

                # 异步发送飞书消息（不阻塞响应）
                await send_wechat_message(message)
            except Exception as e:
                # 发送失败不影响数据保存，只记录日志
                print(f"[Warning] Failed to send notification: {str(e)}")
                import traceback
                traceback.print_exc()

    return reading


@router.delete("/{reading_id}", status_code=204)
def delete_utility_reading(
    reading_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除水电抄表记录
    """
    check_utility_permission(current_user)
    
    reading = db.query(UtilityReading).filter(UtilityReading.id == reading_id).first()
    if not reading:
        raise HTTPException(status_code=404, detail="抄表记录不存在")
    
    db.delete(reading)
    db.commit()
    
    return None


@router.post("/batch", response_model=BatchUtilityReadingResponse, status_code=201)
async def batch_create_utility_readings(
    batch_data: BatchUtilityReadingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量创建水电抄表记录
    
    接收多个房间的水电读数，统一创建记录
    
    自动执行：
    1. 查询上次读数
    2. 查询有效费率
    3. 计算用量和费用
    4. 冗余存储相关数据
    """
    check_utility_permission(current_user)
    
    success_count = 0
    failed_count = 0
    total_amount = Decimal('0')
    created_readings = []
    errors = []
    
    for reading_data in batch_data.readings:
        try:
            # 创建水电记录
            reading = create_utility_reading(
                db,
                room_id=reading_data.room_id,
                utility_type=reading_data.utility_type,
                reading=reading_data.reading,
                reading_date=batch_data.reading_date,  # 使用统一的日期
                recorded_by=current_user.id,
                notes=batch_data.notes or reading_data.notes,  # 优先使用统一备注
                owner_id=current_user.id
            )
            
            success_count += 1
            created_readings.append(reading)
            if reading.amount:
                total_amount += reading.amount
                
        except Exception as e:
            failed_count += 1
            errors.append(f"房间{reading_data.room_id} {reading_data.utility_type}: {str(e)}")
    
    # 检查是否有需要发送微信通知的房间
    # 找出同时录入水和电的房间
    room_ids = list(set(r.room_id for r in created_readings))
    for room_id in room_ids:
        room = db.query(Room).filter(Room.id == room_id).first()
        
        # 跳过2501系列房间
        if not room or room.room_number.startswith('2501'):
            continue
            
        # 检查水和电是否都已录入
        from app.utils.wechat import check_if_both_utilities_recorded, generate_rent_notification, send_wechat_message
        
        utility_status = check_if_both_utilities_recorded(
            db,
            room_id,
            batch_data.reading_date
        )
        
        if utility_status['both_recorded']:
            tenant_name = room.tenant_name or room.room_number
            message = generate_rent_notification(
                room_number=room.room_number,
                tenant_name=tenant_name,
                monthly_rent=float(room.monthly_rent),
                water_amount=utility_status['water_amount'],
                electricity_amount=utility_status['electricity_amount'],
                water_reading=utility_status['water_reading'],
                electricity_reading=utility_status['electricity_reading'],
                include_utilities=True
            )
            
            # 异步发送微信消息
            try:
                await send_wechat_message(message)
            except Exception as e:
                print(f"[Warning] Failed to send WeChat message: {str(e)}")
    
    return BatchUtilityReadingResponse(
        success_count=success_count,
        failed_count=failed_count,
        total_amount=total_amount,
        readings=created_readings,
        errors=errors
    )


@router.get("/previous/{room_id}/{utility_type}")
def get_previous_reading_info(
    room_id: int,
    utility_type: str,
    before_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取某房间某类型的上次读数
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    
    # 租客只能查看自己房间的读数
    if current_user.role == "tenant":
        if room.tenant_name != current_user.full_name:
            raise HTTPException(status_code=403, detail="无权查看此房间信息")
    
    if before_date is None:
        before_date = date.today()
    
    previous = get_previous_reading(db, room_id, utility_type, before_date)
    
    return {
        "room_id": room_id,
        "utility_type": utility_type,
        "previous_reading": previous,
        "before_date": before_date
    }


@router.post("/send-wechat-notification")
def send_wechat_notification(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    发送微信收租通知
    """
    from app.utils.wechat import send_wechat_webhook

    room_id = payload.get("room_id")
    reading_date = payload.get("reading_date")
    message = payload.get("message", "")

    if not room_id or not reading_date:
        raise HTTPException(status_code=400, detail="缺少必要参数")

    # 发送到微信
    try:
        send_wechat_webhook(message)
        return {"success": True, "message": "微信通知发送成功"}
    except Exception as e:
        logger.error(f"发送微信通知失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"发送微信通知失败: {str(e)}")
