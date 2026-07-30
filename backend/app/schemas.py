"""
Pydantic schemas 定义（统一数据模型）
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, TypeVar, Generic
from pydantic import BaseModel, ConfigDict, Field, EmailStr, model_validator, field_validator
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
    utility_type: Optional[str] = Field(None, pattern="^(water|electric)$", description="类型：water(水费)或electric(电费)")
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


# ==================== 房间居住人（多租客）相关 ====================

class RoomOccupantBase(BaseModel):
    """房间居住人基础schema"""
    room_id: int = Field(..., description="房间ID")
    tenant_id: int = Field(..., description="租客ID")
    role: str = Field(default="secondary", pattern="^(primary|secondary)$", description="primary=主租客(签合同), secondary=亲友")
    relation: Optional[str] = Field(None, max_length=50, description="与主租客关系：配偶/子女/父母/朋友/同事等")
    is_active: bool = Field(default=True, description="是否在住")


class RoomOccupantCreate(BaseModel):
    """创建房间居住人"""
    tenant_id: int = Field(..., description="租客ID")
    role: str = Field(default="secondary", pattern="^(primary|secondary)$", description="primary=主租客, secondary=亲友")
    relation: Optional[str] = Field(None, max_length=50, description="与主租客关系")
    is_active: bool = Field(default=True, description="是否在住")


class RoomOccupantUpdate(BaseModel):
    """更新房间居住人"""
    role: Optional[str] = Field(None, pattern="^(primary|secondary)$", description="primary=主租客, secondary=亲友")
    relation: Optional[str] = Field(None, max_length=50, description="与主租客关系")
    is_active: Optional[bool] = None


class RoomOccupantResponse(BaseModel):
    """房间居住人响应（含租客详细信息）"""
    id: int
    room_id: int
    tenant_id: int
    role: str
    relation: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # 关联的租客详细信息（前端展示用）
    tenant_name: Optional[str] = None
    tenant_phone: Optional[str] = None
    tenant_id_card: Optional[str] = None
    tenant_notes: Optional[str] = None

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
    status_display: Optional[str] = Field(None, description="根据租期计算的状态: pending/active/expired")

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def set_status_display(self):
        """根据租期时间自动计算状态"""
        if self.lease_start and self.lease_end:
            today = date.today()
            if self.lease_start > today:
                self.status_display = "pending"
            elif self.lease_end < today:
                self.status_display = "expired"
            else:
                self.status_display = "active"
        return self


class LeaseRecordWithRoom(LeaseRecordResponse):
    """带房间完整信息的租赁记录"""
    room: 'RoomResponse' = Field(description="房间信息")
    total_profit: float = Field(description="总收益")


# ==================== 个人资产 ====================

class AssetPlatformCreate(BaseModel):
    """创建资产平台"""
    name: str = Field(..., description="平台名称")
    current_balance: Decimal = Field(Decimal('0'), description="当前余额")
    total_earnings: Decimal = Field(Decimal('0'), description="累计收益")
    sort_order: int = Field(0, description="排序")
    is_asset: bool = Field(True, description="是否计入总资产")


class AssetPlatformUpdate(BaseModel):
    """更新资产平台"""
    name: Optional[str] = Field(None, description="平台名称")
    current_balance: Optional[Decimal] = Field(None, description="当前余额")
    total_earnings: Optional[Decimal] = Field(None, description="累计收益")
    sort_order: Optional[int] = Field(None, description="排序")
    is_active: Optional[bool] = Field(None, description="是否启用")


class AssetPlatformResponse(BaseModel):
    """资产平台响应"""
    id: int
    name: str
    current_balance: Decimal
    total_earnings: Decimal
    current_year: int = Field(2026, description="当前收益年份")
    yearly_earnings: dict[str, Decimal] = Field(default_factory=dict, description="历年收益")
    sort_order: int
    is_active: bool
    is_asset: bool = Field(True, description="是否计入总资产")
    created_at: datetime
    updated_at: datetime

    @field_validator('yearly_earnings', mode='before')
    @classmethod
    def parse_yearly_earnings(cls, v):
        if isinstance(v, str):
            import json
            try:
                data = json.loads(v)
                return {k: Decimal(str(v)) for k, v in data.items()}
            except (json.JSONDecodeError, ValueError):
                return {}
        return v or {}

    model_config = ConfigDict(from_attributes=True)


class AssetRecordCreate(BaseModel):
    """创建资产变动记录"""
    platform_id: int = Field(..., description="平台ID")
    record_type: str = Field(..., description="类型：balance/transfer_in/transfer_out")
    reported_balance: Optional[Decimal] = Field(None, description="上报余额（余额上报时必填）")
    reported_earnings: Optional[Decimal] = Field(None, description="上报累计收益（余额上报时必填）")
    amount: Optional[Decimal] = Field(None, description="转入/转出金额（transfer类型时必填）")
    notes: Optional[str] = Field(None, description="备注")


class AssetRecordUpdate(BaseModel):
    """编辑资产变动记录（仅超级管理员）"""
    reported_balance: Optional[Decimal] = Field(None, description="上报余额")
    reported_earnings: Optional[Decimal] = Field(None, description="上报累计收益")
    amount: Optional[Decimal] = Field(None, description="转入/转出金额")
    notes: Optional[str] = Field(None, description="备注")


class AssetRecordResponse(BaseModel):
    """资产变动记录响应"""
    id: int
    platform_id: int
    record_type: str
    reported_balance: Optional[Decimal] = None
    reported_earnings: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    calculated_transfer: Optional[Decimal] = None
    balance_before: Optional[Decimal] = None
    balance_after: Optional[Decimal] = None
    earnings_before: Optional[Decimal] = None
    earnings_after: Optional[Decimal] = None
    notes: Optional[str] = None
    created_at: datetime
    platform_name: Optional[str] = Field(None, description="平台名称")

    model_config = ConfigDict(from_attributes=True)


class AssetPlatformDetailResponse(AssetPlatformResponse):
    """资产平台详情（含记录）"""
    records: list[AssetRecordResponse] = Field(default_factory=list, description="变动记录")
    annualized_return: Optional[Decimal] = Field(None, description="年化收益率（当年收益/当前余额*100%）")


class AssetSummaryResponse(BaseModel):
    """资产总览"""
    total_balance: Decimal = Field(Decimal('0'), description="总资产")
    total_earnings: Decimal = Field(Decimal('0'), description="当前年份总收益")
    yearly_earnings: dict[str, Decimal] = Field(default_factory=dict, description="历年总收益 {2025: 1234.56, 2026: 5678.90}")
    current_year: int = Field(2026, description="当前收益年份")
    platforms: list[AssetPlatformDetailResponse] = Field(default_factory=list, description="各平台详情")


class AssetTrendPoint(BaseModel):
    """趋势数据点"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    total_balance: Decimal = Field(Decimal('0'), description="当日总资产")
    total_earnings: Decimal = Field(Decimal('0'), description="当日总收益")
    earnings_delta: Decimal = Field(Decimal('0'), description="当日收益变化")


