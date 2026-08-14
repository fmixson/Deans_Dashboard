"""
load_weekly_report.py
----------------------
Loads one week's "CER_SR_CLASS_DETAILS" Excel export into dashboard.db.

Usage:
    python3 load_weekly_report.py path/to/report.xlsx

Run this once per week, each time you get a fresh export. It's safe to
run multiple times on the SAME day (it'll just overwrite that day's
snapshot rather than duplicating it) — see the "delete existing" note
below.
"""

import sys
import sqlite3
import pandas as pd
from datetime import date

DB_PATH = "dashboard.db"


def load_report(xlsx_path: str):
    # -------------------------------------------------------------
    # 1. READ THE FILE
    # header=2 skips the two junk rows above the real header
    # ("Offered classes w/ details" and "Term = 1266") — we found
    # this by inspecting the file manually first. This is a common
    # real-world step: real exports rarely start with a clean header
    # on row 1.
    # -------------------------------------------------------------
    df = pd.read_excel(xlsx_path, header=2)
    print(f"Read {len(df)} rows from {xlsx_path}")

    # The snapshot date is simply "today" — the day you're loading this.
    snapshot_date = date.today().isoformat()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # -------------------------------------------------------------
    # 2. UPSERT into class_sections
    # "Upsert" = insert a new row, OR update it if it already exists.
    # SQLite's syntax for this is:
    #     INSERT INTO table (...) VALUES (...)
    #     ON CONFLICT(primary_key) DO UPDATE SET ...
    # We need this because the SAME class section (same class_nbr)
    # appears in every weekly file — we don't want 10 duplicate rows
    # for one section, just the latest stable info.
    # -------------------------------------------------------------
    section_rows = 0
    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO class_sections (
                class_nbr, term, session, subject, catalog, descr,
                component, section_number, faculty_name, division,
                department, modality_location, start_date, end_date,
                enrollment_capacity, waitlist_capacity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(class_nbr) DO UPDATE SET
                session=excluded.session,
                faculty_name=excluded.faculty_name,
                enrollment_capacity=excluded.enrollment_capacity,
                waitlist_capacity=excluded.waitlist_capacity
        """, (
            int(row["Class Nbr"]), int(row["Term"]), row["Session"],
            row["Subject"], str(row["Catalog"]), row["Descr"],
            row["Component"], str(row["Section Number"]), row["Faculty Name"],
            row["Division"], row["Department"], row["Modality/Location"],
            str(row["Start Date"]), str(row["End Date"]),
            _safe_int(row["Enrollment Capacity"]),
            _safe_int(row["Waitlist Capacity"]),
        ))
        section_rows += 1

    # -------------------------------------------------------------
    # 3. DELETE any existing snapshot for today, then INSERT fresh
    # This makes the script idempotent for a given day: run it twice
    # by accident on the same day, and you still only get one
    # snapshot per section for that day, not two.
    # -------------------------------------------------------------
    cur.execute("DELETE FROM weekly_snapshot WHERE snapshot_date = ?", (snapshot_date,))

    snapshot_rows = 0
    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO weekly_snapshot (
                class_nbr, snapshot_date, total_enrolled,
                seats_available, total_on_waitlist, class_stat
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            int(row["Class Nbr"]), snapshot_date,
            _safe_int(row["Total Enrolled"]),
            _safe_int(row["Seats Available"]),
            _safe_int(row["Total on Waitlist"]),
            row["Class Stat"],
        ))
        snapshot_rows += 1

    conn.commit()
    conn.close()

    print(f"  {section_rows} sections upserted into class_sections")
    print(f"  {snapshot_rows} rows inserted into weekly_snapshot for {snapshot_date}")


def _safe_int(value):
    """Excel gives us NaN for blank cells; sqlite wants None instead."""
    if pd.isna(value):
        return None
    return int(value)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 load_weekly_report.py path/to/report.xlsx")
        sys.exit(1)
    load_report(sys.argv[1])
