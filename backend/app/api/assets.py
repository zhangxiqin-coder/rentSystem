"""
个人资产管理API
支持两种上报方式：
1. 余额上报：平台名 + 当前余额 + 累计收益 → 自动算出转入/转出净额
2. 转入/转出：平台名 + 金额 → 自动更新当前余额

收益按年份管理：每年首次上报时自动归档上年收益，页面显示当年收益。
"""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db
from app.models import AssetPlatform, AssetRecord, User
from app.schemas import (
    AssetPlatformCreate, AssetPlatformUpdate, AssetPlatformResponse,
    AssetPlatformDetailResponse, AssetRecordResponse, AssetRecordCreate,
    AssetRecordUpdate,
    AssetSummaryResponse,
    AssetTrendResponse, AssetTrendPoint, PlatformTrendPoint,
    ZhaopingfeiYearSummary, ZhaopingfeiSummaryResponse
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


def _parse_yearly_earnings(platform: AssetPlatform) -> dict:
    """解析yearly_earnings JSON字段"""
    if not platform.yearly_earnings:
        return {}
    try:
        return json.loads(platform.yearly_earnings)
    except (json.JSONDecodeError, TypeError):
        return {}


def _save_yearly_earnings(platform: AssetPlatform, data: dict):
    """保存yearly_earnings JSON字段"""
    platform.yearly_earnings = json.dumps(data, ensure_ascii=False)


def _check_year_rollover(platform: AssetPlatform, db: Session):
    """检查是否需要跨年归档，如果是则归档上年收益"""
    current_year = datetime.now().year
    if current_year > (platform.current_year or 2026):
        # 跨年了！归档当前收益
        yearly = _parse_yearly_earnings(platform)
        year_key = str(platform.current_year)
        yearly[year_key] = str(platform.total_earnings or Decimal('0'))
        _save_yearly_earnings(platform, yearly)
        
        # 重置当前年份收益
        platform.total_earnings = Decimal('0')
        platform.current_year = current_year
        db.flush()


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
    current_year = datetime.now().year
    platform = AssetPlatform(
        name=data.name,
        current_balance=data.current_balance,
        total_earnings=Decimal('0'),
        current_year=current_year,
        yearly_earnings='{}',
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

    # 检查是否需要跨年归档
    _check_year_rollover(platform, db)

    record = AssetRecord(
        platform_id=data.platform_id,
        owner_id=current_user.id,
        record_type=data.record_type,
        notes=data.notes,
        balance_before=platform.current_balance,
        earnings_before=platform.total_earnings
    )

    if data.record_type == "balance":
        # 余额+收益上报模式（同时填余额和累计收益）
        if data.reported_balance is None or data.reported_earnings is None:
            raise HTTPException(status_code=400, detail="余额上报必须提供 reported_balance 和 reported_earnings")

        record.reported_balance = data.reported_balance
        record.reported_earnings = data.reported_earnings

        # 计算转入/转出净额 = (新余额 - 旧余额) - (新收益 - 旧收益)
        balance_diff = data.reported_balance - platform.current_balance
        earnings_diff = data.reported_earnings - platform.total_earnings
        record.calculated_transfer = balance_diff - earnings_diff

        # 更新平台数据（total_earnings存当年收益）
        platform.current_balance = data.reported_balance
        platform.total_earnings = data.reported_earnings

    elif data.record_type == "earnings":
        # 仅收益上报模式：填本次收益变化值，自动更新累计收益和余额
        if data.amount is None:
            raise HTTPException(status_code=400, detail="收益上报必须提供 amount（本次收益变化值）")
        new_earnings = platform.total_earnings + data.amount
        record.reported_earnings = new_earnings
        record.reported_balance = platform.current_balance + data.amount
        record.amount = data.amount
        record.calculated_transfer = Decimal('0')
        platform.total_earnings = new_earnings
        platform.current_balance = record.reported_balance

    elif data.record_type == "balance_only":
        # 仅余额上报模式：填余额，收益不变
        if data.reported_balance is None:
            raise HTTPException(status_code=400, detail="余额上报必须提供 reported_balance")
        record.reported_balance = data.reported_balance
        record.reported_earnings = platform.total_earnings
        record.calculated_transfer = data.reported_balance - platform.current_balance
        platform.current_balance = data.reported_balance

    elif data.record_type == "transfer_in":
        if data.amount is None or data.amount <= 0:
            raise HTTPException(status_code=400, detail="转入金额必须大于0")
        record.amount = data.amount
        record.calculated_transfer = data.amount
        platform.current_balance += data.amount

    elif data.record_type == "transfer_out":
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


@router.put("/assets/records/{record_id}", response_model=AssetRecordResponse)
async def update_asset_record(
    record_id: int,
    data: AssetRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """编辑资产变动记录（仅编辑备注和数值，不重新计算平台余额）"""
    record = db.query(AssetRecord).filter(
        AssetRecord.id == record_id,
        AssetRecord.owner_id == current_user.id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    update_data = data.model_dump(exclude_unset=True, exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    for key, value in update_data.items():
        setattr(record, key, value)

    db.commit()
    db.refresh(record)
    if record.platform:
        record.platform_name = record.platform.name
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
    """获取资产总览（含各平台详情和记录）
    
    total_earnings 返回当前年份的收益（不是累计）
    yearly_earnings 返回历年收益归档
    """
    platforms = db.query(AssetPlatform).filter(
        AssetPlatform.owner_id == current_user.id,
        AssetPlatform.is_active == True
    ).order_by(AssetPlatform.sort_order, AssetPlatform.id).all()

    total_balance = Decimal('0')
    total_current_year_earnings = Decimal('0')
    all_yearly: dict[str, Decimal] = {}
    current_year = datetime.now().year

    platform_details = []

    for p in platforms:
        if p.is_asset:
            total_balance += (p.current_balance or Decimal('0'))
            total_current_year_earnings += (p.total_earnings or Decimal('0'))

        # 合并历年收益（所有平台都参与）
        yearly = _parse_yearly_earnings(p)
        for yk, yv in yearly.items():
            all_yearly[yk] = all_yearly.get(yk, Decimal('0')) + Decimal(str(yv))

        # 获取最近20条记录
        records = db.query(AssetRecord).filter(
            AssetRecord.platform_id == p.id
        ).order_by(AssetRecord.created_at.desc()).limit(20).all()

        record_responses = []
        for r in records:
            resp = AssetRecordResponse.model_validate(r)
            resp.platform_name = p.name
            record_responses.append(resp)

        # 计算年化收益率（当年收益/当前余额*100%）
        annualized = None
        if p.current_balance and p.current_balance > 0 and p.total_earnings is not None:
            annualized = round(p.total_earnings / p.current_balance * Decimal('100'), 2)

        detail = AssetPlatformDetailResponse(
            id=p.id,
            name=p.name,
            current_balance=p.current_balance or Decimal('0'),
            total_earnings=p.total_earnings or Decimal('0'),
            current_year=p.current_year or current_year,
            yearly_earnings=yearly,
            sort_order=p.sort_order,
            is_active=p.is_active,
            is_asset=p.is_asset,
            created_at=p.created_at,
            updated_at=p.updated_at,
            records=record_responses,
            annualized_return=annualized
        )
        platform_details.append(detail)

    # 当前年份的收益也加入历年总和中
    if str(current_year) not in all_yearly:
        all_yearly[str(current_year)] = total_current_year_earnings
    else:
        all_yearly[str(current_year)] = total_current_year_earnings

    return AssetSummaryResponse(
        total_balance=total_balance,
        total_earnings=total_current_year_earnings,
        yearly_earnings=all_yearly,
        current_year=current_year,
        platforms=platform_details
    )


# ==================== 资产趋势 ====================

@router.get("/assets/trend", response_model=AssetTrendResponse)
async def get_asset_trend(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取资产趋势（按天汇总balance记录的总资产和总收益）"""
    platforms = db.query(AssetPlatform).filter(
        AssetPlatform.owner_id == current_user.id,
        AssetPlatform.is_active == True,
        AssetPlatform.is_asset == True
    ).all()

    if not platforms:
        return AssetTrendResponse(points=[], platforms=[])

    platform_ids = [p.id for p in platforms]

    # 获取所有记录（不限类型），按日期排序
    records = db.query(AssetRecord).filter(
        AssetRecord.platform_id.in_(platform_ids),
    ).order_by(AssetRecord.created_at.asc()).all()

    if not records:
        return AssetTrendResponse(points=[], platforms=[])

    # 按天汇总
    from collections import defaultdict
    daily_data: dict[str, dict] = defaultdict(lambda: {'total_balance': Decimal('0'), 'total_earnings': Decimal('0')})
    platform_daily: dict[str, dict] = defaultdict(lambda: {})

    for r in records:
        # 用北京时间（UTC+8）来分组日期
        beijing_time = r.created_at + timedelta(hours=8)
        date_key = beijing_time.strftime('%Y-%m-%d')
        p = next((p for p in platforms if p.id == r.platform_id), None)
        pname = p.name if p else '?'

        # 该平台当天最新的balance/earnings（优先用balance_after，退而用reported_balance）
        balance = r.balance_after or r.reported_balance or Decimal('0')
        earnings = r.earnings_after or r.reported_earnings or Decimal('0')
        platform_daily[date_key][r.platform_id] = {
            'name': pname,
            'balance': balance,
            'earnings': earnings
        }

    # 按时间顺序累计各平台
    all_dates = sorted(platform_daily.keys())

    # 对每个日期，汇总所有平台的当前值
    points = []
    platform_points = []
    running_balances: dict[int, Decimal] = {}
    running_earnings: dict[int, Decimal] = {}
    prev_total_earnings = Decimal('0')

    for date_key in all_dates:
        # 更新每个平台的运行值
        for pid, data in platform_daily[date_key].items():
            running_balances[pid] = data['balance']
            running_earnings[pid] = data['earnings']

        total_balance = sum(running_balances.values())
        total_earnings = sum(running_earnings.values())
        earnings_delta = total_earnings - prev_total_earnings
        prev_total_earnings = total_earnings

        points.append(AssetTrendPoint(
            date=date_key,
            total_balance=total_balance,
            total_earnings=total_earnings,
            earnings_delta=earnings_delta
        ))

        # 各平台趋势
        for pid in running_balances:
            pname = next((p.name for p in platforms if p.id == pid), '?')
            platform_points.append(PlatformTrendPoint(
                date=date_key,
                name=pname,
                balance=running_balances[pid],
                earnings=running_earnings[pid]
            ))

    # 最后追加今天的样本点（取各平台当前最新值，仅对已有记录的平台）
    today_key = (datetime.now() + timedelta(hours=8)).strftime('%Y-%m-%d')
    if today_key not in platform_daily:
        # 仅对前面有过记录的平台更新今天的值
        for pid in list(running_balances.keys()):
            p = next((x for x in platforms if x.id == pid), None)
            if p:
                running_balances[pid] = p.current_balance or Decimal('0')
                running_earnings[pid] = p.total_earnings or Decimal('0')
        total_balance = sum(running_balances.values())
        total_earnings = sum(running_earnings.values())
        earnings_delta = total_earnings - prev_total_earnings if points else total_earnings

        points.append(AssetTrendPoint(
            date=today_key,
            total_balance=total_balance,
            total_earnings=total_earnings,
            earnings_delta=earnings_delta
        ))

        for pid, pname in [(pid, next((x.name for x in platforms if x.id == pid), '?')) for pid in running_balances]:
            platform_points.append(PlatformTrendPoint(
                date=today_key,
                name=pname,
                balance=running_balances[pid],
                earnings=running_earnings[pid]
            ))

    return AssetTrendResponse(
        points=points,
        platforms=platform_points
    )


@router.get("/assets/zhaopingfei-summary", response_model=ZhaopingfeiSummaryResponse)
async def get_zhaopingfei_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取赵平飞转账年度统计"""
    platform = db.query(AssetPlatform).filter(
        AssetPlatform.owner_id == current_user.id,
        AssetPlatform.name == "赵平飞"
    ).first()

    if not platform:
        return ZhaopingfeiSummaryResponse(years=[], total_in=Decimal('0'), total_out=Decimal('0'), total_net=Decimal('0'))

    records = db.query(AssetRecord).filter(
        AssetRecord.platform_id == platform.id
    ).order_by(AssetRecord.created_at.asc()).all()

    from collections import defaultdict
    yearly: dict[str, dict] = defaultdict(lambda: {'in': Decimal('0'), 'out': Decimal('0')})
    total_in = Decimal('0')
    total_out = Decimal('0')

    for r in records:
        year_key = r.created_at.strftime('%Y')
        if r.record_type == 'transfer_in':
            yearly[year_key]['in'] += (r.amount or Decimal('0'))
            total_in += (r.amount or Decimal('0'))
        elif r.record_type == 'transfer_out':
            yearly[year_key]['out'] += (r.amount or Decimal('0'))
            total_out += (r.amount or Decimal('0'))

    years = []
    for y in sorted(yearly.keys()):
        d = yearly[y]
        years.append(ZhaopingfeiYearSummary(
            year=y,
            transfer_in=d['in'],
            transfer_out=d['out'],
            net=d['in'] - d['out']
        ))

    return ZhaopingfeiSummaryResponse(
        years=years,
        total_in=total_in,
        total_out=total_out,
        total_net=total_in - total_out
    )
