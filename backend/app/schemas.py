"""
Pydantic schemas 定义
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, EmailStr, model_validator
from enum import Enum


class PaymentMethod(str, Enum):
    """支付方式枚举"""
    CASH = "现金"
    BANK_TRANSFER = "银行转账"
    ALIPAY = "支付宝"
    WECHAT = "微信支付"


# ==================== User Schemas ====================

class UserBase(BaseModel):
    """用户基础 schema"""
    username: str = Field(..., min_length=1, max_length=50)
    email: Optional[EmailStr] = None


class UserCreate(UserBase):
    """用户创建 schema"""
    password: str = Field(..., min_length=6)


class UserResponse(UserBase):
    """用户响应 schema"""
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ==================== Room Schemas ====================

class RoomBase(BaseModel):
    """房间基础 schema"""
    name: str = Field(..., min_length=1, max_length=50)
    monthly_rent: Decimal = Field(..., gt=0, decimal_places=2)
    tenant_name: Optional[str] = Field(None, max_length=100)
    tenant_phone: Optional[str] = Field(None, pattern=r'^1[3-9]\d{9}$')
    lease_start: Optional[date] = None
    lease_end: Optional[date] = None
    payment_cycle: int = Field(default=1, gt=0)


class RoomCreate(RoomBase):
    """房间创建 schema"""
    pass
    
    @model_validator(mode='after')
    def validate_lease_dates(self):
        """验证租约结束日期必须大于开始日期"""
        if self.lease_start and self.lease_end:
            if self.lease_end <= self.lease_start:
                raise ValueError("lease_end must be greater than lease_start")
        return self


class RoomResponse(RoomBase):
    """房间响应 schema"""
    id: int
    last_payment_date: Optional[date] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ==================== Payment Schemas ====================

class PaymentBase(BaseModel):
    """交租记录基础 schema"""
    room_id: int = Field(..., gt=0)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    payment_date: date
    payment_method: Optional[PaymentMethod] = None
    note: Optional[str] = None
    receipt_image: Optional[str] = Field(None, max_length=255)


class PaymentCreate(PaymentBase):
    """交租记录创建 schema"""
    pass


class PaymentResponse(PaymentBase):
    """交租记录响应 schema"""
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ==================== UtilityReading Schemas ====================

class UtilityReadingBase(BaseModel):
    """水电抄表记录基础 schema"""
    room_id: int = Field(..., gt=0)
    utility_type: str = Field(..., pattern=r'^(water|electric)$')
    reading: Decimal = Field(..., ge=0, decimal_places=2)
    reading_date: date
    note: Optional[str] = None


class UtilityReadingCreate(UtilityReadingBase):
    """水电抄表记录创建 schema"""
    pass


class UtilityReadingResponse(UtilityReadingBase):
    """水电抄表记录响应 schema"""
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ==================== UtilityRate Schemas ====================

class UtilityRateBase(BaseModel):
    """水电费率基础 schema"""
    utility_type: str = Field(..., pattern=r'^(water|electric)$')
    unit_price: Decimal = Field(..., gt=0, decimal_places=4)
    effective_date: date


class UtilityRateCreate(UtilityRateBase):
    """水电费率创建 schema"""
    pass


class UtilityRateResponse(UtilityRateBase):
    """水电费率响应 schema"""
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
