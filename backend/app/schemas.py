"""
Pydantic schemas 定义（统一数据模型）
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, TypeVar, Generic
from pydantic import BaseModel, ConfigDict, Field, EmailStr, model_validator
from enum import Enum


# ==================== 通用类型变量 ====================

T = TypeVar('T')


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
    SUPER_LANDLORD = "super_landlord"
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
    REFUND = "refund"  # 退租退款
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
    landlord_name: Optional[str] = Field(None, max_length=100, description="甲方姓名（房东姓名）")
    landlord_phone: Optional[str] = Field(None, max_length=20, description="甲方联系电话")


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
    area: Optional[Decimal] = Field(None, ge=0)
    monthly_rent: Decimal = Field(..., gt=0)
    deposit_amount: Optional[Decimal] = Field(None, ge=0)
    payment_cycle: int = Field(default=1, gt=0, le=12)
    water_rate: Optional[Decimal] = Field(None, ge=0)  # 允许为None或0（针对2501系列房间）
    electricity_rate: Optional[Decimal] = Field(None, ge=0)  # 允许为None或0（针对2501系列房间）
    status: Optional[RoomStatus] = Field(default=RoomStatus.AVAILABLE)
    tenant_name: Optional[str] = Field(None, max_length=100)
    tenant_phone: Optional[str] = Field(None, pattern=r'^1[3-9]\d{9}$')
    tenant_id_card: Optional[str] = Field(None, pattern=r'^\d{17}[\dXx]$', max_length=18, description="租客身份证号码（18位）")
    tenant_id: Optional[int] = Field(None, description="关联租客ID")
    initial_electricity_reading: Optional[Decimal] = Field(default=0, ge=0, description="初始电表读数")
    initial_water_reading: Optional[Decimal] = Field(default=0, ge=0, description="初始水表读数")
    broadband_fee: Optional[Decimal] = Field(default=0, ge=0, description="宽带费")
    lease_start: Optional[date] = None
    lease_end: Optional[date] = None
    description: Optional[str] = None
    series: Optional[str] = Field(None, max_length=50, description="房间系列（如102、102A、2-2501等）")


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
    area: Optional[Decimal] = Field(None, ge=0)
    monthly_rent: Optional[Decimal] = Field(None, gt=0)
    deposit_amount: Optional[Decimal] = Field(None, ge=0)
    payment_cycle: Optional[int] = Field(None, gt=0, le=12)
    water_rate: Optional[Decimal] = Field(None, ge=0)  # 允许为None或0（针对2501系列房间）
    electricity_rate: Optional[Decimal] = Field(None, ge=0)  # 允许为None或0（针对2501系列房间）
    status: Optional[RoomStatus] = None
    tenant_name: Optional[str] = Field(None, max_length=100)
    tenant_phone: Optional[str] = Field(None, pattern=r'^1[3-9]\d{9}$')
    tenant_id_card: Optional[str] = Field(None, pattern=r'^\d{17}[\dXx]$', max_length=18, description="租客身份证号码（18位）")
    lease_start: Optional[date] = None
    lease_end: Optional[date] = None
    description: Optional[str] = None
    series: Optional[str] = Field(None, max_length=50, description="房间系列（如102、102A、2-2501等）")

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


# ==================== Check-in/Check-out Schemas ====================

class CheckoutRequest(BaseModel):
    """退租请求 schema"""
    refund_amount: Decimal = Field(..., ge=0, description="退款金额（退还押金/房租）")
    refund_date: date = Field(default_factory=date.today, description="退款日期")
    refund_reason: Optional[str] = Field(None, max_length=500, description="退租原因")
    payment_method: Optional[PaymentMethod] = Field(None, description="退款方式")


class CheckinRequest(BaseModel):
    """入住请求 schema"""
    tenant_name: Optional[str] = Field(None, max_length=100, description="租客姓名（可为空）")
    tenant_phone: Optional[str] = Field(None, pattern=r'^1[3-9]\d{9}$', description="租客电话（可为空）")
    tenant_id_card: Optional[str] = Field(None, pattern=r'^\d{17}[\dXx]$', max_length=18, description="租客身份证号码（可为空，18位）")
    lease_start: date = Field(..., description="租约开始日期")
    lease_end: date = Field(..., description="租约结束日期")
    monthly_rent: Optional[Decimal] = Field(None, gt=0, description="月租金")
    deposit_amount: Optional[Decimal] = Field(None, ge=0, description="押金金额")
    payment_cycle: Optional[int] = Field(1, gt=0, le=12, description="付款周期（月）")
    initial_electricity_reading: Optional[Decimal] = Field(None, ge=0, description="初始电表读数（可选）")
    initial_water_reading: Optional[Decimal] = Field(None, ge=0, description="初始水表读数（可选）")

    @model_validator(mode='after')
    def validate_lease_dates(self):
        """验证租约结束日期必须大于开始日期"""
        if self.lease_end <= self.lease_start:
            raise ValueError("租约结束日期必须大于开始日期")
        return self


class RenewLeaseRequest(BaseModel):
    """续租请求 schema"""
    months: int = Field(..., gt=0, le=120, description="续租月数（1-120个月，即1-10年）")
    monthly_rent: Optional[Decimal] = Field(None, gt=0, description="新月租金（如不修改则保持原租金）")
    notes: Optional[str] = Field(None, max_length=500, description="续租备注")


class RenewLeaseResponse(BaseModel):
    """续租响应 schema"""
    message: str
    room_id: int
    room_number: str
    old_lease_end: date
    new_lease_end: date
    months_added: int
    monthly_rent: Decimal


class CheckoutResponse(BaseModel):
    """退租响应 schema"""
    message: str
    room_id: int
    refund_payment_id: int
    checkout_date: date


class CheckinResponse(BaseModel):
    """入住响应 schema"""
    message: str
    room_id: int
    tenant_name: str
    lease_start: date
    lease_end: date


# ==================== Payment Schemas ====================

class PaymentBase(BaseModel):
    """支付记录基础 schema"""
    room_id: int = Field(..., gt=0)
    amount: Optional[Decimal] = Field(None, gt=0)
    payment_type: PaymentType
    payment_date: Optional[date] = None
    due_date: Optional[date] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    status: Optional[PaymentStatus] = Field(default=PaymentStatus.COMPLETED)
    payment_method: Optional[PaymentMethod] = None
    description: Optional[str] = None
    receipt_image: Optional[str] = Field(None, max_length=255)


class PaymentCreate(PaymentBase):
    """支付记录创建 schema"""
    payment_date: date = Field(default_factory=date.today)


class PaymentUpdate(BaseModel):
    """支付记录更新 schema"""
    amount: Optional[Decimal] = Field(None, gt=0)
    due_date: Optional[date] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
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
    room_number: Optional[str] = None  # 添加房间号字段

    model_config = ConfigDict(from_attributes=True)


class UtilityPaymentItem(BaseModel):
    """水电费用明细"""
    utility_type: str  # 'water' 或 'electricity'
    amount: Decimal
    original_amount: Decimal  # 原始金额（打折前）
    discount: Decimal = Decimal('0')  # 折扣金额


class BulkPaymentCreate(BaseModel):
    """批量收租创建 schema"""
    room_id: int
    reading_date: Optional[date] = None  # 水电抄表日期（可选）
    rent_amount: Decimal  # 房租（可打折）
    rent_original: Decimal  # 房租原始金额
    period_start: Optional[date] = None  # 房租覆盖起始日
    period_end: Optional[date] = None  # 房租覆盖结束日
    water_charge: Optional[UtilityPaymentItem] = None  # 水费明细
    electricity_charge: Optional[UtilityPaymentItem] = None  # 电费明细
    payment_date: date = Field(default_factory=date.today)
    payment_method: PaymentMethod = PaymentMethod.CASH
    notes: Optional[str] = None


class BulkPaymentResponse(BaseModel):
    """批量收租响应"""
    success: bool
    message: str
    payments: list[int]  # 支付记录ID列表
    total_original: Decimal  # 原始总额
    total_actual: Decimal  # 实收总额
    total_discount: Decimal  # 总折扣


# ==================== UtilityReading Schemas ====================

class UtilityReadingBase(BaseModel):
    """水电抄表记录基础 schema"""
    room_id: int = Field(..., gt=0)
    utility_type: UtilityType
    reading: Decimal = Field(..., ge=0)
    reading_date: date
    notes: Optional[str] = None


class UtilityReadingCreate(UtilityReadingBase):
    """水电抄表记录创建 schema"""
    previous_reading: Optional[Decimal] = Field(None, ge=0, description="可选手工上次读数")


class UtilityReadingUpdate(BaseModel):
    """水电抄表记录更新 schema"""
    reading: Optional[Decimal] = None  # 允许修改读数
    notes: Optional[str] = None  # 允许修改备注


class UtilityReadingResponse(UtilityReadingBase):
    """水电抄表记录响应 schema"""
    id: int
    previous_reading: Optional[Decimal] = None
    usage: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    rate_used: Optional[Decimal] = None
    recorded_by: Optional[int] = None
    payment_id: Optional[int] = None  # 关联的支付记录ID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BatchUtilityReadingCreate(BaseModel):
    """批量水电抄表记录创建 schema"""
    readings: list[UtilityReadingCreate]
    reading_date: date  # 统一设置读数日期
    notes: Optional[str] = None  # 统一设置备注


class BatchUtilityReadingResponse(BaseModel):
    """批量水电抄表记录响应 schema"""
    success_count: int
    failed_count: int
    total_amount: Decimal
    readings: list[UtilityReadingResponse]
    errors: list[str] = []


# ==================== UtilityRate Schemas ====================

class UtilityRateBase(BaseModel):
    """水电费率基础 schema"""
    utility_type: UtilityType
    rate_per_unit: Decimal = Field(..., gt=0)
    effective_date: date
    description: Optional[str] = None


class UtilityRateCreate(UtilityRateBase):
    """水电费率创建 schema"""
    pass


class UtilityRateUpdate(BaseModel):
    """水电费率更新 schema"""
    rate_per_unit: Optional[Decimal] = Field(None, gt=0)
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

class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    items: list[T]
    total: int
    page: int
    size: int


# ==================== 提醒相关 ====================

class ReminderItem(BaseModel):
    """提醒项"""
    room_id: int
    room_number: str
    reminder_type: str  # lease_expiry, lease_overdue, payment_due, payment_overdue
    reminder_date: date
    days_left: int
    amount: float
    tenant_name: Optional[str] = None
    breakdown: Optional[dict] = None  # 费用明细
    message: str


class ReminderResponse(BaseModel):
    """提醒列表响应"""
    total: int
    reminders: list[ReminderItem]
    as_of_date: date
    pages: int


# ==================== 水电账单相关 ====================

class UtilityBillBase(BaseModel):
    """水电账单基础schema"""
    series: str = Field(..., min_length=1, max_length=50, description="房子系列（如102、102A、2-2501等）")
    year: int = Field(..., ge=2020, le=2100, description="年份")
    month: int = Field(..., ge=1, le=12, description="月份")
    utility_type: str = Field(..., pattern="^(water|electric)$", description="类型：water(水费)或electric(电费)")
    cost: float = Field(default=0, ge=0, description="费用支出（元）")
    notes: Optional[str] = Field(None, max_length=500, description="备注")


class UtilityBillCreate(UtilityBillBase):
    """创建水电账单"""
    pass


class UtilityBillUpdate(BaseModel):
    """更新水电账单"""
    cost: Optional[float] = Field(None, ge=0, description="费用支出（元）")
    notes: Optional[str] = Field(None, max_length=500, description="备注")


class UtilityBillResponse(UtilityBillBase):
    """水电账单响应"""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UtilityBillProfitStats(BaseModel):
    """水电收益统计"""
    total_water_profit: float = Field(description="累计水费收益")
    total_electric_profit: float = Field(description="累计电费收益")
    total_profit: float = Field(description="累计总收益")
    monthly_breakdown: list = Field(description="每月明细")


class BillWithProfit(UtilityBillResponse):
    """带收益信息的账单"""
    water_collected: float = Field(description="从租客收取的水费")
    electric_collected: float = Field(description="从租客收取的电费")
    water_profit: float = Field(description="水费收益")
    electric_profit: float = Field(description="电费收益")


# ==================== 租客相关 ====================

class TenantBase(BaseModel):
    """租客基础schema"""
    name: str = Field(..., min_length=1, max_length=100, description="姓名")
    phone: str = Field(..., min_length=1, max_length=20, description="联系电话")
    id_card: Optional[str] = Field(None, min_length=15, max_length=20, description="身份证号码")
    emergency_contact: Optional[str] = Field(None, max_length=100, description="紧急联系人")
    emergency_phone: Optional[str] = Field(None, max_length=20, description="紧急联系电话")
    notes: Optional[str] = Field(None, max_length=1000, description="备注")
    status: str = Field(default='active', description="状态: active=在租, inactive=已搬走")


class TenantCreate(TenantBase):
    """创建租客"""
    pass


class TenantUpdate(BaseModel):
    """更新租客"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="姓名")
    phone: Optional[str] = Field(None, min_length=1, max_length=20, description="联系电话")
    id_card: Optional[str] = Field(None, min_length=15, max_length=20, description="身份证号码")
    emergency_contact: Optional[str] = Field(None, max_length=100, description="紧急联系人")
    emergency_phone: Optional[str] = Field(None, max_length=20, description="紧急联系电话")
    notes: Optional[str] = Field(None, max_length=1000, description="备注")


