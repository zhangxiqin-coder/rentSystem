import sqlite3, json
from pathlib import Path

db = r'd:/codespace/rentSystem/backend/rent_management.db'
out = Path(r'd:/codespace/rentSystem/room22_probe.json')
conn = sqlite3.connect(db)
cur = conn.cursor()

result = {}
cur.execute("SELECT id, room_number, building, owner_id, tenant_name, status, updated_at FROM rooms WHERE id=22")
room = cur.fetchone()
result['room'] = room

if room:
    rid = room[0]
    rno = room[1]
    cur.execute("SELECT COUNT(*), MIN(payment_date), MAX(payment_date) FROM payments WHERE room_id=?", (rid,))
    result['payments_by_room_id'] = cur.fetchone()
    cur.execute("SELECT id, amount, payment_date, owner_id, created_at FROM payments WHERE room_id=? ORDER BY id DESC LIMIT 10", (rid,))
    result['payments_samples'] = cur.fetchall()

    cur.execute("SELECT COUNT(*), MIN(reading_date), MAX(reading_date) FROM utility_readings WHERE room_id=?", (rid,))
    result['readings_by_room_id'] = cur.fetchone()
    cur.execute("SELECT id, utility_type, reading, reading_date, owner_id, created_at FROM utility_readings WHERE room_id=? ORDER BY id DESC LIMIT 20", (rid,))
    result['readings_samples'] = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM payments p JOIN rooms r ON p.room_id=r.id WHERE r.room_number=?", (rno,))
    result['payments_by_room_number_join'] = cur.fetchone()[0]

cur.execute("SELECT id, username, role FROM users ORDER BY id")
result['users'] = cur.fetchall()

out.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
conn.close()
