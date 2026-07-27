import sys
sys.path.insert(0, ".")
from app.database import engine, sync_to_cloud
from sqlalchemy import text

sync_to_cloud()

with engine.connect() as conn:
    # 先看表结构
    cols = conn.execute(text("PRAGMA table_info(utility_readings)")).fetchall()
    print("=== utility_readings 表结构 ===")
    for c in cols:
        print(f"  {c[1]} ({c[2]})")
    
    # 502-2房间 id=26, tenant_id=33
    print("\n=== 502-2 房间 (id=26) ===")
    
    # 查所有水电记录
    utils = conn.execute(text("""
        SELECT * FROM utility_readings WHERE room_id = 26 ORDER BY reading_date DESC
    """)).fetchall()
    col_names = [c[1] for c in cols]
    print(f"水电记录 ({len(utils)}条):")
    for u in utils:
        d = dict(zip(col_names, u))
        print(f"  {d}")
    
    # 查租客
    tenant = conn.execute(text("SELECT id, name, phone FROM tenants WHERE id = 33")).fetchone()
    print(f"\n租客: {tenant}")
    
    # 查该房间的lease
    leases = conn.execute(text("SELECT * FROM lease_records WHERE room_id = 26 ORDER BY lease_start DESC")).fetchall()
    print(f"\n租约记录 ({len(leases)}条):")
    lease_cols = [c[1] for c in conn.execute(text("PRAGMA table_info(lease_records)")).fetchall()]
    for l in leases:
        d = dict(zip(lease_cols, l))
        print(f"  {d}")
