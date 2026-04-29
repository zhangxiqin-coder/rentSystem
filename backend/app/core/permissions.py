"""
用户隔离权限控制工具
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import User, Room, Payment, UtilityReading


def get_user_owner_filter(user: User):
    """
    获取用户的数据过滤条件

    规则：
    - admin/super_landlord角色：可以看到所有数据（返回None，不过滤）
    - landlord角色：只能看到自己创建的数据（owner_id == user.id）
    - tenant角色：无权访问（在API层返回403）

    Returns:
        过滤条件表达式，或None（不过滤）
    """
    if user.role in ("admin", "super_landlord"):
        return None

    # 其他房东只能看到自己创建的数据
    if user.role == "landlord":
        return True  # 标记需要过滤，具体过滤条件在查询时设置

    # 租客无权访问
    return False


def apply_room_filter(query, user: User):
    """
    应用用户权限过滤到房间查询

    Args:
        query: SQLAlchemy查询对象
        user: 当前用户

    Returns:
        过滤后的查询对象
    """
    filter_result = get_user_owner_filter(user)

    # admin和super_landlord不过滤
    if filter_result is None:
        return query

    # 其他角色只能看到自己创建的数据
    if filter_result is True:
        return query.filter(Room.owner_id == user.id)

    # 租客无权访问（在API层会返回403，这里过滤掉所有数据）
    return query.filter(False)


def apply_payment_filter(query, user: User):
    """
    应用用户权限过滤到支付查询

    Args:
        query: SQLAlchemy查询对象
        user: 当前用户

    Returns:
        过滤后的查询对象
    """
    filter_result = get_user_owner_filter(user)

    # admin和super_landlord不过滤
    if filter_result is None:
        return query

    # 其他角色只能看到自己创建的数据
    if filter_result is True:
        return query.filter(Payment.owner_id == user.id)

    # 租客无权访问
    return query.filter(False)


def apply_utility_reading_filter(query, user: User):
    """
    应用用户权限过滤到水电查询

    Args:
        query: SQLAlchemy查询对象
        user: 当前用户

    Returns:
        过滤后的查询对象
    """
    filter_result = get_user_owner_filter(user)

    # admin和super_landlord不过滤
    if filter_result is None:
        return query

    # 其他角色只能看到自己创建的数据
    if filter_result is True:
        return query.filter(UtilityReading.owner_id == user.id)

    # 租客无权访问
    return query.filter(False)
