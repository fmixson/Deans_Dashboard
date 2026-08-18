"""
load_weekly_report.py
----------------------
Loads one week's "CER_SR_CLASS_DETAILS" Excel export into dashboard.db.

Usage:
    python3 load_weekly_report.py path/to/report.xlsx
"""

import sys
import sqlite3
import pandas as pd
from datetime import date

DB_PATH = "dashboard.db"


def load_report(xlsx_path: str):
    df = pd.read_excel(xlsx_path, header=2)

    # DEDUPLICATE — the source export sometimes repeats the exact
    # same class section 2-4 times. class_nbr should be unique, so
    # we keep only the first occurrence of each one.
    before = len(df)
    df = df.drop_duplicates(subset=["Class Nbr"], keep="first")
    duplicates_removed = before - len(df)
    if duplicates_removed > 0:
        print(f"  Removed {duplicates_removed} duplicate rows from source file")
    print(f"Read {len(df)} rows from {xlsx_path}")

    snapshot_date = date.today().isoformat()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

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