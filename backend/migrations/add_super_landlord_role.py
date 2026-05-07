"""
Migration: Add super_landlord role for testuser3

Replaces the hardcoded "testuser3" username checks with a proper role.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'rent_management.db')


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Update testuser3's role from landlord to super_landlord
    cursor.execute(
        "UPDATE users SET role = 'super_landlord' WHERE username = 'testuser3'"
    )

    if cursor.rowcount > 0:
        conn.commit()
        print(f"Updated testuser3 role to super_landlord ({cursor.rowcount} row)")
    else:
        print("testuser3 user not found, skipping")

    conn.close()


if __name__ == '__main__':
    migrate()
