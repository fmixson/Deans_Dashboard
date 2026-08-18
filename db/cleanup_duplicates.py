"""
cleanup_duplicates.py
----------------------
One-time fix: removes duplicate rows that got loaded before we added
deduplication to load_weekly_report.py. Safe to run even if there's
nothing to clean — it'll just report 0 removed.

Run once, then you can delete this file if you like.
"""

import sqlite3

conn = sqlite3.connect("dashboard.db")
cur = conn.cursor()

cur.execute("""
    DELETE FROM weekly_snapshot
    WHERE id NOT IN (
        SELECT MIN(id) FROM weekly_snapshot GROUP BY class_nbr, snapshot_date
    )
""")
print(f"Removed {cur.rowcount} duplicate rows")
conn.commit()
conn.close()