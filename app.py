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
from division_summary import build_division_comparison, build_department_comparison, build_modality_comparison

DB_PATH = "db/dashboard.db"

st.set_page_config(page_title="Enrollment Dashboard", layout="wide")


@st.cache_data(ttl=300)
def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT cs.division, cs.department, cs.subject, cs.catalog, cs.descr,
               cs.faculty_name, cs.enrollment_capacity, cs.waitlist_capacity,
               cs.start_date, cs.instruction_mode, ws.class_nbr,
               ws.snapshot_date, ws.total_enrolled, ws.seats_available,
               ws.total_on_waitlist, ws.class_stat
        FROM weekly_snapshot ws
        JOIN class_sections cs ON cs.class_nbr = ws.class_nbr
    """, conn)
    conn.close()
    return df


df = load_data()

df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce").dt.strftime("%Y-%m-%d")

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

    st.divider()

    st.subheader("Modality Breakdown — College-Wide")
    modality_comparison = build_modality_comparison(latest, prior_week_full)
    modality_display = modality_comparison[[
        "instruction_mode", "current_sections", "prior_sections",
        "current_enrolled", "prior_enrolled", "enrolled_change",
        "current_fill", "critically_low", "low_not_growing",
    ]].rename(columns={
        "instruction_mode": "Modality",
        "current_sections": "Current Sections",
        "prior_sections": "Prior Sections",
        "current_enrolled": "Current Enrolled",
        "prior_enrolled": "Prior Enrolled",
        "enrolled_change": "Change",
        "current_fill": "Current Fill",
        "critically_low": "Critically Low",
        "low_not_growing": "Low & Not Growing",
    })
    st.dataframe(modality_display, use_container_width=True, hide_index=True)

else:
    dept_options = ["All"] + sorted(
        latest_filtered["department"].dropna().unique().tolist()
    )
    selected_department = st.sidebar.selectbox("Department", dept_options)

    if selected_department != "All":
        latest_filtered = latest_filtered[latest_filtered["department"] == selected_department]

    start_date_options = ["All"] + sorted(
        latest_filtered["start_date"].dropna().unique().tolist()
    )
    selected_start_date = st.sidebar.selectbox("Start Date", start_date_options)

    if selected_start_date != "All":
        latest_filtered = latest_filtered[latest_filtered["start_date"] == selected_start_date]

    st.subheader("Department Breakdown")
    dept_prior_all = prior_week_full[prior_week_full["division"] == selected_division]
    latest_division_all = latest[latest["division"] == selected_division]
    dept_comparison = build_department_comparison(latest_division_all, dept_prior_all)
    dept_display = dept_comparison[[
        "department", "current_sections", "prior_sections",
        "current_enrolled", "prior_enrolled", "enrolled_change",
        "current_fill", "critically_low", "low_not_growing",
    ]].rename(columns={
        "department": "Dept",
        "current_sections": "Current Sections",
        "prior_sections": "Prior Sections",
        "current_enrolled": "Current Enrolled",
        "prior_enrolled": "Prior Enrolled",
        "enrolled_change": "Change",
        "current_fill": "Current Fill",
        "critically_low": "Critically Low",
        "low_not_growing": "Low & Not Growing",
    })
    st.dataframe(dept_display, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Modality Breakdown")
    dept_prior_scoped = dept_prior_all
    if selected_department != "All":
        dept_prior_scoped = dept_prior_all[dept_prior_all["department"] == selected_department]
    modality_comparison = build_modality_comparison(latest_filtered, dept_prior_scoped)
    modality_display = modality_comparison[[
        "instruction_mode", "current_sections", "prior_sections",
        "current_enrolled", "prior_enrolled", "enrolled_change",
        "current_fill", "critically_low", "low_not_growing",
    ]].rename(columns={
        "instruction_mode": "Modality",
        "current_sections": "Current Sections",
        "prior_sections": "Prior Sections",
        "current_enrolled": "Current Enrolled",
        "prior_enrolled": "Prior Enrolled",
        "enrolled_change": "Change",
        "current_fill": "Current Fill",
        "critically_low": "Critically Low",
        "low_not_growing": "Low & Not Growing",
    })
    st.dataframe(modality_display, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Critically Low Sections")
    st.caption("9 or fewer students enrolled, or under 25% fill (excludes cancelled sections)")

    critically_low_sections = latest_filtered[
        latest_filtered["critically_low"] & (latest_filtered["class_stat"] != "Cancelled Section")
    ].copy()
    st.dataframe(
        critically_low_sections[[
            "subject", "catalog", "descr", "faculty_name", "start_date",
            "total_enrolled", "enrollment_capacity", "fill_rate", "class_stat"
        ]],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.subheader("Low & Not Growing Sections")
    st.caption("Under 50% fill, with no enrollment growth from last week (excludes cancelled sections)")

    low_not_growing_sections = latest_filtered[
        latest_filtered["low_not_growing"] & (latest_filtered["class_stat"] != "Cancelled Section")
    ].copy()
    st.dataframe(
        low_not_growing_sections[[
            "subject", "catalog", "descr", "faculty_name", "start_date",
            "total_enrolled", "enrollment_capacity", "fill_rate", "growth"
        ]],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.subheader(f"Section Details — {latest_date}")
    st.dataframe(
        latest_filtered[[
            "subject", "catalog", "descr", "faculty_name", "start_date",
            "total_enrolled", "enrollment_capacity", "total_on_waitlist", "class_stat"
        ]],
        use_container_width=True,
        hide_index=True,
    )