class TenantResponse(TenantBase):
    """租客响应"""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================== 租赁记录相关 ====================

class LeaseRecordBase(BaseModel):
    """租赁记录基础schema"""
    tenant_id: int = Field(..., description="租客ID")
    room_id: int = Field(..., description="房间ID")
    lease_start: date = Field(..., description="租期开始日期")
    lease_end: date = Field(..., description="租期结束日期")
    monthly_rent: Decimal = Field(..., ge=0, description="月租金")
    deposit_amount: Optional[Decimal] = Field(None, ge=0, description="押金")
    is_active: bool = Field(True, description="是否当前生效")
    notes: Optional[str] = Field(None, max_length=1000, description="备注")
    initial_electricity_reading: Optional[Decimal] = Field(0, ge=0, description="初始电表读数")
    initial_water_reading: Optional[Decimal] = Field(0, ge=0, description="初始水表读数")


class LeaseRecordCreate(LeaseRecordBase):
    """创建租赁记录"""
    pass


class LeaseRecordUpdate(BaseModel):
    """更新租赁记录"""
    lease_start: Optional[date] = Field(None, description="租期开始日期")
    lease_end: Optional[date] = Field(None, description="租期结束日期")
    monthly_rent: Optional[Decimal] = Field(None, ge=0, description="月租金")
    deposit_amount: Optional[Decimal] = Field(None, ge=0, description="押金")
    is_active: Optional[bool] = Field(None, description="是否当前生效")
    notes: Optional[str] = Field(None, max_length=1000, description="备注")
    initial_electricity_reading: Optional[Decimal] = Field(None, ge=0, description="初始电表读数")
    initial_water_reading: Optional[Decimal] = Field(None, ge=0, description="初始水表读数")


class LeaseRecordResponse(LeaseRecordBase):
    """租赁记录响应"""
    id: int
    created_at: datetime
    updated_at: datetime
    tenant: TenantResponse = Field(description="租客信息")
    room: Optional['RoomResponse'] = Field(None, description="房间信息")

    model_config = ConfigDict(from_attributes=True)


class LeaseRecordWithRoom(LeaseRecordResponse):
    """带房间完整信息的租赁记录"""
    room: 'RoomResponse' = Field(description="房间信息")
    total_profit: float = Field(description="总收益")
