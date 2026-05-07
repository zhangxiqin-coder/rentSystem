import sqlite3

db = r'd:/codespace/rentSystem/backend/rent_management.db'
conn = sqlite3.connect(db)
cur = conn.cursor()

cur.execute("SELECT id, room_number, owner_id FROM rooms WHERE room_number='201'")
row = cur.fetchone()
if row:
    cur.execute("DELETE FROM rooms WHERE id=?", (row[0],))
    conn.commit()

cur.execute("SELECT COUNT(*) FROM rooms WHERE room_number='201'")
print(cur.fetchone()[0])
conn.close()
