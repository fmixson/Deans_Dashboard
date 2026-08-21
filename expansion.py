"""
expansion.py
-------------
Finds courses that might need an ADDITIONAL section — the mirror
image of consolidation.py. A section is "high demand" when it's
nearly/fully full AND has a meaningful waitlist (students turned
away, not just idle capacity).
"""

import pandas as pd


def find_expansion_candidates(df, fill_threshold=0.90, min_waitlist=3):
    """
    fill_threshold: how full a section must be (0.90 = 90%+) to
        count as "high demand" on its own.
    min_waitlist: minimum students waiting to count as meaningful
        demand, not just a couple of stragglers.

    Returns every section belonging to a course where AT LEAST ONE
    section meets both the fill and waitlist thresholds.
    """
    active = df[df["class_stat"] != "Cancelled Section"].copy()

    active["high_demand"] = (
        (active["fill_rate"] >= fill_threshold) &
        (active["total_on_waitlist"] >= min_waitlist)
    )

    active["course_has_high_demand"] = active.groupby(
        ["subject", "catalog"]
    )["high_demand"].transform("max")

    candidates = active[active["course_has_high_demand"]].copy()
    candidates = candidates.sort_values(
        ["subject", "catalog", "total_enrolled"], ascending=[True, True, False]
    )

    return candidates[[
        "subject", "catalog", "class_nbr", "faculty_name", "instruction_mode",
        "start_date", "total_enrolled", "enrollment_capacity", "fill_rate",
        "total_on_waitlist", "high_demand",
    ]]
