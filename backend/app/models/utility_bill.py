"""水电账单模型 - 记录每月交给国网和电网的费用"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, UniqueConstraint
from app.database import Base


class UtilityBill(Base):
    """水电账单表"""
    __tablename__ = "utility_bills"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, comment="年份")
    month = Column(Integer, nullable=False, comment="月份 (1-12)")
    water_cost = Column(Float, default=0, comment="水费支出（元）")
    electric_cost = Column(Float, default=0, comment="电费支出（元）")
    notes = Column(String(500), nullable=True, comment="备注")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 唯一约束：同年同月只能有一条记录
    __table_args__ = (
        UniqueConstraint('year', 'month', name='unique_year_month'),
    )

    def __repr__(self):
        return f"<UtilityBill {self.year}-{self.month:02d}: 水费={self.water_cost}, 电费={self.electric_cost}>"
