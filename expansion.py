"""
expansion.py
-------------
Finds courses that might need an ADDITIONAL section — the mirror
image of consolidation.py.

Rule: for each course + modality combination (e.g. "ACCT 100,
Online"), add up the waitlist across ALL its sections, then compare
that total to the size of just ONE section. If the waiting list
alone is big enough to fill half a section, that's a strong signal
there's real unmet demand for that specific modality.
"""

import pandas as pd


def find_expansion_candidates(df, waitlist_ratio_threshold=0.5):
    """
    waitlist_ratio_threshold: 0.5 means "the combined waitlist for
        this course+modality is at least half the size of one section."

    Returns every section belonging to a (course, modality) group
    that meets the threshold, with the group's combined waitlist
    and ratio attached to each row.
    """
    active = df[df["class_stat"] != "Cancelled Section"].copy()

    group_cols = ["subject", "catalog", "instruction_mode"]

    group_stats = active.groupby(group_cols).agg(
        group_total_waitlist=("total_on_waitlist", "sum"),
        group_avg_capacity=("enrollment_capacity", "mean"),
    ).reset_index()

    group_stats["waitlist_ratio"] = (
        group_stats["group_total_waitlist"] / group_stats["group_avg_capacity"]
    )
    group_stats["high_demand_group"] = group_stats["waitlist_ratio"] >= waitlist_ratio_threshold

    active = active.merge(
        group_stats[group_cols + ["group_total_waitlist", "waitlist_ratio", "high_demand_group"]],
        on=group_cols, how="left"
    )

    candidates = active[active["high_demand_group"]].copy()
    candidates = candidates.sort_values(
        ["subject", "catalog", "instruction_mode", "total_enrolled"],
        ascending=[True, True, True, False]
    )

    return candidates[[
        "subject", "catalog", "instruction_mode", "class_nbr", "faculty_name",
        "start_date", "total_enrolled", "enrollment_capacity", "fill_rate",
        "total_on_waitlist", "group_total_waitlist", "waitlist_ratio",
    ]]
