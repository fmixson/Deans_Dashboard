"""
app.py
------
Dean's enrollment dashboard. Run with:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import sqlite3
from classification import classify_sections
from division_summary import build_division_comparison

DB_PATH = "db/dashboard.db"

st.set_page_config(page_title="Enrollment Dashboard", layout="wide")


@st.cache_data(ttl=300)
def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT cs.division, cs.department, cs.subject, cs.catalog, cs.descr,
               cs.faculty_name, cs.enrollment_capacity, cs.waitlist_capacity,
               cs.start_date, ws.class_nbr,
               ws.snapshot_date, ws.total_enrolled, ws.seats_available,
               ws.total_on_waitlist, ws.class_stat
        FROM weekly_snapshot ws
        JOIN class_sections cs ON cs.class_nbr = ws.class_nbr
    """, conn)
    conn.close()
    return df


df = load_data()

all_dates = sorted(df["snapshot_date"].unique())
latest_date = all_dates[-1]
prior_date = all_dates[-2] if len(all_dates) >= 2 else None

current_week = df[df["snapshot_date"] == latest_date].copy()
if prior_date:
    prior_week_full = df[df["snapshot_date"] == prior_date].copy()
    prior_week = prior_week_full[["class_nbr", "total_enrolled"]]
else:
    prior_week_full = pd.DataFrame(columns=df.columns)
    prior_week = pd.DataFrame(columns=["class_nbr", "total_enrolled"])

latest = classify_sections(current_week, prior_week)

st.title("Enrollment Dashboard")
st.caption(f"Latest data as of {latest_date}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Sections", len(latest))
col2.metric("Total Enrolled", int(latest["total_enrolled"].sum()))
col3.metric("Critically Low", int(latest["critically_low"].sum()))
col4.metric("Low & Not Growing", int(latest["low_not_growing"].sum()))

st.divider()

st.sidebar.header("Filters")
divisions = ["All"] + sorted(df["division"].dropna().unique().tolist())
selected_division = st.sidebar.selectbox("Division", divisions)

if selected_division != "All":
    filtered = df[df["division"] == selected_division]
else:
    filtered = df

latest_filtered = latest if selected_division == "All" else latest[latest["division"] == selected_division]

if selected_division == "All":
    st.subheader("Division Comparison")
    st.caption(f"Current week ({latest_date}) vs. prior week ({prior_date})")

    comparison = build_division_comparison(latest, prior_week_full)
    st.dataframe(
        comparison[[
            "division", "current_sections", "prior_sections", "section_change",
            "current_enrolled", "prior_enrolled", "current_fill",
            "critically_low", "low_not_growing", "cancelled",
        ]],
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Select a division from the sidebar to see its detailed breakdown.")

else:
    st.subheader(f"Enrollment Trend — {selected_division}")
    trend = (
        filtered.groupby(["snapshot_date", "division"])["total_enrolled"]
        .sum()
        .reset_index()
        .pivot(index="snapshot_date", columns="division", values="total_enrolled")
    )
    st.line_chart(trend)

    st.subheader("At-Risk Sections")
    st.caption("Critically low, low & not growing, or cancelled — starting within 4 weeks")

    at_risk_mask = (
        latest_filtered["critically_low"] |
        latest_filtered["low_not_growing"] |
        (latest_filtered["class_stat"] == "Cancelled Section")
    )
    at_risk = latest_filtered[at_risk_mask].copy()

    at_risk["start_date_parsed"] = pd.to_datetime(at_risk["start_date"], errors="coerce")
    weeks_until_start = (at_risk["start_date_parsed"] - pd.Timestamp.now()).dt.days / 7
    at_risk = at_risk[weeks_until_start < 4]

    def risk_reason(row):
        if row["class_stat"] == "Cancelled Section":
            return "Cancelled"
        if row["critically_low"]:
            return "Critically low enrollment"
        if row["low_not_growing"]:
            return "Low fill, not growing"
        return "Other"

    at_risk["risk_reason"] = at_risk.apply(risk_reason, axis=1)

    st.dataframe(
        at_risk[[
            "subject", "catalog", "descr", "faculty_name",
            "total_enrolled", "enrollment_capacity", "fill_rate", "risk_reason"
        ]],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.subheader(f"Section Details — {latest_date}")
    st.dataframe(
        latest_filtered[[
            "subject", "catalog", "descr", "faculty_name",
            "total_enrolled", "enrollment_capacity", "total_on_waitlist", "class_stat"
        ]],
        use_container_width=True,
        hide_index=True,
    )