class PlatformTrendPoint(BaseModel):
    """单个平台趋势点"""
    date: str
    name: str
    balance: Decimal
    earnings: Decimal


class AssetTrendResponse(BaseModel):
    """资产趋势响应"""
    points: list[AssetTrendPoint] = Field(default_factory=list, description="趋势数据点")
    platforms: list[PlatformTrendPoint] = Field(default_factory=list, description="各平台趋势")


class ZhaopingfeiYearSummary(BaseModel):
    """赵平飞年度统计"""
    year: str = Field(..., description="年份")
    transfer_in: Decimal = Field(Decimal('0'), description="转入合计")
    transfer_out: Decimal = Field(Decimal('0'), description="转出合计")
    net: Decimal = Field(Decimal('0'), description="净转入")


class ZhaopingfeiSummaryResponse(BaseModel):
    """赵平飞统计响应"""
    years: list[ZhaopingfeiYearSummary] = Field(default_factory=list, description="各年统计")
    total_in: Decimal = Field(Decimal('0'), description="总转入")
    total_out: Decimal = Field(Decimal('0'), description="总转出")
    total_net: Decimal = Field(Decimal('0'), description="总净转入")


# ==================== 固定资产 ====================


class FixedAssetCreate(BaseModel):
    name: str
    category: str
    estimated_value: Decimal = Decimal('0')
    role: Optional[str] = None
    monthly_rent: Optional[Decimal] = None
    notes: Optional[str] = None
    sort_order: int = 0


class FixedAssetUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    estimated_value: Optional[Decimal] = None
    role: Optional[str] = None
    monthly_rent: Optional[Decimal] = None
    notes: Optional[str] = None
    sort_order: Optional[int] = None


class FixedAssetResponse(BaseModel):
    id: int
    name: str
    category: str
    estimated_value: Decimal
    role: Optional[str] = None
    monthly_rent: Optional[Decimal] = None
    notes: Optional[str] = None
    sort_order: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==================== 资产快照 ====================


class AssetSnapshotCreate(BaseModel):
    notes: Optional[str] = None


class AssetSnapshotResponse(BaseModel):
    id: int
    snapshot_date: date
    snapshot_data: list
    total_amount: Decimal
    platform_summary: Optional[dict] = None
    notes: Optional[str] = None
    created_at: datetime

    @field_validator('snapshot_data', mode='before')
    @classmethod
    def parse_list_json(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return []
        return v or []

    @field_validator('platform_summary', mode='before')
    @classmethod
    def parse_dict_json(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return {}
        return v or {}

    model_config = ConfigDict(from_attributes=True)


# ==================== 持仓明细（资产项） ====================


class AssetItemCreate(BaseModel):
    """创建持仓项"""
    name: str = Field(..., description="资产名称")
    code: Optional[str] = Field(None, description="编号")
    amount: Decimal = Field(Decimal('0'), description="持仓金额")
    stock_pct: Decimal = Field(Decimal('0'), description="股票占比%")
    bond_pct: Decimal = Field(Decimal('0'), description="债权占比%")
    cash_pct: Decimal = Field(Decimal('0'), description="现金占比%")
    commodity_pct: Decimal = Field(Decimal('0'), description="商品占比%")
    fixed_income_pct: Decimal = Field(Decimal('0'), description="固收占比%")
    other_pct: Decimal = Field(Decimal('0'), description="其他占比%")
    platform_id: Optional[int] = Field(None, description="所属平台ID")
    sort_order: int = Field(0, description="排序")


class AssetItemUpdate(BaseModel):
    """更新持仓项"""
    name: Optional[str] = Field(None, description="资产名称")
    code: Optional[str] = Field(None, description="编号")
    amount: Optional[Decimal] = Field(None, description="持仓金额")
    stock_pct: Optional[Decimal] = Field(None, description="股票占比%")
    bond_pct: Optional[Decimal] = Field(None, description="债权占比%")
    cash_pct: Optional[Decimal] = Field(None, description="现金占比%")
    commodity_pct: Optional[Decimal] = Field(None, description="商品占比%")
    fixed_income_pct: Optional[Decimal] = Field(None, description="固收占比%")
    other_pct: Optional[Decimal] = Field(None, description="其他占比%")
    platform_id: Optional[int] = Field(None, description="所属平台ID")
    sort_order: Optional[int] = Field(None, description="排序")


class AssetItemResponse(BaseModel):
    """持仓项响应"""
    id: int
    name: str
    code: Optional[str] = None
    amount: Decimal
    stock_pct: Decimal
    bond_pct: Decimal
    cash_pct: Decimal
    commodity_pct: Decimal
    fixed_income_pct: Decimal
    other_pct: Decimal
    platform_id: Optional[int] = None
    platform_name: Optional[str] = None
    sort_order: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PortfolioSummaryResponse(BaseModel):
    """资产组合汇总"""
    total_amount: Decimal = Decimal('0')
    stock_amount: Decimal = Decimal('0')
    bond_amount: Decimal = Decimal('0')
    cash_amount: Decimal = Decimal('0')
    commodity_amount: Decimal = Decimal('0')
    fixed_income_amount: Decimal = Decimal('0')
    other_amount: Decimal = Decimal('0')
    stock_pct: Decimal = Decimal('0')
    bond_pct: Decimal = Decimal('0')
    cash_pct: Decimal = Decimal('0')
    commodity_pct: Decimal = Decimal('0')
    fixed_income_pct: Decimal = Decimal('0')
    other_pct: Decimal = Decimal('0')
