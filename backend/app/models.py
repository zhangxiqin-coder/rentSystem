"""
SQLAlchemy 数据库模型定义
"""
from sqlalchemy import Column, Integer, String, Text, DECIMAL, Date, DateTime, ForeignKey, CheckConstraint, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from decimal import Decimal
from passlib.context import CryptContext
from enum import Enum

from app.database import Base

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class PaymentMethod(str, Enum):
    """支付方式枚举"""
    CASH = "现金"
    BANK_TRANSFER = "银行转账"
    ALIPAY = "支付宝"
    WECHAT = "微信支付"


class User(Base):
    """用户模型"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def set_password(self, password: str) -> None:
        """设置密码（哈希存储）"""
        self.password_hash = pwd_context.hash(password)
    
    def verify_password(self, password: str) -> bool:
        """验证密码"""
        return pwd_context.verify(password, self.password_hash)
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Room(Base):
    """房间模型"""
    __tablename__ = "rooms"
    __table_args__ = (
        CheckConstraint('lease_end > lease_start', name='check_lease_dates'),
    )
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    monthly_rent = Column(DECIMAL(10, 2), nullable=False)
    tenant_name = Column(String(100))
    tenant_phone = Column(String(20))
    lease_start = Column(Date)
    lease_end = Column(Date)
    payment_cycle = Column(Integer, default=1, nullable=False)
    last_payment_date = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # 关系
    payments = relationship("Payment", back_populates="room", cascade="all, delete-orphan")
    utility_readings = relationship("UtilityReading", back_populates="room", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Room(id={self.id}, name='{self.name}', monthly_rent={self.monthly_rent})>"


class Payment(Base):
    """交租记录模型"""
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    payment_date = Column(Date, nullable=False, index=True)
    payment_method = Column(SQLEnum(PaymentMethod), nullable=True)
    note = Column(Text)
    receipt_image = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # 关系
    room = relationship("Room", back_populates="payments")
    
    def __repr__(self):
        return f"<Payment(id={self.id}, room_id={self.room_id}, amount={self.amount}, payment_date={self.payment_date})>"


class UtilityReading(Base):
    """水电抄表记录模型"""
    __tablename__ = "utility_readings"
    __table_args__ = (
        CheckConstraint("utility_type IN ('water', 'electric')", name='check_utility_type'),
    )
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    utility_type = Column(String(10), nullable=False, index=True)
    reading = Column(DECIMAL(10, 2), nullable=False)
    reading_date = Column(Date, nullable=False, index=True)
    note = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # 关系
    room = relationship("Room", back_populates="utility_readings")
    
    def __repr__(self):
        return f"<UtilityReading(id={self.id}, room_id={self.room_id}, utility_type='{self.utility_type}', reading={self.reading})>"


class UtilityRate(Base):
    """水电费率模型"""
    __tablename__ = "utility_rates"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    utility_type = Column(String(10), unique=True, nullable=False, index=True)
    unit_price = Column(DECIMAL(10, 4), nullable=False)
    effective_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<UtilityRate(id={self.id}, utility_type='{self.utility_type}', unit_price={self.unit_price})>"
