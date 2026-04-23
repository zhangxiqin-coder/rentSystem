"""
Pydantic schemas 定义（统一数据模型）
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, EmailStr, model_validator
from enum import Enum


# ==================== 枚举定义 ====================

class PaymentMethod(str, Enum):
    """支付方式枚举"""
    CASH = "现金"
    BANK_TRANSFER = "银行转账"
    ALIPAY = "支付宝"
    WECHAT = "微信支付"


class UserRole(str, Enum):
    """用户角色枚举"""
    ADMIN = "admin"
    LANDLORD = "landlord"
    TENANT = "tenant"


class RoomStatus(str, Enum):
    """房间状态枚举"""
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"


class PaymentType(str, Enum):
    """支付类型枚举"""
    RENT = "rent"
    DEPOSIT = "deposit"
    UTILITY = "utility"
    OTHER = "other"


class PaymentStatus(str, Enum):
    """支付状态枚举"""
    PENDING = "pending"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class UtilityType(str, Enum):
    """水电类型枚举"""
    WATER = "water"
    ELECTRICITY = "electricity"
    GAS = "gas"


# ==================== User Schemas ====================

class UserBase(BaseModel):
    """用户基础 schema"""
    username: str = Field(..., min_length=1, max_length=50)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)


class UserCreate(UserBase):
    """用户创建 schema"""
    password: str = Field(..., min_length=8)
    role: Optional[UserRole] = Field(default=UserRole.LANDLORD)


class UserUpdate(BaseModel):
    """用户更新 schema"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """用户响应 schema"""
    id: int
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================== Auth Schemas ====================

class LoginRequest(BaseModel):
    """登录请求 schema"""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Token 响应 schema"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ChangePasswordRequest(BaseModel):
    """修改密码请求 schema"""
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


class MessageResponse(BaseModel):
    """通用消息响应 schema"""
    message: str


# ==================== Room Schemas ====================

class RoomBase(BaseModel):
    """房间基础 schema"""
    room_number: str = Field(..., min_length=1, max_length=50)
    building: Optional[str] = Field(None, max_length=50)
    floor: Optional[int] = Field(None, ge=0)
    area: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    monthly_rent: Decimal = Field(..., gt=0, decimal_places=2)
    deposit_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    payment_cycle: int = Field(default=1, gt=0, le=12)
    status: Optional[RoomStatus] = Field(default=RoomStatus.AVAILABLE)
    tenant_name: Optional[str] = Field(None, max_length=100)
    tenant_phone: Optional[str] = Field(None, pattern=r'^1[3-9]\d{9}$')
    lease_start: Optional[date] = None
    lease_end: Optional[date] = None
    description: Optional[str] = None


class RoomCreate(RoomBase):
    """房间创建 schema"""

    @model_validator(mode='after')
    def validate_lease_dates(self):
        """验证租约结束日期必须大于开始日期"""
        if self.lease_start and self.lease_end:
            if self.lease_end <= self.lease_start:
                raise ValueError("lease_end must be greater than lease_start")
        return self


class RoomUpdate(BaseModel):
    """房间更新 schema"""
    building: Optional[str] = Field(None, max_length=50)
    floor: Optional[int] = Field(None, ge=0)
    area: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    monthly_rent: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    deposit_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    payment_cycle: Optional[int] = Field(None, gt=0, le=12)
    status: Optional[RoomStatus] = None
    tenant_name: Optional[str] = Field(None, max_length=100)
    tenant_phone: Optional[str] = Field(None, pattern=r'^1[3-9]\d{9}$')
    lease_start: Optional[date] = None
    lease_end: Optional[date] = None
    description: Optional[str] = None

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
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================== Payment Schemas ====================

class PaymentBase(BaseModel):
    """支付记录基础 schema"""
    room_id: int = Field(..., gt=0)
    amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    payment_type: PaymentType
    payment_date: Optional[date] = None
    due_date: Optional[date] = None
    status: Optional[PaymentStatus] = Field(default=PaymentStatus.COMPLETED)
    payment_method: Optional[PaymentMethod] = None
    description: Optional[str] = None
    receipt_image: Optional[str] = Field(None, max_length=255)


class PaymentCreate(PaymentBase):
    """支付记录创建 schema"""
    payment_date: date = Field(default_factory=date.today)


class PaymentUpdate(BaseModel):
    """支付记录更新 schema"""
    amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    due_date: Optional[date] = None
    status: Optional[PaymentStatus] = None
    payment_method: Optional[PaymentMethod] = None
    description: Optional[str] = None
    receipt_image: Optional[str] = Field(None, max_length=255)


class PaymentResponse(PaymentBase):
    """支付记录响应 schema"""
    id: int
    payment_date: date
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================== UtilityReading Schemas ====================

class UtilityReadingBase(BaseModel):
    """水电抄表记录基础 schema"""
    room_id: int = Field(..., gt=0)
    utility_type: UtilityType
    reading: Decimal = Field(..., ge=0, decimal_places=2)
    reading_date: date
    notes: Optional[str] = None


class UtilityReadingCreate(UtilityReadingBase):
    """水电抄表记录创建 schema"""
    # 上次读数、用量、费用自动计算，不在此输入


class UtilityReadingUpdate(BaseModel):
    """水电抄表记录更新 schema"""
    notes: Optional[str] = None
    # 其他字段不允许修改


class UtilityReadingResponse(UtilityReadingBase):
    """水电抄表记录响应 schema"""
    id: int
    previous_reading: Optional[Decimal] = None
    usage: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    rate_used: Optional[Decimal] = None
    recorded_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================== UtilityRate Schemas ====================

class UtilityRateBase(BaseModel):
    """水电费率基础 schema"""
    utility_type: UtilityType
    rate_per_unit: Decimal = Field(..., gt=0, decimal_places=4)
    effective_date: date
    description: Optional[str] = None


class UtilityRateCreate(UtilityRateBase):
    """水电费率创建 schema"""
    pass


class UtilityRateUpdate(BaseModel):
    """水电费率更新 schema"""
    rate_per_unit: Optional[Decimal] = Field(None, gt=0, decimal_places=4)
    effective_date: Optional[date] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


class UtilityRateResponse(UtilityRateBase):
    """水电费率响应 schema"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================== 统计相关 Schemas ====================

class RoomStatsResponse(BaseModel):
    """房间统计响应"""
    total_rooms: int
    available_rooms: int
    occupied_rooms: int
    maintenance_rooms: int
    occupancy_rate: float


class RevenueStatsResponse(BaseModel):
    """收入统计响应"""
    total_revenue: Decimal
    rent_revenue: Decimal
    utility_revenue: Decimal
    deposit_revenue: Decimal
    by_month: list[dict]


class OverdueInfoResponse(BaseModel):
    """逾期信息响应"""
    room_id: int
    room_number: str
    tenant_name: Optional[str]
    due_date: date
    overdue_days: int
    amount: Decimal


class ExpiringLeaseResponse(BaseModel):
    """即将到期租约响应"""
    room_id: int
    room_number: str
    tenant_name: Optional[str]
    lease_end: date
    days_remaining: int


# ==================== 分页参数 ====================

class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(default=1, ge=1)
    size: int = Field(default=10, ge=1, le=100)
    search: Optional[str] = None
    sort_by: Optional[str] = None
    order: Optional[str] = Field(default="desc", pattern="^(asc|desc)$")


# ==================== 通用列表响应 ====================

class PaginatedResponse(BaseModel):
    """分页响应"""
    items: list
    total: int
    page: int
    size: int
    pages: int
