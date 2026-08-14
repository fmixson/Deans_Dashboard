"""
app.py
------
Dean's enrollment dashboard. Run with:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import sqlite3

DB_PATH = "db/dashboard.db"

# -----------------------------------------------------------------
# PAGE CONFIG
# Must be the first Streamlit command in the script.
# "wide" layout uses the full browser width instead of a narrow
# centered column — better for dashboards with charts/tables.
# -----------------------------------------------------------------
st.set_page_config(page_title="Enrollment Dashboard", layout="wide")


# -----------------------------------------------------------------
# CACHED DATA LOADING
# @st.cache_data means: run this function once, remember the result,
# and don't re-run it on every rerun UNLESS the underlying data
# changes (ttl=300 means "treat the cache as stale after 5 minutes,
# so a new weekly load will eventually show up without restarting").
# Without this, every dropdown click would re-query the whole DB.
# -----------------------------------------------------------------
@st.cache_data(ttl=300)
def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT cs.division, cs.department, cs.subject, cs.catalog, cs.descr,
               cs.faculty_name, cs.enrollment_capacity, cs.waitlist_capacity,
               ws.snapshot_date, ws.total_enrolled, ws.seats_available,
               ws.total_on_waitlist, ws.class_stat
        FROM weekly_snapshot ws
        JOIN class_sections cs ON cs.class_nbr = ws.class_nbr
    """, conn)
    conn.close()
    return df


df = load_data()
latest_date = df["snapshot_date"].max()
latest = df[df["snapshot_date"] == latest_date]

# -----------------------------------------------------------------
# TITLE + TOP-LINE METRICS
# st.columns() splits the layout horizontally. st.metric() gives
# that clean "big number + label" KPI look dashboards use.
# -----------------------------------------------------------------
st.title("Enrollment Dashboard")
st.caption(f"Latest data as of {latest_date}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Sections", len(latest))
col2.metric("Total Enrolled", int(latest["total_enrolled"].sum()))
col3.metric("Cancelled Sections", (latest["class_stat"] == "Cancelled Section").sum())
col4.metric("Sections at/near capacity",
            (latest["total_enrolled"] >= latest["enrollment_capacity"]).sum())

st.divider()

# -----------------------------------------------------------------
# SIDEBAR FILTER
# st.sidebar puts widgets in the left panel instead of the main
# page. This is a variable — selecting a value here reruns the
# whole script with `selected_division` set to the new choice.
# -----------------------------------------------------------------
st.sidebar.header("Filters")
divisions = ["All"] + sorted(df["division"].dropna().unique().tolist())
selected_division = st.sidebar.selectbox("Division", divisions)

if selected_division != "All":
    filtered = df[df["division"] == selected_division]
else:
    filtered = df

# -----------------------------------------------------------------
# TREND CHART
# Pandas does the GROUP BY here instead of SQL — same concept you
# just practiced, just written in pandas syntax instead:
#   .groupby([...]) is GROUP BY
#   .sum() is the aggregate function
# -----------------------------------------------------------------
st.subheader("Enrollment Trend by Division")
trend = (
    filtered.groupby(["snapshot_date", "division"])["total_enrolled"]
    .sum()
    .reset_index()
    .pivot(index="snapshot_date", columns="division", values="total_enrolled")
)
st.line_chart(trend)

# -----------------------------------------------------------------
# DETAIL TABLE (latest week only, respecting the filter)
# -----------------------------------------------------------------
st.subheader("At-Risk Sections")
st.caption("Cancelled, tentative, or active with zero enrollment, starting within 4 weeks — candidates for review")

# -----------------------------------------------------------------
# CONDITIONAL FLAGGING
# This is the pandas equivalent of the WHERE clause from your SQL
# exercise: "class_stat = 'Active' AND total_enrolled = 0".
# The | symbol means OR (like SQL's OR), combining three separate
# risk conditions into one filter.
# -----------------------------------------------------------------
at_risk_mask = (
    (latest_filtered["class_stat"] == "Cancelled Section") |
    (latest_filtered["class_stat"] == "Tentative Section") |
    ((latest_filtered["class_stat"] == "Active") & (latest_filtered["total_enrolled"] == 0))
)
at_risk = latest_filtered[at_risk_mask].copy()

# -----------------------------------------------------------------
# EXCLUDE SECTIONS STARTING FAR IN THE FUTURE
# pd.to_datetime() converts the text column into real datetime
# objects so we can do date math on it. pd.Timestamp.now() gets
# today's date/time to compare against.
# We compute how many days away each section's start is, then
# convert to weeks (days / 7). Sections 4+ weeks out are excluded —
# low enrollment that far ahead is normal, not a red flag.
# -----------------------------------------------------------------
at_risk["start_date_parsed"] = pd.to_datetime(at_risk["start_date"], errors="coerce")
weeks_until_start = (at_risk["start_date_parsed"] - pd.Timestamp.now()).dt.days / 7
at_risk = at_risk[weeks_until_start < 4]

# Label WHY each row is flagged — makes the table self-explanatory
def risk_reason(row):
    if row["class_stat"] == "Cancelled Section":
        return "Cancelled"
    if row["class_stat"] == "Tentative Section":
        return "Tentative — not yet confirmed"
    return "Active with zero enrollment"

at_risk["risk_reason"] = at_risk.apply(risk_reason, axis=1)

st.dataframe(
    at_risk[[
        "subject", "catalog", "descr", "faculty_name",
        "total_enrolled", "enrollment_capacity", "risk_reason"
    ]],
    use_container_width=True,
    hide_index=True,
)

st.divider()

st.subheader(f"Section Details — {latest_date}")
latest_filtered = latest if selected_division == "All" else latest[latest["division"] == selected_division]
st.dataframe(
    latest_filtered[[
        "subject", "catalog", "descr", "faculty_name",
        "total_enrolled", "enrollment_capacity", "total_on_waitlist", "class_stat"
    ]],
    use_container_width=True,
    hide_index=True,
)
