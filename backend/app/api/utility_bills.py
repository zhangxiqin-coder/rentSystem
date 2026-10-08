"""水电账单API路由"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from typing import List, Dict, Any
from datetime import datetime

from app.database import get_db
from app.models import UtilityBill, UtilityReading, Room, Payment, PaymentType
from app.schemas import (
    UtilityBillCreate,
    UtilityBillUpdate,
    UtilityBillResponse,
    UtilityBillProfitStats,
    BillWithProfit
)
from app.core.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/utility-bills", tags=["水电账单"])


def _get_user_series_set(db: Session, user_id: int) -> set:
    """获取当前用户拥有的所有房子系列（用于按 series 间接隔离 UtilityBill）。

    UtilityBill 表本身没有 owner_id 字段，但 series 字段值来自 Room.series，
    而 Room 是按 owner_id 隔离的。所以只要把当前用户拥有的 series 集合算出来，
    再用它过滤 UtilityBill，就能实现数据隔离。
    """
    rows = db.query(Room.series).filter(
        Room.owner_id == user_id,
        Room.series.isnot(None)
    ).distinct().all()
    return {r[0] for r in rows if r[0]}




@router.get("/series", response_model=List[Dict[str, Any]])
def get_series_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的房子系列列表（排除水电不收费的系列）"""
    # 获取当前用户的所有房间，排除水电费率都为0的房间
    user_rooms = db.query(Room.series).filter(
        Room.owner_id == current_user.id,
        Room.series.isnot(None)
    ).distinct().all()
    
    # 获取有水电收费的系列（至少有一个房间的水费或电费率大于0）
    billable_series = set()
    for (series,) in user_rooms:
        # 检查该系列是否至少有一个房间有水电收费
        room_with_rates = db.query(Room).filter(
            Room.owner_id == current_user.id,
            Room.series == series,
            or_(
                Room.water_rate > 0,
                Room.electricity_rate > 0
            )
        ).first()
        
        if room_with_rates:
            billable_series.add(series)
    
    # 统计每个系列的房间数量（只统计水电收费的房间）
    result = []
    for series in sorted(billable_series):
        room_count = db.query(Room).filter(
            Room.owner_id == current_user.id,
            Room.series == series,
            or_(
                Room.water_rate > 0,
                Room.electricity_rate > 0
            )
        ).count()
        
        result.append({
            "series": series,
            "room_count": room_count
        })
    
    return result


