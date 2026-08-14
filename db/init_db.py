"""
init_db.py
----------
Builds the SQLite database for the class-section enrollment dashboard.

Run this ONCE to create the empty schema. After that, use
load_weekly_report.py to load each week's Excel export — don't re-run
this script once you have real data in it, since it drops everything.
"""

import sqlite3

DB_PATH = "dashboard.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.executescript("""
DROP TABLE IF EXISTS weekly_snapshot;
DROP TABLE IF EXISTS class_sections;

-- Stable info about a class section (rarely changes within a term)
CREATE TABLE class_sections (
    class_nbr           INTEGER PRIMARY KEY,   -- unique per term, from source file
    term                INTEGER NOT NULL,
    session              TEXT,
    subject              TEXT,
    catalog              TEXT,
    descr                TEXT,
    component            TEXT,
    section_number       TEXT,
    faculty_name         TEXT,
    division             TEXT,
    department           TEXT,
    modality_location     TEXT,
    start_date           TEXT,
    end_date             TEXT,
    enrollment_capacity   INTEGER,
    waitlist_capacity     INTEGER
);

-- One row per section, per week the report is uploaded
CREATE TABLE weekly_snapshot (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    class_nbr          INTEGER NOT NULL,
    snapshot_date       TEXT NOT NULL,   -- date this report was loaded
    total_enrolled      INTEGER,
    seats_available     INTEGER,
    total_on_waitlist    INTEGER,
    class_stat          TEXT,
    FOREIGN KEY (class_nbr) REFERENCES class_sections(class_nbr)
);
""")

conn.commit()
conn.close()
print(f"Empty schema created at {DB_PATH}")
