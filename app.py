"""
app.py
------
Dean's enrollment dashboard. Run with:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import sqlite3
from classification import classif"""
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
from ai_assistant import build_context, ask_claude
from consolidation import find_multi_section_courses
from expansion import find_expansion_candidates
from enrollment_trail import build_trail
from key_takeaways import generate_takeaways

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

trail_data = build_trail(df, n_weeks=4)
latest = latest.merge(trail_data, on="class_nbr", how="left")

today = pd.Timestamp.now().normalize()
latest["days_until_start"] = (pd.to_datetime(latest["start_date"], errors="coerce") - today).dt.days
latest["eligible_for_risk_lists"] = latest["days_until_start"] <= 30
latest["critically_low"] = (
    latest["critically_low"] & latest["eligible_for_risk_lists"] & (latest["class_stat"] != "Cancelled Section")
)
latest["low_not_growing"] = (
    latest["low_not_growing"] & latest["eligible_for_risk_lists"] & (latest["class_stat"] != "Cancelled Section")
)

st.title("Enrollment Dashboard")
st.caption(f"Latest data as of {latest_date}")

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
    start_date_options = sorted(latest["start_date"].dropna().unique().tolist())
    selected_start_dates = st.sidebar.multiselect(
        "Start Date", start_date_options, default=start_date_options
    )
    latest = latest[latest["start_date"].isin(selected_start_dates)]
    prior_week_full = prior_week_full[prior_week_full["start_date"].isin(selected_start_dates)]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Sections", len(latest))
    col2.metric("Total Enrolled", int(latest["total_enrolled"].sum()))
    col3.metric("Critically Low", int((latest["critically_low"] & latest["eligible_for_risk_lists"]).sum()))
    col4.metric("Low & Not Growing", int((latest["low_not_growing"] & latest["eligible_for_risk_lists"]).sum()))

    st.divider()

    comparison = build_division_comparison(latest, prior_week_full)
    modality_comparison = build_modality_comparison(latest, prior_week_full)
    modality_display = modality_comparison[[
        "instruction_mode", "current_sections",
        "current_enrolled", "enrolled_change",
        "current_fill", "critically_low", "low_not_growing",
    ]].rename(columns={
        "instruction_mode": "Modality",
        "current_sections": "Current Sections",
        "current_enrolled": "Current Enrolled",
        "enrolled_change": "Change",
        "current_fill": "Current Fill",
        "critically_low": "Critically Low",
        "low_not_growing": "Low & Not Growing",
    })

    college_critically_low = latest[
        latest["critically_low"] & (latest["class_stat"] != "Cancelled Section") & latest["eligible_for_risk_lists"]
    ][["division", "department", "subject", "catalog", "start_date", "total_enrolled", "enrollment_capacity", "total_on_waitlist", "trail"]]
    college_low_not_growing = latest[
        latest["low_not_growing"] & (latest["class_stat"] != "Cancelled Section") & latest["eligible_for_risk_lists"]
    ][["division", "department", "subject", "catalog", "start_date", "total_enrolled", "growth", "total_on_waitlist", "trail"]]

    college_context = build_context(
        scope_label="All Divisions (College-Wide)",
        breakdown_display=comparison[[
            "division", "current_sections", "prior_sections", "section_change",
            "current_enrolled", "prior_enrolled", "current_fill",
            "critically_low", "low_not_growing", "cancelled",
        ]],
        breakdown_label="DIVISION BREAKDOWN",
        modality_display=modality_display,
        critically_low_df=college_critically_low,
        low_not_growing_df=college_low_not_growing,
        section_count=len(latest),
    )

    st.subheader("Key Takeaways")
    if st.button("Generate Key Takeaways", key="takeaways_button_college"):
        with st.spinner("Analyzing..."):
            try:
                api_key = st.secrets["ANTHROPIC_API_KEY"]
                st.session_state["takeaways_college"] = generate_takeaways(api_key, college_context)
            except Exception as e:
                st.error(f"Couldn't generate takeaways: {e}")

    if "takeaways_college" in st.session_state:
        st.markdown(st.session_state["takeaways_college"])

    st.divider()

    st.subheader("Division Comparison")
    st.caption(f"Current week ({latest_date}) vs. prior week ({prior_date})")

    st.dataframe(
        comparison[[
            "division", "current_sections", "section_change",
            "current_enrolled", "current_fill",
            "critically_low", "low_not_growing", "cancelled",
        ]],
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Select a division from the sidebar to see its detailed breakdown.")

    st.divider()

    st.subheader("Modality Breakdown — College-Wide")
    st.dataframe(modality_display, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Ask About This Data")
    st.caption("Ask questions about enrollment across all divisions")

    if "chat_history_college" not in st.session_state:
        st.session_state.chat_history_college = []

    for message in st.session_state.chat_history_college:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    college_question = st.chat_input("e.g. Which division has the most critically low sections?")

    if college_question:
        with st.chat_message("user"):
            st.write(college_question)
        st.session_state.chat_history_college.append({"role": "user", "content": college_question})

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    api_key = st.secrets["ANTHROPIC_API_KEY"]
                    answer = ask_claude(api_key, college_context, college_question, st.session_state.chat_history_college[:-1])
                    st.write(answer)
                    st.session_state.chat_history_college.append({"role": "assistant", "content": answer})
                except Exception as e:
                    st.error(f"Couldn't get a response: {e}")

else:
    dept_options = ["All"] + sorted(
        latest_filtered["department"].dropna().unique().tolist()
    )
    selected_department = st.sidebar.selectbox("Department", dept_options)

    if selected_department != "All":
        latest_filtered = latest_filtered[latest_filtered["department"] == selected_department]

    start_date_options = sorted(latest_filtered["start_date"].dropna().unique().tolist())
    selected_start_dates = st.sidebar.multiselect(
        "Start Date", start_date_options, default=start_date_options
    )

    latest_filtered = latest_filtered[latest_filtered["start_date"].isin(selected_start_dates)]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Sections", len(latest_filtered))
    col2.metric("Total Enrolled", int(latest_filtered["total_enrolled"].sum()))
    col3.metric("Critically Low", int((latest_filtered["critically_low"] & latest_filtered["eligible_for_risk_lists"]).sum()))
    col4.metric("Low & Not Growing", int((latest_filtered["low_not_growing"] & latest_filtered["eligible_for_risk_lists"]).sum()))

    st.divider()

    dept_prior_all = prior_week_full[prior_week_full["division"] == selected_division]
    latest_division_all = latest[latest["division"] == selected_division]
    dept_comparison = build_department_comparison(latest_division_all, dept_prior_all)
    dept_display = dept_comparison[[
        "department", "current_sections",
        "current_enrolled", "enrolled_change",
        "current_fill", "critically_low", "low_not_growing",
    ]].rename(columns={
        "department": "Dept",
        "current_sections": "Current Sections",
        "current_enrolled": "Current Enrolled",
        "enrolled_change": "Change",
        "current_fill": "Current Fill",
        "critically_low": "Critically Low",
        "low_not_growing": "Low & Not Growing",
    })

    dept_prior_scoped = dept_prior_all
    if selected_department != "All":
        dept_prior_scoped = dept_prior_all[dept_prior_all["department"] == selected_department]
    modality_comparison = build_modality_comparison(latest_filtered, dept_prior_scoped)
    modality_display = modality_comparison[[
        "instruction_mode", "current_sections",
        "current_enrolled", "enrolled_change",
        "current_fill", "critically_low", "low_not_growing",
    ]].rename(columns={
        "instruction_mode": "Modality",
        "current_sections": "Current Sections",
        "current_enrolled": "Current Enrolled",
        "enrolled_change": "Change",
        "current_fill": "Current Fill",
        "critically_low": "Critically Low",
        "low_not_growing": "Low & Not Growing",
    })

    critically_low_sections = latest_filtered[
        latest_filtered["critically_low"] & (latest_filtered["class_stat"] != "Cancelled Section") & latest_filtered["eligible_for_risk_lists"]
    ].copy()

    low_not_growing_sections = latest_filtered[
        latest_filtered["low_not_growing"] & (latest_filtered["class_stat"] != "Cancelled Section") & latest_filtered["eligible_for_risk_lists"]
    ].copy()

    consolidation_candidates = find_multi_section_courses(latest_filtered[latest_filtered["eligible_for_risk_lists"]])
    expansion_candidates = find_expansion_candidates(latest_filtered)

    drill_scope_label = f"{selected_division}" + (f" — {selected_department}" if selected_department != "All" else "")
    drill_context = build_context(
        scope_label=drill_scope_label,
        breakdown_display=dept_display,
        breakdown_label="DEPARTMENT BREAKDOWN",
        modality_display=modality_display,
        critically_low_df=critically_low_sections[["subject", "catalog", "start_date", "total_enrolled", "enrollment_capacity", "total_on_waitlist", "trail"]],
        low_not_growing_df=low_not_growing_sections[["subject", "catalog", "start_date", "total_enrolled", "growth", "total_on_waitlist", "trail"]],
        section_count=len(latest_filtered),
        consolidation_df=consolidation_candidates,
        expansion_df=expansion_candidates,
        full_roster_df=latest_filtered[[
            "department", "subject", "catalog", "faculty_name",
            "start_date", "total_enrolled", "enrollment_capacity", "class_stat"
        ]],
    )

    st.subheader("Key Takeaways")
    takeaways_key = f"takeaways_{drill_scope_label}"
    if st.button("Generate Key Takeaways", key="takeaways_button_drilldown"):
        with st.spinner("Analyzing..."):
            try:
                api_key = st.secrets["ANTHROPIC_API_KEY"]
                st.session_state[takeaways_key] = generate_takeaways(api_key, drill_context)
            except Exception as e:
                st.error(f"Couldn't generate takeaways: {e}")

    if takeaways_key in st.session_state:
        st.markdown(st.session_state[takeaways_key])

    st.divider()

    st.subheader("Department Breakdown")
    st.dataframe(dept_display, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Modality Breakdown")
    st.dataframe(modality_display, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Critically Low Sections")
    st.caption("9 or fewer students enrolled, or under 25% fill — sections starting within 30 days (excludes cancelled sections)")
    st.dataframe(
        critically_low_sections[[
            "subject", "catalog", "descr", "faculty_name", "start_date",
            "total_enrolled", "enrollment_capacity", "fill_rate",
            "total_on_waitlist", "trail", "class_stat"
        ]],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.subheader("Low & Not Growing Sections")
    st.caption("Under 50% fill, with no enrollment growth from last week — sections starting within 30 days (excludes cancelled sections)")
    st.dataframe(
        low_not_growing_sections[[
            "subject", "catalog", "descr", "faculty_name", "start_date",
            "total_enrolled", "enrollment_capacity", "fill_rate",
            "total_on_waitlist", "trail", "growth"
        ]],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.subheader("Consolidation Candidates")
    st.caption("Courses with multiple sections in the SAME modality where at least one is struggling — sections starting within 30 days — compare side by side")
    st.dataframe(
        consolidation_candidates,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.subheader("Expansion Candidates")
    st.caption("Courses where the combined waitlist across all sections of a modality is 50%+ the size of one section — possible candidates for an additional section")
    st.dataframe(
        expansion_candidates,
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

    st.divider()

    st.subheader("Ask About This Data")
    st.caption(f"Ask questions about {drill_scope_label}")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    user_question = st.chat_input("e.g. Which departments have the most critically low sections?")

    if user_question:
        with st.chat_message("user"):
            st.write(user_question)
        st.session_state.chat_history.append({"role": "user", "content": user_question})

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    api_key = st.secrets["ANTHROPIC_API_KEY"]
                    answer = ask_claude(api_key, drill_context, user_question, st.session_state.chat_history[:-1])
                    st.write(answer)
                    st.session_state.chat_history.append({"role": "assistant", "content": answer})
                except Exception as e:
                    st.error(f"Couldn't get a response: {e}")y_sections
from division_summary import build_division_comparison, build_department_comparison, build_modality_comparison
from ai_assistant import build_context, ask_claude
from consolidation import find_multi_section_courses
from expansion import find_expansion_candidates
from enrollment_trail import build_trail
from key_takeaways import generate_takeaways

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

trail_data = build_trail(df, n_weeks=4)
latest = latest.merge(trail_data, on="class_nbr", how="left")

today = pd.Timestamp.now().normalize()
latest["days_until_start"] = (pd.to_datetime(latest["start_date"], errors="coerce") - today).dt.days
latest["eligible_for_risk_lists"] = latest["days_until_start"] <= 30

st.title("Enrollment Dashboard")
st.caption(f"Latest data as of {latest_date}")

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
    start_date_options = sorted(latest["start_date"].dropna().unique().tolist())
    selected_start_dates = st.sidebar.multiselect(
        "Start Date", start_date_options, default=start_date_options
    )
    latest = latest[latest["start_date"].isin(selected_start_dates)]
    prior_week_full = prior_week_full[prior_week_full["start_date"].isin(selected_start_dates)]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Sections", len(latest))
    col2.metric("Total Enrolled", int(latest["total_enrolled"].sum()))
    col3.metric("Critically Low", int((latest["critically_low"] & latest["eligible_for_risk_lists"]).sum()))
    col4.metric("Low & Not Growing", int((latest["low_not_growing"] & latest["eligible_for_risk_lists"]).sum()))

    st.divider()

    comparison = build_division_comparison(latest, prior_week_full)
    modality_comparison = build_modality_comparison(latest, prior_week_full)
    modality_display = modality_comparison[[
        "instruction_mode", "current_sections",
        "current_enrolled", "enrolled_change",
        "current_fill", "critically_low", "low_not_growing",
    ]].rename(columns={
        "instruction_mode": "Modality",
        "current_sections": "Current Sections",
        "current_enrolled": "Current Enrolled",
        "enrolled_change": "Change",
        "current_fill": "Current Fill",
        "critically_low": "Critically Low",
        "low_not_growing": "Low & Not Growing",
    })

    college_critically_low = latest[
        latest["critically_low"] & (latest["class_stat"] != "Cancelled Section") & latest["eligible_for_risk_lists"]
    ][["division", "department", "subject", "catalog", "start_date", "total_enrolled", "enrollment_capacity", "total_on_waitlist", "trail"]]
    college_low_not_growing = latest[
        latest["low_not_growing"] & (latest["class_stat"] != "Cancelled Section") & latest["eligible_for_risk_lists"]
    ][["division", "department", "subject", "catalog", "start_date", "total_enrolled", "growth", "total_on_waitlist", "trail"]]

    college_context = build_context(
        scope_label="All Divisions (College-Wide)",
        breakdown_display=comparison[[
            "division", "current_sections", "prior_sections", "section_change",
            "current_enrolled", "prior_enrolled", "current_fill",
            "critically_low", "low_not_growing", "cancelled",
        ]],
        breakdown_label="DIVISION BREAKDOWN",
        modality_display=modality_display,
        critically_low_df=college_critically_low,
        low_not_growing_df=college_low_not_growing,
        section_count=len(latest),
    )

    st.subheader("Key Takeaways")
    if st.button("Generate Key Takeaways", key="takeaways_button_college"):
        with st.spinner("Analyzing..."):
            try:
                api_key = st.secrets["ANTHROPIC_API_KEY"]
                st.session_state["takeaways_college"] = generate_takeaways(api_key, college_context)
            except Exception as e:
                st.error(f"Couldn't generate takeaways: {e}")

    if "takeaways_college" in st.session_state:
        st.markdown(st.session_state["takeaways_college"])

    st.divider()

    st.subheader("Division Comparison")
    st.caption(f"Current week ({latest_date}) vs. prior week ({prior_date})")

    st.dataframe(
        comparison[[
            "division", "current_sections", "section_change",
            "current_enrolled", "current_fill",
            "critically_low", "low_not_growing", "cancelled",
        ]],
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Select a division from the sidebar to see its detailed breakdown.")

    st.divider()

    st.subheader("Modality Breakdown — College-Wide")
    st.dataframe(modality_display, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Ask About This Data")
    st.caption("Ask questions about enrollment across all divisions")

    if "chat_history_college" not in st.session_state:
        st.session_state.chat_history_college = []

    for message in st.session_state.chat_history_college:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    college_question = st.chat_input("e.g. Which division has the most critically low sections?")

    if college_question:
        with st.chat_message("user"):
            st.write(college_question)
        st.session_state.chat_history_college.append({"role": "user", "content": college_question})

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    api_key = st.secrets["ANTHROPIC_API_KEY"]
                    answer = ask_claude(api_key, college_context, college_question, st.session_state.chat_history_college[:-1])
                    st.write(answer)
                    st.session_state.chat_history_college.append({"role": "assistant", "content": answer})
                except Exception as e:
                    st.error(f"Couldn't get a response: {e}")

else:
    dept_options = ["All"] + sorted(
        latest_filtered["department"].dropna().unique().tolist()
    )
    selected_department = st.sidebar.selectbox("Department", dept_options)

    if selected_department != "All":
        latest_filtered = latest_filtered[latest_filtered["department"] == selected_department]

    start_date_options = sorted(latest_filtered["start_date"].dropna().unique().tolist())
    selected_start_dates = st.sidebar.multiselect(
        "Start Date", start_date_options, default=start_date_options
    )

    latest_filtered = latest_filtered[latest_filtered["start_date"].isin(selected_start_dates)]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Sections", len(latest_filtered))
    col2.metric("Total Enrolled", int(latest_filtered["total_enrolled"].sum()))
    col3.metric("Critically Low", int((latest_filtered["critically_low"] & latest_filtered["eligible_for_risk_lists"]).sum()))
    col4.metric("Low & Not Growing", int((latest_filtered["low_not_growing"] & latest_filtered["eligible_for_risk_lists"]).sum()))

    st.divider()

    dept_prior_all = prior_week_full[prior_week_full["division"] == selected_division]
    latest_division_all = latest[latest["division"] == selected_division]
    dept_comparison = build_department_comparison(latest_division_all, dept_prior_all)
    dept_display = dept_comparison[[
        "department", "current_sections",
        "current_enrolled", "enrolled_change",
        "current_fill", "critically_low", "low_not_growing",
    ]].rename(columns={
        "department": "Dept",
        "current_sections": "Current Sections",
        "current_enrolled": "Current Enrolled",
        "enrolled_change": "Change",
        "current_fill": "Current Fill",
        "critically_low": "Critically Low",
        "low_not_growing": "Low & Not Growing",
    })

    dept_prior_scoped = dept_prior_all
    if selected_department != "All":
        dept_prior_scoped = dept_prior_all[dept_prior_all["department"] == selected_department]
    modality_comparison = build_modality_comparison(latest_filtered, dept_prior_scoped)
    modality_display = modality_comparison[[
        "instruction_mode", "current_sections",
        "current_enrolled", "enrolled_change",
        "current_fill", "critically_low", "low_not_growing",
    ]].rename(columns={
        "instruction_mode": "Modality",
        "current_sections": "Current Sections",
        "current_enrolled": "Current Enrolled",
        "enrolled_change": "Change",
        "current_fill": "Current Fill",
        "critically_low": "Critically Low",
        "low_not_growing": "Low & Not Growing",
    })

    critically_low_sections = latest_filtered[
        latest_filtered["critically_low"] & (latest_filtered["class_stat"] != "Cancelled Section") & latest_filtered["eligible_for_risk_lists"]
    ].copy()

    low_not_growing_sections = latest_filtered[
        latest_filtered["low_not_growing"] & (latest_filtered["class_stat"] != "Cancelled Section") & latest_filtered["eligible_for_risk_lists"]
    ].copy()

    consolidation_candidates = find_multi_section_courses(latest_filtered[latest_filtered["eligible_for_risk_lists"]])
    expansion_candidates = find_expansion_candidates(latest_filtered)

    drill_scope_label = f"{selected_division}" + (f" — {selected_department}" if selected_department != "All" else "")
    drill_context = build_context(
        scope_label=drill_scope_label,
        breakdown_display=dept_display,
        breakdown_label="DEPARTMENT BREAKDOWN",
        modality_display=modality_display,
        critically_low_df=critically_low_sections[["subject", "catalog", "start_date", "total_enrolled", "enrollment_capacity", "total_on_waitlist", "trail"]],
        low_not_growing_df=low_not_growing_sections[["subject", "catalog", "start_date", "total_enrolled", "growth", "total_on_waitlist", "trail"]],
        section_count=len(latest_filtered),
        consolidation_df=consolidation_candidates,
        expansion_df=expansion_candidates,
        full_roster_df=latest_filtered[[
            "department", "subject", "catalog", "faculty_name",
            "start_date", "total_enrolled", "enrollment_capacity", "class_stat"
        ]],
    )

    st.subheader("Key Takeaways")
    takeaways_key = f"takeaways_{drill_scope_label}"
    if st.button("Generate Key Takeaways", key="takeaways_button_drilldown"):
        with st.spinner("Analyzing..."):
            try:
                api_key = st.secrets["ANTHROPIC_API_KEY"]
                st.session_state[takeaways_key] = generate_takeaways(api_key, drill_context)
            except Exception as e:
                st.error(f"Couldn't generate takeaways: {e}")

    if takeaways_key in st.session_state:
        st.markdown(st.session_state[takeaways_key])

    st.divider()

    st.subheader("Department Breakdown")
    st.dataframe(dept_display, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Modality Breakdown")
    st.dataframe(modality_display, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Critically Low Sections")
    st.caption("9 or fewer students enrolled, or under 25% fill — sections starting within 30 days (excludes cancelled sections)")
    st.dataframe(
        critically_low_sections[[
            "subject", "catalog", "descr", "faculty_name", "start_date",
            "total_enrolled", "enrollment_capacity", "fill_rate",
            "total_on_waitlist", "trail", "class_stat"
        ]],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.subheader("Low & Not Growing Sections")
    st.caption("Under 50% fill, with no enrollment growth from last week — sections starting within 30 days (excludes cancelled sections)")
    st.dataframe(
        low_not_growing_sections[[
            "subject", "catalog", "descr", "faculty_name", "start_date",
            "total_enrolled", "enrollment_capacity", "fill_rate",
            "total_on_waitlist", "trail", "growth"
        ]],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.subheader("Consolidation Candidates")
    st.caption("Courses with multiple sections in the SAME modality where at least one is struggling — sections starting within 30 days — compare side by side")
    st.dataframe(
        consolidation_candidates,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.subheader("Expansion Candidates")
    st.caption("Courses where the combined waitlist across all sections of a modality is 50%+ the size of one section — possible candidates for an additional section")
    st.dataframe(
        expansion_candidates,
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

    st.divider()

    st.subheader("Ask About This Data")
    st.caption(f"Ask questions about {drill_scope_label}")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    user_question = st.chat_input("e.g. Which departments have the most critically low sections?")

    if user_question:
        with st.chat_message("user"):
            st.write(user_question)
        st.session_state.chat_history.append({"role": "user", "content": user_question})

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    api_key = st.secrets["ANTHROPIC_API_KEY"]
                    answer = ask_claude(api_key, drill_context, user_question, st.session_state.chat_history[:-1])
                    st.write(answer)
                    st.session_state.chat_history.append({"role": "assistant", "content": answer})
                except Exception as e:
                    st.error(f"Couldn't get a response: {e}")
