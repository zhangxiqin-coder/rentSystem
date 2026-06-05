"""水电账单API路由"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import extract
from typing import List
from datetime import datetime

from app.database import get_db
from app.models import UtilityBill, UtilityReading
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


@router.post("/", response_model=UtilityBillResponse)
def create_utility_bill(
    bill: UtilityBillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建水电账单"""
    # 检查同年月是否已存在
    existing = db.query(UtilityBill).filter(
        UtilityBill.year == bill.year,
        UtilityBill.month == bill.month
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="该月份的账单已存在")
    
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
    bills = db.query(UtilityBill).order_by(
        UtilityBill.year.desc(),
        UtilityBill.month.desc()
    ).all()
    
    total_water_profit = 0
    total_electric_profit = 0
    monthly_breakdown = []
    
    for bill in bills:
        # 获取该月从租客收取的水电费 - 从reading_date中提取年月
        readings = db.query(UtilityReading).filter(
            extract('year', UtilityReading.reading_date) == bill.year,
            extract('month', UtilityReading.reading_date) == bill.month
        ).all()
        
        water_collected = sum(r.amount for r in readings if r.utility_type == "water") if readings else 0
        electric_collected = sum(r.amount for r in readings if r.utility_type == "electricity") if readings else 0
        
        water_profit = water_collected - bill.water_cost
        electric_profit = electric_collected - bill.electric_cost
        
        total_water_profit += water_profit
        total_electric_profit += electric_profit
        
        monthly_breakdown.append({
            "year": bill.year,
            "month": bill.month,
            "water_collected": water_collected,
            "water_cost": bill.water_cost,
            "water_profit": water_profit,
            "electric_collected": electric_collected,
            "electric_cost": bill.electric_cost,
            "electric_profit": electric_profit,
            "total_profit": water_profit + electric_profit
        })
    
    return {
        "total_water_profit": total_water_profit,
        "total_electric_profit": total_electric_profit,
        "total_profit": total_water_profit + total_electric_profit,
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
