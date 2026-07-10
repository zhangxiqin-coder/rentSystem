#!/usr/bin/env python3
"""一键重置 xiqin2026 密码为 123456。
用法: python3 tools/reset_password.py
"""
import sqlite3
import os
from passlib.hash import bcrypt

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'rent_management.db')

def reset():
    new_hash = bcrypt.hash("123456")
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE users SET password_hash = ?, updated_at = datetime('now') WHERE username = 'xiqin2026'",
        (new_hash,)
    )
    conn.commit()
    # 验证
    row = conn.execute(
        "SELECT password_hash FROM users WHERE username = 'xiqin2026'"
    ).fetchone()
    ok = bcrypt.verify("123456", row[0])
    conn.close()
    print(f"✅ 密码已重置为 123456，验证: {'通过' if ok else '失败'}")

if __name__ == '__main__':
    reset()
