"""
统计报表 API 路由
"""
from typing import Optional
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, extract

from app.core.deps import get_db, get_current_user
from app.models import User, Room, Payment, UtilityReading
from app.schemas import (
    RoomStatsResponse, RevenueStatsResponse, OverdueInfoResponse, ExpiringLeaseResponse
)
from app.service.business import (
    get_room_statistics, get_revenue_statistics, get_overdue_payments, get_expiring_leases
)

router = APIRouter(prefix="/stats", tags=["statistics"])


def check_stats_permission(user: User):
    """检查统计权限"""
    if user.role == "tenant":
        raise HTTPException(status_code=403, detail="租客无权查看统计")
    return True


@router.get("/rooms", response_model=RoomStatsResponse)
def get_statistics_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取房间统计
    
    - 总房间数
    - 空置/已租/维修中的房间数
    - 出租率
    """
    check_stats_permission(current_user)
    
    stats = get_room_statistics(db)
    return stats


@router.get("/revenue")
def get_statistics_revenue(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    group_by: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取收入统计
    
    - 总收入
    - 按类型统计（租金/水电费/押金）
    - 按时间分组统计（月度/年度）
    
    参数：
    - start_date: 开始日期
    - end_date: 结束日期
    - group_by: 分组方式 (month/year)
    """
    check_stats_permission(current_user)
    
    if not start_date:
        start_date = date.today().replace(day=1)
    if not end_date:
        end_date = date.today()
    
    stats = get_revenue_statistics(db, start_date, end_date)
    
    # 按时间分组
    by_month = []
    if group_by in ['month', 'year']:
        query = db.query(
            extract('year', Payment.payment_date).label('year'),
            extract('month', Payment.payment_date).label('month'),
            Payment.payment_type,
            func.sum(Payment.amount).label('total')
        ).filter(
            and_(
                Payment.payment_date >= start_date,
                Payment.payment_date <= end_date,
                Payment.status == 'completed'
            )
        ).group_by(
            extract('year', Payment.payment_date),
            extract('month', Payment.payment_date),
            Payment.payment_type
        ).order_by(
            extract('year', Payment.payment_date),
            extract('month', Payment.payment_date)
        ).all()
        
        for row in query:
            by_month.append({
                'year': int(row.year),
                'month': int(row.month),
                'payment_type': row.payment_type,
                'total': float(row.total)
            })
    
    return {
        **stats,
        'start_date': start_date,
        'end_date': end_date,
        'by_month': by_month
    }


@router.get("/utility")
def get_statistics_utility(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    utility_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取水电费统计
    
    - 总用量和总费用
    - 按类型统计
    - 按房间统计
    
    参数：
    - start_date: 开始日期
    - end_date: 结束日期
    - utility_type: 水电类型 (water/electricity/gas)
    """
    check_stats_permission(current_user)
    
    if not start_date:
        start_date = date.today().replace(day=1)
    if not end_date:
        end_date = date.today()
    
    query = db.query(UtilityReading).filter(
        and_(
            UtilityReading.reading_date >= start_date,
            UtilityReading.reading_date <= end_date
        )
    )
    
    if utility_type:
        query = query.filter(UtilityReading.utility_type == utility_type)
    
    readings = query.all()
    
    total_usage = sum(r.usage or 0 for r in readings)
    total_amount = sum(r.amount or 0 for r in readings)
    
    # 按类型统计
    by_type = {}
    for utype in ['water', 'electricity', 'gas']:
        type_readings = [r for r in readings if r.utility_type == utype]
        by_type[utype] = {
            'count': len(type_readings),
            'usage': sum(r.usage or 0 for r in type_readings),
            'amount': sum(r.amount or 0 for r in type_readings)
        }
    
    # 按房间统计
    by_room = {}
    for reading in readings:
        if reading.room_id not in by_room:
            by_room[reading.room_id] = {
                'room_id': reading.room_id,
                'room_number': reading.room.room_number,
                'usage': 0,
                'amount': 0
            }
        by_room[reading.room_id]['usage'] += reading.usage or 0
        by_room[reading.room_id]['amount'] += reading.amount or 0
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'total_usage': total_usage,
        'total_amount': total_amount,
        'by_type': by_type,
        'by_room': list(by_room.values())
    }


@router.get("/overdue")
def get_statistics_overdue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取逾期支付统计
    
    - 逾期支付列表
    - 逾期总金额
    - 逾期天数统计
    """
    check_stats_permission(current_user)
    
    overdue_list = get_overdue_payments(db)
    total_overdue_amount = sum(p['amount'] for p in overdue_list)
    
    return {
        'count': len(overdue_list),
        'total_amount': total_overdue_amount,
        'overdue_list': overdue_list
    }


@router.get("/expiring")
def get_statistics_expiring(
    days_threshold: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取即将到期租约统计
    
    参数：
    - days_threshold: 天数阈值（默认30天）
    
    返回：
    - 即将到期的租约列表
    - 按紧急程度分类
    """
    check_stats_permission(current_user)
    
    expiring_leases = get_expiring_leases(db, days_threshold)
    
    # 按紧急程度分类
    critical = []  # 7天内
    warning = []   # 8-30天
    normal = []    # 31天以上
    
    for lease in expiring_leases:
        days = lease['days_remaining']
        if days <= 7:
            critical.append(lease)
        elif days <= 30:
            warning.append(lease)
        else:
            normal.append(lease)
    
    return {
        'total_count': len(expiring_leases),
        'critical_count': len(critical),
        'warning_count': len(warning),
        'normal_count': len(normal),
        'critical': critical,
        'warning': warning,
        'normal': normal
    }


@router.get("/dashboard")
def get_dashboard_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取仪表板统计概览
    
    返回关键统计指标：
    - 房间统计
    - 本月收入
    - 逾期提醒
    - 租约到期提醒
    """
    check_stats_permission(current_user)
    
    today = date.today()
    month_start = today.replace(day=1)
    
    # 房间统计
    room_stats = get_room_statistics(db)
    
    # 本月收入
    revenue_stats = get_revenue_statistics(db, month_start, today)
    
    # 逾期提醒
    overdue_list = get_overdue_payments(db)
    
    # 租约到期提醒（30天内）
    expiring_leases = get_expiring_leases(db, 30)
    
    return {
        'rooms': room_stats,
        'revenue_this_month': revenue_stats,
        'overdue_count': len(overdue_list),
        'overdue_amount': sum(p['amount'] for p in overdue_list),
        'expiring_leases_count': len(expiring_leases),
        'overdue_recent': overdue_list[:5],
        'expiring_recent': expiring_leases[:5]
    }
