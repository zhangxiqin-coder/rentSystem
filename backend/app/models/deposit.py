# Deposit model for managing security deposits
from sqlalchemy import Column, Integer, String, Numeric, Date, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class Deposit(Base):
    """Security deposit model"""
    __tablename__ = "deposits"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)

    # Deposit amount
    amount = Column(Numeric(10, 2), nullable=False)

    # Status: 'held'（押金中）, 'refunded'（已退还）, 'deducted'（已抵扣）
    status = Column(String(20), default='held', nullable=False)

    # Date information
    deposit_date = Column(Date, nullable=False)  # 收款日期
    refund_date = Column(Date, nullable=True)  # 退还日期

    # Payment method: '现金', '微信', '支付宝', '银行转账'
    payment_method = Column(String(20), default='现金')

    # Deduction information (if applicable)
    deduction_reason = Column(Text, nullable=True)  # 抵扣原因
    deduction_amount = Column(Numeric(10, 2), nullable=True)  # 抵扣金额

    # Notes
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    room = relationship("Room", back_populates="deposits")
