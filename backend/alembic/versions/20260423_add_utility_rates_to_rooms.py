"""add utility rates to rooms

Revision ID: 20260423_add_utility_rates
Revises: 
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import DECIMAL


# revision identifiers, used by Alembic.
revision = '20260423_add_utility_rates'
down_revision = None  # 设置为实际的上一个迁移ID
branch_labels = None
depends_on = None


def upgrade():
    """添加水电费率字段到rooms表"""
    # 添加水费率字段，默认5.00
    op.add_column('rooms', sa.Column(
        'water_rate',
        DECIMAL(10, 2),
        nullable=False,
        server_default='5.00'
    ))

    # 添加电费率字段，默认1.00
    op.add_column('rooms', sa.Column(
        'electricity_rate',
        DECIMAL(10, 2),
        nullable=False,
        server_default='1.00'
    ))


def downgrade():
    """移除水电费率字段"""
    op.drop_column('rooms', 'electricity_rate')
    op.drop_column('rooms', 'water_rate')
