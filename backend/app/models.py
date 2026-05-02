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
    lease_start = Column(Date)
    lease_end = Column(Date)
    last_payment_date = Column(Date)
    description = Column(Text)
    owner_id = Column(Integer, nullable=True, index=True)  # 用户隔离字段
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
