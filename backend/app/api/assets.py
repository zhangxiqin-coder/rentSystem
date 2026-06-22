"""
个人资产管理API
支持两种上报方式：
1. 余额上报：平台名 + 当前余额 + 累计收益 → 自动算出转入/转出净额
2. 转入/转出：平台名 + 金额 → 自动更新当前余额
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models import AssetPlatform, AssetRecord, User
from app.schemas import (
    AssetPlatformCreate, AssetPlatformUpdate, AssetPlatformResponse,
    AssetPlatformDetailResponse, AssetRecordResponse, AssetRecordCreate,
    AssetSummaryResponse
)
from app.core.deps import get_current_user

router = APIRouter()


def _get_platform_or_404(db: Session, platform_id: int, user_id: int) -> AssetPlatform:
    """获取平台并校验归属"""
    platform = db.query(AssetPlatform).filter(
        AssetPlatform.id == platform_id,
        AssetPlatform.owner_id == user_id
    ).first()
    if not platform:
        raise HTTPException(status_code=404, detail="平台不存在")
    return platform


# ==================== 平台管理 ====================

@router.get("/assets/platforms", response_model=list[AssetPlatformResponse])
async def list_platforms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的所有资产平台"""
    return db.query(AssetPlatform).filter(
        AssetPlatform.owner_id == current_user.id,
        AssetPlatform.is_active == True
    ).order_by(AssetPlatform.sort_order, AssetPlatform.id).all()


@router.post("/assets/platforms", response_model=AssetPlatformResponse)
async def create_platform(
    data: AssetPlatformCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建资产平台"""
    platform = AssetPlatform(
        name=data.name,
        current_balance=data.current_balance,
        total_earnings=data.total_earnings,
        sort_order=data.sort_order,
        owner_id=current_user.id
    )
    db.add(platform)
    db.commit()
    db.refresh(platform)
    return platform


@router.put("/assets/platforms/{platform_id}", response_model=AssetPlatformResponse)
async def update_platform(
    platform_id: int,
    data: AssetPlatformUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新资产平台"""
    platform = _get_platform_or_404(db, platform_id, current_user.id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(platform, key, value)
    platform.updated_at = datetime.now()
    db.commit()
    db.refresh(platform)
    return platform


@router.delete("/assets/platforms/{platform_id}")
async def delete_platform(
    platform_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除资产平台（同时删除所有关联记录）"""
    platform = _get_platform_or_404(db, platform_id, current_user.id)
    # 删除关联记录
    db.query(AssetRecord).filter(AssetRecord.platform_id == platform_id).delete()
    db.delete(platform)
    db.commit()
    return {"message": "平台已删除"}


# ==================== 资产变动记录 ====================

@router.post("/assets/records", response_model=AssetRecordResponse)
async def create_asset_record(
    data: AssetRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建资产变动记录（包含余额上报和转入/转出两种模式）"""
    platform = _get_platform_or_404(db, data.platform_id, current_user.id)

    record = AssetRecord(
        platform_id=data.platform_id,
        owner_id=current_user.id,
        record_type=data.record_type,
        notes=data.notes,
        balance_before=platform.current_balance,
        earnings_before=platform.total_earnings
    )

    if data.record_type == "balance":
        # 余额上报模式
        if data.reported_balance is None or data.reported_earnings is None:
            raise HTTPException(status_code=400, detail="余额上报必须提供 reported_balance 和 reported_earnings")

        record.reported_balance = data.reported_balance
        record.reported_earnings = data.reported_earnings

        # 计算转入/转出净额 = (新余额 - 旧余额) - (新收益 - 旧收益)
        balance_diff = data.reported_balance - platform.current_balance
        earnings_diff = data.reported_earnings - platform.total_earnings
        record.calculated_transfer = balance_diff - earnings_diff

        # 更新平台数据
        platform.current_balance = data.reported_balance
        platform.total_earnings = data.reported_earnings

    elif data.record_type == "transfer_in":
        # 转入模式
        if data.amount is None or data.amount <= 0:
            raise HTTPException(status_code=400, detail="转入金额必须大于0")
        record.amount = data.amount
        record.calculated_transfer = data.amount
        platform.current_balance += data.amount

    elif data.record_type == "transfer_out":
        # 转出模式
        if data.amount is None or data.amount <= 0:
            raise HTTPException(status_code=400, detail="转出金额必须大于0")
        if data.amount > platform.current_balance:
            raise HTTPException(status_code=400, detail="转出金额不能超过当前余额")
        record.amount = data.amount
        record.calculated_transfer = -data.amount
        platform.current_balance -= data.amount

    else:
        raise HTTPException(status_code=400, detail=f"不支持的记录类型: {data.record_type}")

    record.balance_after = platform.current_balance
    record.earnings_after = platform.total_earnings
    platform.updated_at = datetime.now()

    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/assets/records", response_model=list[AssetRecordResponse])
async def list_asset_records(
    platform_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取资产变动记录"""
    query = db.query(AssetRecord).filter(AssetRecord.owner_id == current_user.id)
    if platform_id:
        query = query.filter(AssetRecord.platform_id == platform_id)
    records = query.order_by(AssetRecord.created_at.desc()).limit(limit).all()

    # 补充 platform_name
    result = []
    for r in records:
        resp = AssetRecordResponse.model_validate(r)
        if r.platform:
            resp.platform_name = r.platform.name
        result.append(resp)
    return result


# ==================== 资产总览 ====================

@router.get("/assets/summary", response_model=AssetSummaryResponse)
async def get_asset_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取资产总览（含各平台详情和记录）"""
    platforms = db.query(AssetPlatform).filter(
        AssetPlatform.owner_id == current_user.id,
        AssetPlatform.is_active == True
    ).order_by(AssetPlatform.sort_order, AssetPlatform.id).all()

    total_balance = Decimal('0')
    total_earnings = Decimal('0')
    platform_details = []

    for p in platforms:
        total_balance += (p.current_balance or Decimal('0'))
        total_earnings += (p.total_earnings or Decimal('0'))

        # 获取最近20条记录
        records = db.query(AssetRecord).filter(
            AssetRecord.platform_id == p.id
        ).order_by(AssetRecord.created_at.desc()).limit(20).all()

        record_responses = []
        for r in records:
            resp = AssetRecordResponse.model_validate(r)
            resp.platform_name = p.name
            record_responses.append(resp)

        detail = AssetPlatformDetailResponse(
            id=p.id,
            name=p.name,
            current_balance=p.current_balance or Decimal('0'),
            total_earnings=p.total_earnings or Decimal('0'),
            sort_order=p.sort_order,
            is_active=p.is_active,
            created_at=p.created_at,
            updated_at=p.updated_at,
            records=record_responses
        )
        platform_details.append(detail)

    return AssetSummaryResponse(
        total_balance=total_balance,
        total_earnings=total_earnings,
        platforms=platform_details
    )
