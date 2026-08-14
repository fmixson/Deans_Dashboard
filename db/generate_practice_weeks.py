"""
generate_practice_weeks.py
---------------------------
FAKE DATA FOR PRACTICE ONLY.

Simulates 3 prior weeks of snapshots by taking today's real snapshot
and working backwards with randomized enrollment numbers (since
enrollment typically climbs as a term approaches). This lets us
practice week-over-week trend queries before real weekly data exists.

To remove this fake data later, run:
    DELETE FROM weekly_snapshot WHERE snapshot_date < '2026-07-28';
(replace the date with today's real snapshot date)
"""

import sqlite3
import random
from datetime import date, timedelta

DB_PATH = "dashboard.db"
random.seed(42)  # reproducible fake data

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Find the real snapshot date already loaded (today's actual data)
cur.execute("SELECT MAX(snapshot_date) FROM weekly_snapshot")
real_date = cur.fetchone()[0]
real_date_obj = date.fromisoformat(real_date)
print(f"Using real snapshot from {real_date} as the anchor point")

# Pull today's real rows to base fake history on
cur.execute("""
    SELECT class_nbr, total_enrolled, seats_available, total_on_waitlist, class_stat
    FROM weekly_snapshot WHERE snapshot_date = ?
""", (real_date,))
today_rows = cur.fetchall()

# Generate 3 prior weeks, each with LOWER enrollment than the next
# (simulating registration filling up over time toward today).
for weeks_back in [3, 2, 1]:
    fake_date = (real_date_obj - timedelta(weeks=weeks_back)).isoformat()
    cur.execute("DELETE FROM weekly_snapshot WHERE snapshot_date = ?", (fake_date,))

    rows_inserted = 0
    for class_nbr, enrolled, seats_avail, waitlist, class_stat in today_rows:
        if enrolled is None:
            enrolled = 0
        # Earlier weeks had fewer students enrolled — shrink by 10-30% per week back
        shrink_factor = 1 - (0.15 * weeks_back) + random.uniform(-0.05, 0.05)
        fake_enrolled = max(0, int(enrolled * max(shrink_factor, 0)))
        fake_seats_avail = None if seats_avail is None else seats_avail + (enrolled - fake_enrolled)
        fake_waitlist = 0 if weeks_back >= 2 else (waitlist or 0)

        # Sections cancelled today were likely still "Active" or "Tentative" earlier
        if class_stat == "Cancelled Section" and weeks_back >= 2:
            fake_status = "Tentative Section"
        else:
            fake_status = class_stat

        cur.execute("""
            INSERT INTO weekly_snapshot
                (class_nbr, snapshot_date, total_enrolled, seats_available,
                 total_on_waitlist, class_stat)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (class_nbr, fake_date, fake_enrolled, fake_seats_avail, fake_waitlist, fake_status))
        rows_inserted += 1

    print(f"  {fake_date}: {rows_inserted} fake rows inserted ({weeks_back} weeks before real data)")

conn.commit()
conn.close()
print("\nDone. Remember: this is FAKE data for practice only.")
