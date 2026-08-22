"""
add_class_type_column.py
--------------------------
One-time migration: adds a 'class_type' column to class_sections.
Safe to run even if the column already exists.
"""

import sqlite3

conn = sqlite3.connect("dashboard.db")
cur = conn.cursor()

cur.execute("PRAGMA table_info(class_sections)")
existing_columns = [row[1] for row in cur.fetchall()]

if "class_type" in existing_columns:
    print("Column already exists — nothing to do.")
else:
    cur.execute("ALTER TABLE class_sections ADD COLUMN class_type TEXT")
    conn.commit()
    print("Added class_type column to class_sections.")

conn.close()
