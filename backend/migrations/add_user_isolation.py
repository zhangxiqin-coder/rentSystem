"""
用户隔离数据迁移
为Room、Payment、UtilityReading添加owner_id字段，并将现有数据归属到testuser3
"""
import sys
from pathlib import Path

# 添加项目路径到sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine, SessionLocal
from app.models import User, Room, Payment, UtilityReading

def migrate():
    """执行数据迁移"""
    print("🔄 开始用户隔离迁移...")

    with engine.connect() as conn:
        # 开始事务
        trans = conn.begin()
        try:
            # 1. 添加owner_id字段到rooms表
            print("\n1️⃣ 添加owner_id字段到rooms表...")
            conn.execute(text("ALTER TABLE rooms ADD COLUMN owner_id INTEGER"))
            print("   ✅ rooms表添加owner_id成功")

            # 2. 添加owner_id字段到payments表
            print("\n2️⃣ 添加owner_id字段到payments表...")
            conn.execute(text("ALTER TABLE payments ADD COLUMN owner_id INTEGER"))
            print("   ✅ payments表添加owner_id成功")

            # 3. 添加owner_id字段到utility_readings表
            print("\n3️⃣ 添加owner_id字段到utility_readings表...")
            conn.execute(text("ALTER TABLE utility_readings ADD COLUMN owner_id INTEGER"))
            print("   ✅ utility_readings表添加owner_id成功")

            # 4. 查找testuser3用户ID（房东姐姐）
            print("\n4️⃣ 查找房东姐姐用户...")
            db = SessionLocal()
            testuser3 = db.query(User).filter(User.username == "testuser3").first()
            if not testuser3:
                print("   ❌ 未找到testuser3用户！")
                trans.rollback()
                db.close()
                return
            print(f"   ✅ 找到房东姐姐: {testuser3.username} (ID: {testuser3.id})")
            db.close()

            # 5. 更新所有现有数据的owner_id
            print("\n5️⃣ 更新现有数据的owner_id...")
            result_rooms = conn.execute(text(f"UPDATE rooms SET owner_id = {testuser3.id} WHERE owner_id IS NULL"))
            print(f"   ✅ 更新了 {result_rooms.rowcount} 条房间记录")

            result_payments = conn.execute(text(f"UPDATE payments SET owner_id = {testuser3.id} WHERE owner_id IS NULL"))
            print(f"   ✅ 更新了 {result_payments.rowcount} 条支付记录")

            result_readings = conn.execute(text(f"UPDATE utility_readings SET owner_id = {testuser3.id} WHERE owner_id IS NULL"))
            print(f"   ✅ 更新了 {result_readings.rowcount} 条水电记录")

            # 6. 创建索引以优化查询性能
            print("\n6️⃣ 创建性能优化索引...")
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_room_owner ON rooms(owner_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payment_owner ON payments(owner_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_reading_owner ON utility_readings(owner_id)"))
            print("   ✅ 索引创建成功")

            # 提交事务
            trans.commit()
            print("\n✅ 迁移完成！所有数据已归属到房东姐姐账户")

        except Exception as e:
            print(f"\n❌ 迁移失败: {e}")
            trans.rollback()
            raise

if __name__ == "__main__":
    migrate()
