#!/usr/bin/env python3
"""
数据库迁移脚本：统一前后端数据模型
版本: v1.0 -> v2.0

使用方法:
    python migrations/migrate_to_v2.py

注意事项:
    1. 运行前请备份数据库文件 rent_management.db
    2. 确保虚拟环境已激活
    3. 该脚本会自动处理数据迁移和字段填充
"""
import sys
import os
from datetime import datetime
from decimal import Decimal

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text
from app.database import engine, SessionLocal


def migrate_database():
    """执行数据库迁移"""

    print("=" * 60)
    print("开始数据库迁移: v1.0 -> v2.0")
    print("=" * 60)

    db = SessionLocal()

    try:
        # ==================== 步骤 1: 检查数据库状态 ====================
        print("\n[1/7] 检查数据库状态...")

        # 检查是否已经迁移过
        result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'"))
        tables = [row[0] for row in result]

        if 'users' not in tables:
            print("  ⚠️  数据库为空，将创建新表")
            from app.models import Base
            Base.metadata.create_all(bind=engine)
            print("  ✓ 数据库表创建完成")
            return

        # 检查是否已有 role 字段（判断是否已迁移）
        try:
            result = db.execute(text("SELECT role FROM users LIMIT 1"))
            print("  ✓ 数据库已迁移，跳过")
            return
        except Exception:
            print("  ✓ 检测到旧版本数据库，开始迁移...")

        # ==================== 步骤 2: 备份 ====================
        print("\n[2/7] 创建数据库备份...")
        backup_path = f"rent_management_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        import shutil
        shutil.copy2("rent_management.db", backup_path)
        print(f"  ✓ 备份已创建: {backup_path}")

        # ==================== 步骤 3: 迁移 users 表 ====================
        print("\n[3/7] 迁移 users 表...")

        # 添加新字段
        try:
            db.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR(100)"))
            print("  ✓ 添加 full_name 字段")
        except Exception:
            print("  - full_name 字段已存在，跳过")

        try:
            db.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'landlord'"))
            print("  ✓ 添加 role 字段")
        except Exception:
            print("  - role 字段已存在，跳过")

        try:
            db.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1"))
            print("  ✓ 添加 is_active 字段")
        except Exception:
            print("  - is_active 字段已存在，跳过")

        try:
            db.execute(text("ALTER TABLE users ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
            print("  ✓ 添加 updated_at 字段")
        except Exception:
            print("  - updated_at 字段已存在，跳过")

        # 初始化 role 字段
        db.execute(text("UPDATE users SET role = 'landlord' WHERE role IS NULL"))
        db.commit()
        print("  ✓ users 表迁移完成")

        # ==================== 步骤 4: 迁移 rooms 表 ====================
        print("\n[4/7] 迁移 rooms 表...")

        # 检查新字段是否存在
        try:
            db.execute(text("SELECT room_number FROM rooms LIMIT 1"))
            print("  - rooms 表已是新结构，跳过重建")
        except Exception:
            # 创建新表
            print("  - 创建新的 rooms 表结构...")
            db.execute(text("""
                CREATE TABLE rooms_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_number VARCHAR(50) UNIQUE NOT NULL,
                    building VARCHAR(50),
                    floor INTEGER,
                    area DECIMAL(10, 2),
                    monthly_rent DECIMAL(10, 2) NOT NULL,
                    deposit_amount DECIMAL(10, 2),
                    payment_cycle INTEGER DEFAULT 1 NOT NULL,
                    status VARCHAR(20) DEFAULT 'available' NOT NULL,
                    tenant_name VARCHAR(100),
                    tenant_phone VARCHAR(20),
                    lease_start DATE,
                    lease_end DATE,
                    last_payment_date DATE,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    CHECK (lease_end > lease_start)
                )
            """))

            # 迁移数据
            print("  - 迁移现有数据...")
            db.execute(text("""
                INSERT INTO rooms_new (
                    id, room_number, monthly_rent, tenant_name, tenant_phone,
                    lease_start, lease_end, payment_cycle, last_payment_date,
                    created_at, status, description
                )
                SELECT
                    id,
                    name AS room_number,
                    monthly_rent,
                    tenant_name,
                    tenant_phone,
                    lease_start,
                    lease_end,
                    payment_cycle,
                    last_payment_date,
                    created_at,
                    'available' AS status,
                    NULL AS description
                FROM rooms
            """))

            # 删除旧表，重命名新表
            db.execute(text("DROP TABLE rooms"))
            db.execute(text("ALTER TABLE rooms_new RENAME TO rooms"))
            db.commit()
            print("  ✓ rooms 表迁移完成")

        # ==================== 步骤 5: 迁移 payments 表 ====================
        print("\n[5/7] 迁移 payments 表...")

        try:
            db.execute(text("ALTER TABLE payments ADD COLUMN payment_type VARCHAR(20) DEFAULT 'rent'"))
            print("  ✓ 添加 payment_type 字段")
        except Exception:
            print("  - payment_type 字段已存在，跳过")

        try:
            db.execute(text("ALTER TABLE payments ADD COLUMN due_date DATE"))
            print("  ✓ 添加 due_date 字段")
        except Exception:
            print("  - due_date 字段已存在，跳过")

        try:
            db.execute(text("ALTER TABLE payments ADD COLUMN status VARCHAR(20) DEFAULT 'completed'"))
            print("  ✓ 添加 status 字段")
        except Exception:
            print("  - status 字段已存在，跳过")

        try:
            db.execute(text("ALTER TABLE payments ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
            print("  ✓ 添加 updated_at 字段")
        except Exception:
            print("  - updated_at 字段已存在，跳过")

        # 初始化字段
        db.execute(text("UPDATE payments SET payment_type = 'rent' WHERE payment_type IS NULL"))
        db.execute(text("UPDATE payments SET status = 'completed' WHERE status IS NULL"))
        db.commit()
        print("  ✓ payments 表迁移完成")

        # ==================== 步骤 6: 迁移 utility_readings 表 ====================
        print("\n[6/7] 迁移 utility_readings 表...")

        try:
            db.execute(text("ALTER TABLE utility_readings ADD COLUMN previous_reading DECIMAL(10, 2)"))
            print("  ✓ 添加 previous_reading 字段")
        except Exception:
            print("  - previous_reading 字段已存在，跳过")

        try:
            db.execute(text("ALTER TABLE utility_readings ADD COLUMN usage DECIMAL(10, 2)"))
            print("  ✓ 添加 usage 字段")
        except Exception:
            print("  - usage 字段已存在，跳过")

        try:
            db.execute(text("ALTER TABLE utility_readings ADD COLUMN amount DECIMAL(10, 2)"))
            print("  ✓ 添加 amount 字段")
        except Exception:
            print("  - amount 字段已存在，跳过")

        try:
            db.execute(text("ALTER TABLE utility_readings ADD COLUMN rate_used DECIMAL(10, 4)"))
            print("  ✓ 添加 rate_used 字段")
        except Exception:
            print("  - rate_used 字段已存在，跳过")

        try:
            db.execute(text("ALTER TABLE utility_readings ADD COLUMN recorded_by INTEGER"))
            print("  ✓ 添加 recorded_by 字段")
        except Exception:
            print("  - recorded_by 字段已存在，跳过")

        try:
            db.execute(text("ALTER TABLE utility_readings ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
            print("  ✓ 添加 updated_at 字段")
        except Exception:
            print("  - updated_at 字段已存在，跳过")

        # 重命名字段 note -> notes（需要重建表）
        try:
            db.execute(text("SELECT notes FROM utility_readings LIMIT 1"))
            print("  - notes 字段已存在，跳过重命名")
        except Exception:
            print("  - 重命名 note 字段为 notes...")
            db.execute(text("""
                CREATE TABLE utility_readings_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    utility_type VARCHAR(10) NOT NULL,
                    reading DECIMAL(10, 2) NOT NULL,
                    reading_date DATE NOT NULL,
                    previous_reading DECIMAL(10, 2),
                    usage DECIMAL(10, 2),
                    amount DECIMAL(10, 2),
                    rate_used DECIMAL(10, 4),
                    recorded_by INTEGER,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    CHECK (utility_type IN ('water', 'electricity', 'gas')),
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
                )
            """))
            db.execute(text("""
                INSERT INTO utility_readings_new (
                    id, room_id, utility_type, reading, reading_date,
                    previous_reading, usage, amount, rate_used,
                    notes, created_at
                )
                SELECT
                    id, room_id, utility_type, reading, reading_date,
                    NULL, NULL, NULL, NULL,
                    note, created_at
                FROM utility_readings
            """))
            db.execute(text("DROP TABLE utility_readings"))
            db.execute(text("ALTER TABLE utility_readings_new RENAME TO utility_readings"))
            db.commit()
            print("  ✓ utility_readings 表迁移完成")

        # ==================== 步骤 7: 迁移 utility_rates 表 ====================
        print("\n[7/7] 迁移 utility_rates 表...")

        # 重命名字段 unit_price -> rate_per_unit
        try:
            db.execute(text("SELECT rate_per_unit FROM utility_rates LIMIT 1"))
            print("  - rate_per_unit 字段已存在，跳过重命名")
        except Exception:
            print("  - 重命名 unit_price 为 rate_per_unit...")
            db.execute(text("""
                CREATE TABLE utility_rates_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    utility_type VARCHAR(10) NOT NULL,
                    rate_per_unit DECIMAL(10, 4) NOT NULL,
                    effective_date DATE NOT NULL,
                    is_active BOOLEAN DEFAULT 1 NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    CHECK (utility_type IN ('water', 'electricity', 'gas'))
                )
            """))
            db.execute(text("""
                INSERT INTO utility_rates_new (
                    id, utility_type, rate_per_unit, effective_date,
                    is_active, description, created_at
                )
                SELECT
                    id, utility_type, unit_price, effective_date,
                    1, NULL, created_at
                FROM utility_rates
            """))
            db.execute(text("DROP TABLE utility_rates"))
            db.execute(text("ALTER TABLE utility_rates_new RENAME TO utility_rates"))
            db.commit()
            print("  ✓ utility_rates 表迁移完成")

        # ==================== 步骤 8: 初始化默认数据 ====================
        print("\n[8/8] 初始化默认数据...")

        # 检查是否已有费率数据
        result = db.execute(text("SELECT COUNT(*) FROM utility_rates"))
        rate_count = result.scalar()

        if rate_count == 0:
            print("  - 插入默认水电费率...")
            db.execute(text("""
                INSERT INTO utility_rates (utility_type, rate_per_unit, effective_date, description, is_active)
                VALUES ('water', 5.0, DATE('now'), '默认水费率（5元/吨）', 1)
            """))
            db.execute(text("""
                INSERT INTO utility_rates (utility_type, rate_per_unit, effective_date, description, is_active)
                VALUES ('electricity', 1.0, DATE('now'), '默认电费率（1元/度）', 1)
            """))
            db.commit()
            print("  ✓ 默认费率已创建（水：5元/吨，电：1元/度）")
        else:
            print("  - 费率数据已存在，跳过")

        # ==================== 验证迁移结果 ====================
        print("\n" + "=" * 60)
        print("迁移完成！验证结果：")
        print("=" * 60)

        tables_info = [
            ("Users", "users"),
            ("Rooms", "rooms"),
            ("Payments", "payments"),
            ("Utility Readings", "utility_readings"),
            ("Utility Rates", "utility_rates"),
        ]

        for name, table in tables_info:
            result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            print(f"  ✓ {name}: {count} 条记录")

        print("\n" + "=" * 60)
        print("数据库迁移成功完成！")
        print("=" * 60)
        print(f"\n备份文件: {backup_path}")
        print("如果迁移出现问题，可以恢复备份文件。")

    except Exception as e:
        print(f"\n❌ 迁移失败: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        print("\n数据库已回滚，请检查错误信息。")
        sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    # 检查数据库文件是否存在
    if not os.path.exists("rent_management.db"):
        print("错误: rent_management.db 文件不存在")
        print("请确保在正确的目录下运行此脚本")
        sys.exit(1)

    # 执行迁移
    migrate_database()