@router.post("/", response_model=UtilityBillResponse)
def create_utility_bill(
    bill: UtilityBillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建水电账单"""
    # 数据隔离：只能为自己拥有的系列创建账单
    user_series = _get_user_series_set(db, current_user.id)
    if bill.series not in user_series:
        raise HTTPException(status_code=403, detail=f"无权操作系列 '{bill.series}'：该系列不属于当前用户")

    # 检查同系列同年月同类型是否已存在
    existing = db.query(UtilityBill).filter(
        UtilityBill.series == bill.series,
        UtilityBill.year == bill.year,
        UtilityBill.month == bill.month,
        UtilityBill.utility_type == bill.utility_type
    ).first()
    
    if existing:
        type_name = "水费" if bill.utility_type == "water" else "电费"
        raise HTTPException(status_code=400, detail=f"该系列{bill.year}-{bill.month:02d}的{type_name}账单已存在")
    
    db_bill = UtilityBill(**bill.model_dump())
    db.add(db_bill)
    try:
        db.commit()
    except (IntegrityError, ValueError) as e:
        # 兜底：本地缓存副本落后时上面的查重看不到云端已有记录
        #（embedded replica 读旧数据），INSERT 会在云端撞
        # UNIQUE(series, year, month, utility_type) 约束。
        # libsql 把约束错误包成 ValueError，SQLite 直抛 IntegrityError。
        db.rollback()
        err_text = str(e)
        if "UNIQUE constraint" in err_text or "SQLITE_CONSTRAINT" in err_text:
            type_name = "水费" if bill.utility_type == "water" else "电费"
            raise HTTPException(
                status_code=400,
                detail=f"该系列{bill.year}-{bill.month:02d}的{type_name}账单已存在（云端已有记录，请刷新后查看；如需修改请编辑现有账单）",
            )
        raise
    db.refresh(db_bill)
    return db_bill


@router.get("/", response_model=List[UtilityBillResponse])
def get_utility_bills(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取水电账单列表（按当前用户拥有的系列过滤）"""
    user_series = _get_user_series_set(db, current_user.id)
    if not user_series:
        return []  # 当前用户没有任何系列，直接返回空

    bills = db.query(UtilityBill).filter(
        UtilityBill.series.in_(user_series)
    ).order_by(
        UtilityBill.year.desc(),
        UtilityBill.month.desc()
    ).offset(skip).limit(limit).all()
    return bills


def _bill_period(payment_date) -> tuple:
    """水电收益的账期归属：每月1-5号收的算上个月。

    供电局按自然月出账，但抄表/收款日不固定（有时31号收、有时1号收），
    同一期账可能落在两个日历月。规则：day<=5 归上个月，day>5 归当月，
    这样同一期账始终落在同一个账期里，跟供电局账单月对齐。
    """
    d = payment_date
    if d.day <= 5:
        if d.month == 1:
            return (d.year - 1, 12)
        return (d.year, d.month - 1)
    return (d.year, d.month)


@router.get("/profit", response_model=UtilityBillProfitStats)
def get_profit_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取水电收益统计（按当前用户拥有的系列过滤）

    归月规则：收款日在1-5号 → 算上个月账期；其余算当月。
    每个房间每类型每个账期只取最近一次收款（以关联的抄表记录为准）。
    """
    # 数据隔离：只统计当前用户拥有的系列
    user_series = _get_user_series_set(db, current_user.id)
    if not user_series:
        return {
            "total_water_profit": 0.0,
            "total_electric_profit": 0.0,
            "total_profit": 0.0,
            "monthly_breakdown": []
        }

    # 一次性拉出用户所有房间的水电收款（含房间系列信息）
    user_rooms = db.query(Room).filter(Room.owner_id == current_user.id).all()
    room_series = {r.id: r.series for r in user_rooms}

    payments = db.query(Payment).filter(
        Payment.room_id.in_(room_series.keys()),
        Payment.payment_type == PaymentType.UTILITY
    ).all()

    from collections import defaultdict
    from decimal import Decimal

    # (series, period_year, period_month, room_id, utility_type) -> 最新一次
    latest = {}
    for p in payments:
        series = room_series.get(p.room_id)
        if not series or series not in user_series:
            continue
        desc = (p.description or "")
        if "水" in desc or "water" in desc.lower():
            utype = "water"
        elif "电" in desc or "electric" in desc.lower():
            utype = "electricity"
        else:
            continue
        period = _bill_period(p.payment_date)
        key = (series, period[0], period[1], p.room_id, utype)
        prev = latest.get(key)
        # 同账期同房间同类型多次收款：保留 payment_date 最新的一条
        if prev is None or (p.payment_date, p.id) > (prev.payment_date, prev.id):
            latest[key] = p

    # 按系列+账期汇总收款
    collected = defaultdict(lambda: {"water": Decimal("0"), "electricity": Decimal("0")})
    for (series, y, m, room_id, utype), p in latest.items():
        collected[(series, y, m)][utype] += p.amount or Decimal("0")

    # 支出账单按账期对齐（支出无“1-5号”问题，直接用账单年月）
    bills = db.query(UtilityBill).filter(
        UtilityBill.series.in_(user_series)
    ).all()

    total_water_profit = Decimal("0")
    total_electric_profit = Decimal("0")
    monthly_breakdown = []

    all_keys = set(collected.keys()) | {(b.series, b.year, b.month) for b in bills}
    for (series, year, month) in sorted(all_keys, reverse=True):
        data = collected.get((series, year, month), {"water": Decimal("0"), "electricity": Decimal("0")})

        water_cost = Decimal("0")
        electric_cost = Decimal("0")
        for b in bills:
            if b.series == series and b.year == year and b.month == month:
                if b.utility_type == "water":
                    water_cost = b.cost
                else:
                    electric_cost = b.cost

        water_collected = data["water"]
        electric_collected = data["electricity"]

        # 收益 = 从租客收取的 - 交给供电局的 = 净收益
        # 支出为0（还没录入供电局账单）时，收益暂不算
        if water_cost > 0:
            water_profit = water_collected - water_cost
        else:
            water_profit = Decimal("0")
        if electric_cost > 0:
            electric_profit = electric_collected - electric_cost
        else:
            electric_profit = Decimal("0")

        total_water_profit += water_profit
        total_electric_profit += electric_profit

        monthly_breakdown.append({
            "series": series,
            "year": year,
            "month": month,
            "water_collected": float(water_collected),
            "water_cost": float(water_cost),
            "water_profit": float(water_profit),
            "electric_collected": float(electric_collected),
            "electric_cost": float(electric_cost),
            "electric_profit": float(electric_profit),
            "total_profit": float(water_profit + electric_profit)
        })

    return {
        "total_water_profit": float(total_water_profit),
        "total_electric_profit": float(total_electric_profit),
        "total_profit": float(total_water_profit + total_electric_profit),
        "monthly_breakdown": monthly_breakdown
    }


@router.get("/{bill_id}", response_model=BillWithProfit)
def get_utility_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取单个水电账单（含收益）

    收款按账期归属（1-5号算上个月），每房间每类型取最近一次，
    与 /profit 口径一致。
    """
    bill = db.query(UtilityBill).filter(UtilityBill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")

    # 数据隔离：只能查看自己系列下的账单
    user_series = _get_user_series_set(db, current_user.id)
    if bill.series not in user_series:
        raise HTTPException(status_code=403, detail="无权操作此账单：该账单的系列不属于当前用户")

    # 该系列所有房间
    room_ids = [r.id for r in db.query(Room.id).filter(
        Room.series == bill.series,
        Room.owner_id == current_user.id
    ).all()]

    # 该账期的水电收款（账期归属 + 每房间每类型取最新）
    from decimal import Decimal
    utility_payments = db.query(Payment).filter(
        Payment.room_id.in_(room_ids),
        Payment.payment_type == PaymentType.UTILITY
    ).all() if room_ids else []

    latest = {}
    for p in utility_payments:
        if _bill_period(p.payment_date) != (bill.year, bill.month):
            continue
        desc = (p.description or "")
        if "水" in desc or "water" in desc.lower():
            utype = "water"
        elif "电" in desc or "electric" in desc.lower():
            utype = "electricity"
        else:
            continue
        key = (p.room_id, utype)
        prev = latest.get(key)
        if prev is None or (p.payment_date, p.id) > (prev.payment_date, prev.id):
            latest[key] = p

    water_collected = sum((p.amount for p in latest.values() if "水" in (p.description or "") or "water" in (p.description or "").lower()), Decimal("0"))
    electric_collected = sum((p.amount for p in latest.values() if "电" in (p.description or "") or "electric" in (p.description or "").lower()), Decimal("0"))

    bill_cost = bill.cost or Decimal("0")
    if bill.utility_type == "water":
        water_profit = water_collected - bill_cost
        electric_profit = Decimal("0")
    else:
        water_profit = Decimal("0")
        electric_profit = electric_collected - bill_cost

    return {
        **UtilityBillResponse.model_validate(bill).model_dump(),
        "water_collected": water_collected,
        "electric_collected": electric_collected,
        "water_profit": water_profit,
        "electric_profit": electric_profit,
        "total_profit": water_profit + electric_profit
    }


@router.put("/{bill_id}", response_model=UtilityBillResponse)
def update_utility_bill(
    bill_id: int,
    bill_update: UtilityBillUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新水电账单"""
    db_bill = db.query(UtilityBill).filter(UtilityBill.id == bill_id).first()
    if not db_bill:
        raise HTTPException(status_code=404, detail="账单不存在")

    # 数据隔离：只能更新自己系列下的账单
    user_series = _get_user_series_set(db, current_user.id)
    if db_bill.series not in user_series:
        raise HTTPException(status_code=403, detail="无权操作此账单：该账单的系列不属于当前用户")

    update_data = bill_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_bill, key, value)
    
    db.commit()
    db.refresh(db_bill)
    return db_bill


@router.get("/series/{series}/detail", response_model=List[Dict[str, Any]])
def get_series_utility_detail(
    series: str,
    year: int,
    month: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定系列、指定账期所有房间的水电收租明细。

    账期规则与 /profit 一致：reading_date 在1-5号 → 算上个月账期。
    每个房间每类型只取账期内最近一次抄表（多次录入以最新为准）。
    """
    # 获取该系列的所有房间
    rooms = db.query(Room).filter(
        Room.series == series,
        Room.owner_id == current_user.id
    ).all()

    if not rooms:
        raise HTTPException(status_code=404, detail="该系列没有房间")

    room_ids = [r.id for r in rooms]

    # 拉该系列全部抄表记录，在Python侧按账期过滤（1-5号归上月）
    readings = db.query(UtilityReading).filter(
        UtilityReading.room_id.in_(room_ids)
    ).all()

    # 按房间分组：每类型保留账期内 reading_date 最大的一条
    per_room = {rid: {} for rid in room_ids}
    for reading in readings:
        py, pm = _bill_period(reading.reading_date)
        if (py, pm) != (year, month):
            continue
        rid = reading.room_id
        utype = reading.utility_type
        if utype not in ("water", "electricity"):
            continue
        current = per_room[rid].get(utype)
        if current is None or reading.reading_date > current.reading_date:
            per_room[rid][utype] = reading

    result = []
    for room in rooms:
        water_reading = per_room[room.id].get("water")
        electric_reading = per_room[room.id].get("electricity")

        result.append({
            'room_id': room.id,
            'room_number': room.room_number,
            'water_previous': water_reading.previous_reading if water_reading else None,
            'water_current': water_reading.reading if water_reading else None,
            'water_usage': water_reading.usage if water_reading else None,
            'water_amount': float(water_reading.amount) if water_reading else None,
            'water_date': water_reading.reading_date.isoformat() if water_reading else None,
            'electric_previous': electric_reading.previous_reading if electric_reading else None,
            'electric_current': electric_reading.reading if electric_reading else None,
            'electric_usage': electric_reading.usage if electric_reading else None,
            'electric_amount': float(electric_reading.amount) if electric_reading else None,
            'electric_date': electric_reading.reading_date.isoformat() if electric_reading else None,
            'total_amount': (
                (float(water_reading.amount) if water_reading else 0) +
                (float(electric_reading.amount) if electric_reading else 0)
            )
        })

    # 按房间号排序
    result.sort(key=lambda x: x['room_number'])

    return result


@router.delete("/{bill_id}")
def delete_utility_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除水电账单"""
    db_bill = db.query(UtilityBill).filter(UtilityBill.id == bill_id).first()
    if not db_bill:
        raise HTTPException(status_code=404, detail="账单不存在")

    # 数据隔离：只能删除自己系列下的账单
    user_series = _get_user_series_set(db, current_user.id)
    if db_bill.series not in user_series:
        raise HTTPException(status_code=403, detail="无权操作此账单：该账单的系列不属于当前用户")

    db.delete(db_bill)
    db.commit()
    return {"message": "删除成功"}
