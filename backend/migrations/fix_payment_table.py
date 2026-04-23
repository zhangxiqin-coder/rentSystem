#!/usr/bin/env python3
"""
修复数据库列名：将 payments 表的 note 列重命名为 description
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text
from app.database import SessionLocal


def fix_payment_table():
    """修复 payments 表的列名"""
    db = SessionLocal()

    try:
        print("检查 payments 表结构...")

        # 检查是否有 note 列
        result = db.execute(text("PRAGMA table_info(payments)"))
        columns = [row[1] for row in result]

        if 'note' in columns and 'description' not in columns:
            print("  - 发现 note 列，需要重命名为 description")

            # SQLite 不支持直接重命名列，需要重建表
            print("  - 重建 payments 表...")

            # 创建新表
            db.execute(text("""
                CREATE TABLE payments_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    amount DECIMAL(10, 2) NOT NULL,
                    payment_type VARCHAR(20) DEFAULT 'rent',
                    payment_date DATE NOT NULL,
                    due_date DATE,
                    status VARCHAR(20) DEFAULT 'completed',
                    payment_method VARCHAR(50),
                    description TEXT,
                    receipt_image VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
                )
            """))

            # 复制数据
            db.execute(text("""
                INSERT INTO payments_new (
                    id, room_id, amount, payment_type, payment_date, due_date, status,
                    payment_method, description, receipt_image, created_at, updated_at
                )
                SELECT
                    id, room_id, amount, payment_type, payment_date, due_date, status,
                    payment_method, note, receipt_image, created_at, updated_at
                FROM payments
            """))

            # 删除旧表
            db.execute(text("DROP TABLE payments"))

            # 重命名新表
            db.execute(text("ALTER TABLE payments_new RENAME TO payments"))

            # 重建索引
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_payment_room_date ON payments(room_id, payment_date)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_payment_type ON payments(payment_type)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_payment_status ON payments(status)"))

            db.commit()

            print("  ✓ payments 表修复完成")
        elif 'description' in columns:
            print("  ✓ description 列已存在，无需修复")
        else:
            print("  ⚠️  未找到 note 或 description 列")

        # 验证结果
        result = db.execute(text("PRAGMA table_info(payments)"))
        columns = [row[1] for row in result]
        print(f"\n当前 payments 表列: {columns}")

        if 'description' in columns:
            print("\n✓ 修复成功！")
        else:
            print("\n⚠️  修复可能失败")

    except Exception as e:
        print(f"\n❌ 修复失败: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    fix_payment_table()
