"""
generate_weekly_report.py
---------------------------
Builds a one-page PDF summary of the latest week's enrollment data,
suitable for emailing to deans while the hosted dashboard is pending
IT approval.

Usage:
    python3 generate_weekly_report.py

Run this AFTER load_weekly_report.py for the current week.
Output: weekly_report_<date>.pdf
"""

import sqlite3
import pandas as pd
from datetime import date
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)

DB_PATH = "db/dashboard.db"


def build_report():
    conn = sqlite3.connect(DB_PATH)

    # -------------------------------------------------------------
    # SAME QUERIES AS app.py — this is the point: one source of
    # truth for "what counts as at-risk," reused in two places
    # instead of redefining the logic and risking them drifting
    # apart over time.
    # -------------------------------------------------------------
    df = pd.read_sql("""
        SELECT cs.division, cs.department, cs.subject, cs.catalog, cs.descr,
               cs.faculty_name, cs.enrollment_capacity, cs.start_date,
               ws.snapshot_date, ws.total_enrolled, ws.total_on_waitlist,
               ws.class_stat
        FROM weekly_snapshot ws
        JOIN class_sections cs ON cs.class_nbr = ws.class_nbr
    """, conn)
    conn.close()

    latest_date = df["snapshot_date"].max()
    latest = df[df["snapshot_date"] == latest_date].copy()

    at_risk_mask = (
        (latest["class_stat"] == "Cancelled Section") |
        (latest["class_stat"] == "Tentative Section") |
        ((latest["class_stat"] == "Active") & (latest["total_enrolled"] == 0))
    )
    at_risk = latest[at_risk_mask].copy()
    at_risk["start_parsed"] = pd.to_datetime(at_risk["start_date"], errors="coerce")
    weeks_out = (at_risk["start_parsed"] - pd.Timestamp.now()).dt.days / 7
    at_risk = at_risk[weeks_out < 4]

    # -------------------------------------------------------------
    # BUILD THE PDF
    # SimpleDocTemplate + a list of "flowables" (Paragraph, Table,
    # Spacer) is reportlab's standard pattern — you build a list of
    # elements top to bottom, then call .build() once at the end.
    # -------------------------------------------------------------
    out_path = f"weekly_report_{latest_date}.pdf"
    doc = SimpleDocTemplate(out_path, pagesize=letter,
                             topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Weekly Enrollment Report", styles["Title"]))
    story.append(Paragraph(f"Data as of {latest_date}", styles["Normal"]))
    story.append(Spacer(1, 16))

    # --- KPI summary table ---
    kpi_data = [
        ["Total Sections", "Total Enrolled", "Cancelled", "At-Risk (this week)"],
        [
            str(len(latest)),
            str(int(latest["total_enrolled"].sum())),
            str((latest["class_stat"] == "Cancelled Section").sum()),
            str(len(at_risk)),
        ],
    ]
    kpi_table = Table(kpi_data, hAlign="LEFT")
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 20))

    # --- Enrollment by division table ---
    story.append(Paragraph("Enrollment by Division", styles["Heading2"]))
    by_division = (
        latest.groupby("division")
        .agg(sections=("division", "count"),
             enrolled=("total_enrolled", "sum"),
             capacity=("enrollment_capacity", "sum"))
        .reset_index()
        .sort_values("division")
    )
    div_data = [["Division", "Sections", "Enrolled", "Capacity"]] + by_division.values.tolist()
    div_table = Table(div_data, hAlign="LEFT")
    div_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
    ]))
    story.append(div_table)
    story.append(Spacer(1, 20))

    # --- At-risk sections table (top 15, to keep it to one page) ---
    story.append(Paragraph(
        f"At-Risk Sections ({len(at_risk)} total, top 15 shown)", styles["Heading2"]
    ))
    at_risk_display = at_risk[["subject", "catalog", "faculty_name", "class_stat"]].head(15)
    ar_data = [["Subject", "Catalog", "Faculty", "Status"]] + at_risk_display.fillna("—").values.tolist()
    ar_table = Table(ar_data, hAlign="LEFT")
    ar_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#922b21")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fbeee9")]),
    ]))
    story.append(ar_table)

    doc.build(story)
    print(f"Report written to {out_path}")
    return out_path


if __name__ == "__main__":
    build_report()
