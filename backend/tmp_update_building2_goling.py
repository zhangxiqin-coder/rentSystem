import json
import sqlite3
from pathlib import Path

db = Path(r"d:\codespace\rentSystem\backend\rent_management.db")
out = Path(r"d:\codespace\rentSystem\db_update_building2_goling_result.json")

conn = sqlite3.connect(db, timeout=10)
cur = conn.cursor()

cur.execute("PRAGMA table_info(rooms)")
columns = [row[1] for row in cur.fetchall()]

if "building" not in columns or "room_number" not in columns:
    result = {
        "ok": False,
        "error": "rooms表缺少building或room_number字段",
        "columns": columns,
    }
else:
    cur.execute(
        "SELECT COUNT(*) FROM rooms "
        "WHERE room_number LIKE '2-%' AND TRIM(CAST(building AS TEXT))='2'"
    )
    before = cur.fetchone()[0]

    cur.execute(
        "UPDATE rooms SET building=? "
        "WHERE room_number LIKE '2-%' AND TRIM(CAST(building AS TEXT))='2'",
        ("果岭2幢",),
    )
    affected = cur.rowcount
    conn.commit()

    cur.execute(
        "SELECT COUNT(*) FROM rooms "
        "WHERE room_number LIKE '2-%' AND TRIM(CAST(building AS TEXT))='2'"
    )
    after_old = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM rooms WHERE room_number LIKE '2-%' AND building=?",
        ("果岭2幢",),
    )
    after_new = cur.fetchone()[0]

    cur.execute(
        "SELECT id, room_number, building FROM rooms "
        "WHERE room_number LIKE '2-%' AND building=? "
        "ORDER BY id LIMIT 30",
        ("果岭2幢",),
    )
    samples = cur.fetchall()

    result = {
        "ok": True,
        "rule": "room_number LIKE '2-%' AND building='2'",
        "before": before,
        "affected": affected,
        "after_old": after_old,
        "after_new": after_new,
        "samples": samples,
    }

conn.close()
out.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
