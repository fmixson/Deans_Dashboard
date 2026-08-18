"""
division_summary.py
--------------------
Builds the "Division Comparison" table for the landing page: one row
per division, comparing current vs. prior week.
"""

import pandas as pd


def build_division_comparison(current, prior):
    """
    current: the LATEST week's classified sections (output of
             classify_sections()) — needs division, total_enrolled,
             enrollment_capacity, critically_low, low_not_growing,
             class_stat columns.
    prior:   the PRIOR week's raw sections — needs division and
             total_enrolled columns only.

    Returns one row per division with current vs. prior comparisons,
    plus a final "TOTAL / COLLEGE AVG" row summing everything.
    """
    current_agg = current.groupby("division").agg(
        current_sections=("division", "count"),
        current_enrolled=("total_enrolled", "sum"),
        current_capacity=("enrollment_capacity", "sum"),
        critically_low=("critically_low", "sum"),
        low_not_growing=("low_not_growing", "sum"),
        cancelled=("class_stat", lambda s: (s == "Cancelled Section").sum()),
    ).reset_index()

    prior_agg = prior.groupby("division").agg(
        prior_sections=("division", "count"),
        prior_enrolled=("total_enrolled", "sum"),
    ).reset_index()

    combined = current_agg.merge(prior_agg, on="division", how="left")
    combined[["prior_sections", "prior_enrolled"]] = combined[
        ["prior_sections", "prior_enrolled"]
    ].fillna(0)

    combined["section_change"] = combined["current_sections"] - combined["prior_sections"]

    combined["current_fill"] = None
    has_capacity = combined["current_capacity"] > 0
    combined.loc[has_capacity, "current_fill"] = (
        combined.loc[has_capacity, "current_enrolled"]
        / combined.loc[has_capacity, "current_capacity"]
    )

    total_capacity = combined["current_capacity"].sum()
    total_enrolled = combined["current_enrolled"].sum()
    total_fill = total_enrolled / total_capacity if total_capacity > 0 else None

    total_row = pd.DataFrame([{
        "division": "TOTAL / COLLEGE AVG",
        "current_sections": combined["current_sections"].sum(),
        "prior_sections": combined["prior_sections"].sum(),
        "section_change": combined["section_change"].sum(),
        "current_enrolled": total_enrolled,
        "prior_enrolled": combined["prior_enrolled"].sum(),
        "current_capacity": total_capacity,
        "current_fill": total_fill,
        "critically_low": combined["critically_low"].sum(),
        "low_not_growing": combined["low_not_growing"].sum(),
        "cancelled": combined["cancelled"].sum(),
    }])

    result = pd.concat([combined, total_row], ignore_index=True)
    return result