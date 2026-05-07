import json
import sqlite3
from pathlib import Path

db = Path(r"d:\codespace\rentSystem\backend\rent_management.db")
out = Path(r"d:\codespace\rentSystem\room201_probe.json")

conn = sqlite3.connect(db)
cur = conn.cursor()

result = {}

cur.execute(
    "SELECT id, room_number, building, status, owner_id, tenant_name, last_payment_date "
    "FROM rooms WHERE room_number = ?",
    ("201",),
)
rows = cur.fetchall()
result["room_201"] = rows

if rows:
    room_id = rows[0][0]
    cur.execute("SELECT COUNT(*) FROM payments WHERE room_id = ?", (room_id,))
    result["payments_count"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM utility_readings WHERE room_id = ?", (room_id,))
    result["utility_readings_count"] = cur.fetchone()[0]

cur.execute("SELECT id, username, role, is_active FROM users ORDER BY id")
result["users"] = cur.fetchall()

conn.close()
out.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
