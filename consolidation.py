"""
consolidation.py
------------------
Groups sections of the SAME course, in the SAME modality, together
so they can be compared side by side. This is the foundation for
consolidation questions like "could these 3 struggling online
sections of BA 100 become 2 fuller ones?" — you can't answer that
looking at one section at a time.

Modality matters here: a student in an online section usually can't
be folded into an in-person one, so an online BA 100 and an
in-person BA 100 are really two separate consolidation pools, not
one combined course.
"""

import pandas as pd


def find_multi_section_courses(df):
    """
    Returns only (course, modality) groups that have MORE THAN ONE
    active section AND at least one of those sections is struggling
    — these are the real consolidation candidates. A course with
    only one online section and one in-person section, for example,
    would NOT qualify, even though it has 2 sections total, because
    neither modality has more than one section to consolidate with.
    """
    active = df[df["class_stat"] != "Cancelled Section"].copy()

    group_cols = ["subject", "catalog", "instruction_mode"]

    active["section_count"] = active.groupby(group_cols)["class_nbr"].transform("count")

    active["group_has_struggling_section"] = (
        active.groupby(group_cols)["critically_low"].transform("max") |
        active.groupby(group_cols)["low_not_growing"].transform("max")
    )

    candidates = active[
        (active["section_count"] > 1) & (active["group_has_struggling_section"])
    ].copy()

    candidates = candidates.sort_values(
        ["subject", "catalog", "instruction_mode", "total_enrolled"],
        ascending=[True, True, True, False]
    )

    return candidates[[
        "subject", "catalog", "instruction_mode", "class_nbr", "faculty_name",
        "start_date", "total_enrolled", "enrollment_capacity", "fill_rate",
        "class_stat", "critically_low", "low_not_growing",
    ]]
