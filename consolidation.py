"""
consolidation.py
------------------
Groups sections of the SAME course (same subject + catalog number)
together, so they can be compared side by side. This is the
foundation for consolidation questions like "could these 3 struggling
sections of BA 100 become 2 fuller ones?" — you can't answer that
looking at one section at a time.
"""

import pandas as pd


def find_multi_section_courses(df):
    """
    df: the classified section dataframe (needs subject, catalog,
        class_nbr, faculty_name, instruction_mode, start_date,
        total_enrolled, enrollment_capacity, fill_rate, class_stat,
        critically_low, low_not_growing columns).

    Returns only courses that have MORE THAN ONE active section AND
    at least one of those sections is struggling (critically low or
    low & not growing) — these are the real consolidation candidates.
    """
    active = df[df["class_stat"] != "Cancelled Section"].copy()

    active["section_count"] = active.groupby(["subject", "catalog"])["class_nbr"].transform("count")

    active["course_has_struggling_section"] = (
        active.groupby(["subject", "catalog"])["critically_low"].transform("max") |
        active.groupby(["subject", "catalog"])["low_not_growing"].transform("max")
    )

    candidates = active[
        (active["section_count"] > 1) & (active["course_has_struggling_section"])
    ].copy()

    candidates = candidates.sort_values(["subject", "catalog", "total_enrolled"], ascending=[True, True, False])

    return candidates[[
        "subject", "catalog", "class_nbr", "faculty_name", "instruction_mode",
        "start_date", "total_enrolled", "enrollment_capacity", "fill_rate",
        "class_stat", "critically_low", "low_not_growing",
    ]]
