"""
add_instruction_mode_column.py
--------------------------------
One-time migration: adds an 'instruction_mode' column to
class_sections. Safe to run even if the column already exists —
it'll just tell you and do nothing.
"""

import sqlite3

conn = sqlite3.connect("dashboard.db")
cur = conn.cursor()

cur.execute("PRAGMA table_info(class_sections)")
existing_columns = [row[1] for row in cur.fetchall()]

if "instruction_mode" in existing_columns:
    print("Column already exists — nothing to do.")
else:
    cur.execute("ALTER TABLE class_sections ADD COLUMN instruction_mode TEXT")
    conn.commit()
    print("Added instruction_mode column to class_sections.")

conn.close()