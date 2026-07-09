"""
SQLAlchemy 数据库模型定义（统一数据模型）
"""
from sqlalchemy import Column, Integer, String, Text, DECIMAL, Date, DateTime, ForeignKey, CheckConstraint, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from decimal import Decimal
from passlib.context import CryptContext
from datetime import datetime

from app.database import Base

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class PaymentMethod(str):
    """支付方式枚举"""
    CASH = "现金"
    BANK_TRANSFER = "银行转账"
    ALIPAY = "支付宝"
    WECHAT = "微信支付"


class UserRole(str):
    """用户角色枚举"""
    ADMIN = "admin"
    SUPER_LANDLORD = "super_landlord"
    LANDLORD = "landlord"
    TENANT = "tenant"


class RoomStatus(str):
    """房间状态枚举"""
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"


class PaymentType(str):
    """支付类型枚举"""
    RENT = "rent"
    DEPOSIT = "deposit"
    UTILITY = "utility"
    REFUND = "refund"  # 退租退款
    OTHER = "other"


class PaymentStatus(str):
    """支付状态枚举"""
    PENDING = "pending"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class UtilityType(str):
    """水电类型枚举"""
    WATER = "water"
    ELECTRICITY = "electricity"
    GAS = "gas"


class User(Base):
    """用户模型"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100))
    full_name = Column(String(100))
    role = Column(String(20), nullable=False, default="landlord", index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # 甲方（房东）信息
    landlord_name = Column(String(100))
    landlord_phone = Column(String(20))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    recorded_readings = relationship("UtilityReading", back_populates="recorded_by_user")

    def set_password(self, password: str) -> None:
        """设置密码（哈希存储）"""
        self.password_hash = pwd_context.hash(password)

    def verify_password(self, password: str) -> bool:
        """验证密码"""
        return pwd_context.verify(password, self.password_hash)

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"


class Room(Base):
    """房间模型（统一前后端）"""
    __tablename__ = "rooms"
    __table_args__ = (
        CheckConstraint('lease_end > lease_start', name='check_lease_dates'),
        Index('idx_room_status', 'status'),
        Index('idx_room_tenant', 'tenant_name'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_number = Column(String(50), unique=True, nullable=False, index=True)
    building = Column(String(50))
    floor = Column(Integer)
    area = Column(DECIMAL(10, 2))
    monthly_rent = Column(DECIMAL(10, 2), nullable=False)
    deposit_amount = Column(DECIMAL(10, 2))
    payment_cycle = Column(Integer, default=1, nullable=False)
    water_rate = Column(DECIMAL(10, 2), default=5.00, nullable=False)
    electricity_rate = Column(DECIMAL(10, 2), default=1.00, nullable=False)
    status = Column(String(20), nullable=False, default="available")
    tenant_name = Column(String(100))
    tenant_phone = Column(String(20))
    tenant_id_card = Column(String(18))  # 租客身份证号码（18位）
    tenant_id = Column(Integer, nullable=True)  # 关联租客ID
    initial_electricity_reading = Column(DECIMAL(10, 2), default=0)  # 初始电表读数
    initial_water_reading = Column(DECIMAL(10, 2), default=0)  # 初始水表读数
    broadband_fee = Column(DECIMAL(10, 2), default=0)  # 宽带费
    lease_start = Column(Date)
    lease_end = Column(Date)
    last_payment_date = Column(Date)
    description = Column(Text)
    owner_id = Column(Integer, nullable=True, index=True)  # 用户隔离字段
    series = Column(String(50), nullable=True)  # 房间系列（如102、102A、2-2501等）
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    payments = relationship("Payment", back_populates="room", cascade="all, delete-orphan")
    utility_readings = relationship("UtilityReading", back_populates="room", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Room(id={self.id}, room_number='{self.room_number}', status='{self.status}')>"


class Payment(Base):
    """支付记录模型（统一前后端）"""
    __tablename__ = "payments"
    __table_args__ = (
        Index('idx_payment_room_date', 'room_id', 'payment_date'),
        Index('idx_payment_type', 'payment_type'),
        Index('idx_payment_status', 'status'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    payment_type = Column(String(20), nullable=False, default="rent")
    payment_date = Column(Date, nullable=False, index=True)
    due_date = Column(Date)
    period_start = Column(Date)
    period_end = Column(Date)
    status = Column(String(20), nullable=False, default="completed")
    payment_method = Column(String(50))
    description = Column(Text)
    receipt_image = Column(String(255))
    owner_id = Column(Integer, nullable=True, index=True)  # 用户隔离字段
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    room = relationship("Room", back_populates="payments")

    def __repr__(self):
        return f"<Payment(id={self.id}, room_id={self.room_id}, amount={self.amount}, type='{self.payment_type}')>"


class Tenant(Base):
    """租客模型：独立管理租客信息"""
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    id_card = Column(String(20), unique=True, nullable=False, index=True)
    emergency_contact = Column(String(100))
    emergency_phone = Column(String(20))
    notes = Column(Text)
    status = Column(String(20), default='active', nullable=False)  # active: 在租, inactive: 已搬走
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    owner = relationship("User", foreign_keys=[owner_id])
    lease_records = relationship("LeaseRecord", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tenant(id={self.id}, name='{self.name}', id_card='{self.id_card}')>"


class LeaseRecord(Base):
    """租赁记录表：记录租客在不同房间的租赁历史"""
    __tablename__ = "lease_records"
    __table_args__ = (
        CheckConstraint('lease_end > lease_start', name='check_lease_dates'),
        Index('idx_lease_tenant_date', 'tenant_id', 'lease_start'),
        Index('idx_lease_room_date', 'room_id', 'lease_start'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    lease_start = Column(Date, nullable=False)
    lease_end = Column(Date, nullable=False)
    monthly_rent = Column(DECIMAL(10, 2), nullable=False)
    deposit_amount = Column(DECIMAL(10, 2))
    is_active = Column(Boolean, default=True, index=True)  # 是否当前生效
    notes = Column(Text)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    initial_electricity_reading = Column(DECIMAL(10, 2), server_default="0")  # 初始电表读数
    initial_water_reading = Column(DECIMAL(10, 2), server_default="0")  # 初始水表读数
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    tenant = relationship("Tenant", back_populates="lease_records")
    room = relationship("Room")
    owner = relationship("User", foreign_keys=[owner_id])

    def __repr__(self):
        return f"<LeaseRecord(id={self.id}, tenant_id={self.tenant_id}, room_id={self.room_id}, lease_start={self.lease_start})>"
    
    @property
    def computed_status(self) -> str:
        """
        根据租期时间计算当前状态：
        - pending: 待生效（还未开始）
        - active: 生效中（当前日期在租期内）
        - expired: 已结束（租期已过）
        """
        from datetime import date
        today = date.today()
        if self.lease_start > today:
            return "pending"
        elif self.lease_end < today:
            return "expired"
        else:
            return "active"


class UtilityReading(Base):
    """水电抄表记录模型（统一前后端）"""
    __tablename__ = "utility_readings"
    __table_args__ = (
        CheckConstraint("utility_type IN ('water', 'electricity', 'gas')", name='check_utility_type'),
        Index('idx_reading_room_type_date', 'room_id', 'utility_type', 'reading_date'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    utility_type = Column(String(10), nullable=False, index=True)
    reading = Column(DECIMAL(10, 2), nullable=False)
    reading_date = Column(Date, nullable=False, index=True)
    previous_reading = Column(DECIMAL(10, 2))
    usage = Column(DECIMAL(10, 2))
    amount = Column(DECIMAL(10, 2))
    rate_used = Column(DECIMAL(10, 4))
    recorded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    payment_id = Column(Integer, ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)  # 关联的支付记录ID
    notes = Column(Text)
    owner_id = Column(Integer, nullable=True, index=True)  # 用户隔离字段
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    room = relationship("Room", back_populates="utility_readings")
    recorded_by_user = relationship("User", foreign_keys=[recorded_by])
    payment = relationship("Payment", foreign_keys=[payment_id])

    def __repr__(self):
        return f"<UtilityReading(id={self.id}, room_id={self.room_id}, type='{self.utility_type}', reading={self.reading})>"


class UtilityRate(Base):
    """水电费率模型（统一前后端）"""
    __tablename__ = "utility_rates"
    __table_args__ = (
        CheckConstraint("utility_type IN ('water', 'electricity', 'gas')", name='check_rate_utility_type'),
        Index('idx_rate_type_date', 'utility_type', 'effective_date'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    utility_type = Column(String(10), nullable=False, index=True)
    rate_per_unit = Column(DECIMAL(10, 4), nullable=False)
    effective_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<UtilityRate(id={self.id}, type='{self.utility_type}', rate={self.rate_per_unit}, active={self.is_active})>"


class UtilityBill(Base):
    """水电账单模型 - 记录每个房子系列每月交给国网和电网的费用"""
    __tablename__ = "utility_bills"
    __table_args__ = (
        Index('idx_bill_series_year_month_type', 'series', 'year', 'month', 'utility_type', unique=True),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    series = Column(String(50), nullable=False, comment="房子系列（如102、102A、2-2501等）")
    year = Column(Integer, nullable=False, comment="年份")
    month = Column(Integer, nullable=False, comment="月份 (1-12)")
    utility_type = Column(String(20), nullable=False, comment="类型：water(水费)或electric(电费)")
    cost = Column(DECIMAL(10, 2), default=0, comment="费用支出（元）")
    notes = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        type_name = "水费" if self.utility_type == "water" else "电费"
        return f"<UtilityBill(id={self.id}, series={self.series}, {self.year}-{self.month:02d}, {type_name}={self.cost})>"


class AssetPlatform(Base):
    """个人资产平台模型"""
    __tablename__ = "asset_platforms"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), nullable=False, comment="平台名称（支付宝、网商银行等）")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    current_balance = Column(DECIMAL(12, 2), default=0, comment="当前余额")
    total_earnings = Column(DECIMAL(12, 2), default=0, comment="累计收益")
    current_year = Column(Integer, default=2026, comment="当前收益年份")
    yearly_earnings = Column(Text, default="{}", comment="历年收益归 JSON {2025: 123.45, 2026: 678.90}")
    sort_order = Column(Integer, default=0, comment="排序")
    is_active = Column(Boolean, default=True, nullable=False)
    is_asset = Column(Boolean, default=True, nullable=False, comment="是否计入总资产")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    owner = relationship("User")

    def __repr__(self):
        return f"<AssetPlatform(id={self.id}, name='{self.name}', balance={self.current_balance})>"


class AssetRecord(Base):
    """资产变动记录模型"""
    __tablename__ = "asset_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    platform_id = Column(Integer, ForeignKey("asset_platforms.id"), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # 变动类型
    record_type = Column(String(10), nullable=False, comment="类型：balance(余额上报) / transfer_in(转入) / transfer_out(转出)")
    
    # 上报数据
    reported_balance = Column(DECIMAL(12, 2), nullable=True, comment="上报时的余额（余额上报时使用）")
    reported_earnings = Column(DECIMAL(12, 2), nullable=True, comment="上报时的累计收益（余额上报时使用）")
    amount = Column(DECIMAL(12, 2), nullable=True, comment="转入/转出金额（transfer类型时使用）")
    
    # 系统自动计算的结果
    calculated_transfer = Column(DECIMAL(12, 2), nullable=True, comment="系统算出的转入/转出净额（余额上报时记录）")
    balance_before = Column(DECIMAL(12, 2), nullable=True, comment="操作前余额")
    balance_after = Column(DECIMAL(12, 2), nullable=True, comment="操作后余额")
    earnings_before = Column(DECIMAL(12, 2), nullable=True, comment="操作前累计收益")
    earnings_after = Column(DECIMAL(12, 2), nullable=True, comment="操作后累计收益")
    
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    platform = relationship("AssetPlatform")
    owner = relationship("User")

    def __repr__(self):
        return f"<AssetRecord(id={self.id}, platform={self.platform_id}, type='{self.record_type}')>"


class AssetItem(Base):
    """个人资产持仓项（基金、ETF、组合等具体标的）"""
    __tablename__ = "asset_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False, comment="资产名称（如 易方达蓝筹精选、沪深300ETF）")
    code = Column(String(20), nullable=True, comment="编号（如 001、002）")
    amount = Column(DECIMAL(12, 2), default=Decimal('0'), comment="持仓金额")
    stock_pct = Column(DECIMAL(5, 2), default=Decimal('0'), comment="股票占比%")
    bond_pct = Column(DECIMAL(5, 2), default=Decimal('0'), comment="债权占比%")
    cash_pct = Column(DECIMAL(5, 2), default=Decimal('0'), comment="现金占比%")
    commodity_pct = Column(DECIMAL(5, 2), default=Decimal('0'), comment="商品占比%")
    fixed_income_pct = Column(DECIMAL(5, 2), default=Decimal('0'), comment="固收占比%")
    other_pct = Column(DECIMAL(5, 2), default=Decimal('0'), comment="其他占比%")
    platform_id = Column(Integer, ForeignKey("asset_platforms.id"), nullable=True, index=True, comment="所属平台")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    owner = relationship("User")
    platform = relationship("AssetPlatform")

    def __repr__(self):
        return f"<AssetItem(id={self.id}, name='{self.name}', amount={self.amount})>"


class AssetSnapshot(Base):
    """资产持仓快照（每半月记录一次）"""
    __tablename__ = "asset_snapshots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, comment="快照日期")
    snapshot_data = Column(Text, nullable=False, comment="快照数据 JSON，包含各平台持仓明细")
    total_amount = Column(DECIMAL(12, 2), default=Decimal('0'), comment="快照时持仓总金额")
    platform_summary = Column(Text, nullable=True, comment="平台余额快照 JSON")
    notes = Column(String(200), nullable=True, comment="备注")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    owner = relationship("User")

    def __repr__(self):
        return f"<AssetSnapshot(id={self.id}, date={self.snapshot_date}, total={self.total_amount})>"


class FixedAsset(Base):
    """固定资产（房产等）"""
    __tablename__ = "fixed_assets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False, comment="资产名称（如 府新花园）")
    category = Column(String(50), nullable=False, comment="类别（如 住房、商业）")
    estimated_value = Column(DECIMAL(12, 2), default=Decimal('0'), comment="估价")
    role = Column(String(100), nullable=True, comment="角色/用途（如 保值、居住/改善、现金流机器）")
    monthly_rent = Column(DECIMAL(12, 2), nullable=True, comment="月租金收入")
    notes = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    owner = relationship("User")

    def __repr__(self):
        return f"<FixedAsset(id={self.id}, name='{self.name}', value={self.estimated_value})>"
