"""
load_reporting_extract.py
---------------------------
Loads the OTHER weekly enrollment format (columns like STRM,
REPORTING_ENRL_CNT, Modality_Combined) into the same dashboard.db
used by load_weekly_report.py.

Usage:
    python3 load_reporting_extract.py path/to/report.xlsx

The snapshot date is read directly from the file's DAY_DATE column.
"""

import sys
import sqlite3
import pandas as pd

DB_PATH = "dashboard.db"

STATUS_MAP = {
    "A": "Active",
    "T": "Tentative Section",
    "X": "Cancelled Section",
    "S": "Stop Further Enrollment",
}


def load_report(xlsx_path: str):
    df = pd.read_excel(xlsx_path, header=0)

    before = len(df)
    df = df[df["REPORTING_IND"] == 1].copy()
    print(f"Read {before} rows, kept {len(df)} reportable rows "
          f"(excluded {before - len(df)} secondary combined-section rows)")

    before_dedup = len(df)
    df = df.drop_duplicates(subset=["CLASS_NBR"], keep="first")
    if len(df) < before_dedup:
        print(f"  Removed {before_dedup - len(df)} duplicate class numbers")

    snapshot_date = pd.to_datetime(df["DAY_DATE"].iloc[0]).date().isoformat()
    print(f"Snapshot date (from file): {snapshot_date}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    section_rows = 0
    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO class_sections (
                class_nbr, term, session, subject, catalog, descr,
                component, section_number, faculty_name, division,
                department, modality_location, start_date, end_date,
                enrollment_capacity, waitlist_capacity, instruction_mode
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(class_nbr) DO UPDATE SET
                session=excluded.session,
                faculty_name=excluded.faculty_name,
                enrollment_capacity=excluded.enrollment_capacity,
                waitlist_capacity=excluded.waitlist_capacity,
                instruction_mode=excluded.instruction_mode
        """, (
            int(row["CLASS_NBR"]), int(row["STRM"]), str(row.get("SESSION_CODE")),
            row.get("SUBJECT"), str(row.get("COURSE")),
            None, None, None,
            row.get("Instructor_Name"), row.get("DIV"), row.get("DEPT"),
            row.get("FACILITY_ID_NAME"),
            str(row.get("SESSION_BEGIN_DT")), None,
            _safe_int(row.get("CLASS_CAPACITY")),
            None,
            row.get("Modality_Combined"),
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
            int(row["CLASS_NBR"]), snapshot_date,
            _safe_int(row.get("ENRL_CNT")),
            None,
            _safe_int(row.get("WAIT_CNT")),
            STATUS_MAP.get(row["CLASS_STAT"], row["CLASS_STAT"]),
        ))
        snapshot_rows += 1

    conn.commit()
    conn.close()

    print(f"  {section_rows} sections upserted into class_sections")
    print(f"  {snapshot_rows} rows inserted into weekly_snapshot for {snapshot_date}")


def _safe_int(value):
    if pd.isna(value):
        return None
    return int(value)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 load_reporting_extract.py path/to/report.xlsx")
        sys.exit(1)
    load_report(sys.argv[1])