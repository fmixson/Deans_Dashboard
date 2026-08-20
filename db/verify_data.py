"""
verify_data.py
---------------
One-time check: confirms all 7 weeks loaded cleanly, with no
duplicate class numbers within any single week.
"""

import sqlite3

conn = sqlite3.connect("dashboard.db")
cur = conn.cursor()

cur.execute("""
    SELECT snapshot_date, COUNT(*) as total, COUNT(DISTINCT class_nbr) as unique_count
    FROM weekly_snapshot GROUP BY snapshot_date ORDER BY snapshot_date
""")
print("Snapshot dates loaded:")
all_clean = True
for row in cur.fetchall():
    date, total, unique = row
    status = "OK" if total == unique else "DUPLICATES FOUND"
    if total != unique:
        all_clean = False
    print(f"  {date}: {total} rows ({status})")

print()
cur.execute("SELECT term, COUNT(*) FROM class_sections GROUP BY term")
print("class_sections by term (should show only ONE term):")
for row in cur.fetchall():
    print(" ", row)

print()
print("All snapshots clean:", all_clean)

conn.close()