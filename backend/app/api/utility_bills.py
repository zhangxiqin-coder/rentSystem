"""水电账单API路由"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import extract, or_
from typing import List, Dict, Any
from datetime import datetime

from app.database import get_db
from app.models import UtilityBill, UtilityReading, Room
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
    db.commit()
    db.refresh(db_bill)
    return db_bill


@router.get("/", response_model=List[UtilityBillResponse])
def get_utility_bills(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取水电账单列表"""
    bills = db.query(UtilityBill).order_by(
        UtilityBill.year.desc(),
        UtilityBill.month.desc()
    ).offset(skip).limit(limit).all()
    return bills


@router.get("/profit", response_model=UtilityBillProfitStats)
def get_profit_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取水电收益统计"""
    # 获取所有账单，按年月倒序
    bills = db.query(UtilityBill).order_by(
        UtilityBill.year.desc(),
        UtilityBill.month.desc()
    ).all()
    
    # 按系列+年月分组
    from collections import defaultdict
    from decimal import Decimal
    grouped = defaultdict(lambda: {"water_cost": Decimal("0"), "electric_cost": Decimal("0"), "bills": []})
    
    for bill in bills:
        key = (bill.series, bill.year, bill.month)
        if bill.utility_type == "water":
            grouped[key]["water_cost"] = bill.cost
        else:
            grouped[key]["electric_cost"] = bill.cost
        grouped[key]["bills"].append(bill)
    
    total_water_profit = Decimal("0")
    total_electric_profit = Decimal("0")
    monthly_breakdown = []
    
    for (series, year, month), data in grouped.items():
        # 获取该系列的所有房间
        rooms = db.query(Room).filter(Room.series == series).all()
        room_ids = [r.id for r in rooms]
        
        # 获取该月该系列从租客收取的水电费
        readings = db.query(UtilityReading).filter(
            UtilityReading.room_id.in_(room_ids),
            extract('year', UtilityReading.reading_date) == year,
            extract('month', UtilityReading.reading_date) == month
        ).all()
        
        water_collected = sum((r.amount for r in readings if r.utility_type == "water"), Decimal("0")) if readings else Decimal("0")
        electric_collected = sum((r.amount for r in readings if r.utility_type == "electricity"), Decimal("0")) if readings else Decimal("0")
        
        water_cost = data["water_cost"]
        electric_cost = data["electric_cost"]
        
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
    """获取单个水电账单（含收益）"""
    bill = db.query(UtilityBill).filter(UtilityBill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")
    
    # 获取该月从租客收取的水电费 - 从reading_date中提取年月
    readings = db.query(UtilityReading).filter(
        extract('year', UtilityReading.reading_date) == bill.year,
        extract('month', UtilityReading.reading_date) == bill.month
    ).all()
    
    water_collected = sum(r.amount for r in readings if r.utility_type == "water") if readings else 0
    electric_collected = sum(r.amount for r in readings if r.utility_type == "electricity") if readings else 0
    
    water_profit = water_collected - bill.water_cost
    electric_profit = electric_collected - bill.electric_cost
    
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
    """获取指定系列、指定年月所有房间的水电收租明细"""
    # 获取该系列的所有房间
    rooms = db.query(Room).filter(
        Room.series == series,
        Room.owner_id == current_user.id
    ).all()
    
    if not rooms:
        raise HTTPException(status_code=404, detail="该系列没有房间")
    
    room_ids = [r.id for r in rooms]
    
    # 获取该年月的所有水电记录
    readings = db.query(UtilityReading, Room).join(
        Room, UtilityReading.room_id == Room.id
    ).filter(
        Room.id.in_(room_ids),
        extract('year', UtilityReading.reading_date) == year,
        extract('month', UtilityReading.reading_date) == month
    ).all()
    
    # 按房间分组
    result = []
    for room in rooms:
        room_readings = [r for r, rm in readings if rm.id == room.id]
        
        water_reading = None
        electric_reading = None
        
        for reading in room_readings:
            if reading.utility_type == 'water':
                water_reading = reading
            elif reading.utility_type == 'electricity':
                electric_reading = reading
        
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
    
    db.delete(db_bill)
    db.commit()
    return {"message": "删除成功"}
