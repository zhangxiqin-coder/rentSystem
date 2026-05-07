import json
import sqlite3
from pathlib import Path

db = Path(r"d:\codespace\rentSystem\backend\rent_management.db")
out = Path(r"d:\codespace\rentSystem\db_update_result.json")

result = {}

conn = sqlite3.connect(db, timeout=10)
cur = conn.cursor()

cur.execute("PRAGMA table_info(rooms)")
columns = [row[1] for row in cur.fetchall()]

if "building" not in columns:
    result = {
        "ok": False,
        "error": "rooms表不存在building字段",
        "columns": columns,
    }
else:
    cur.execute("SELECT COUNT(*) FROM rooms WHERE TRIM(CAST(building AS TEXT))='4'")
    before = cur.fetchone()[0]

    cur.execute(
        "UPDATE rooms SET building=? WHERE TRIM(CAST(building AS TEXT))='4'",
        ("登新公寓 4幢",),
    )
    affected = cur.rowcount
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM rooms WHERE TRIM(CAST(building AS TEXT))='4'")
    after_old = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM rooms WHERE building=?", ("登新公寓 4幢",))
    after_new = cur.fetchone()[0]

    cur.execute(
        "SELECT id, room_number, building FROM rooms WHERE building=? ORDER BY id LIMIT 20",
        ("登新公寓 4幢",),
    )
    samples = cur.fetchall()

    result = {
        "ok": True,
        "before": before,
        "affected": affected,
        "after_old": after_old,
        "after_new": after_new,
        "samples": samples,
    }

conn.close()
out.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
