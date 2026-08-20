"""
division_summary.py
--------------------
Builds comparison tables (current vs. prior week) grouped by either
division, department, or modality.
"""

import pandas as pd


def build_group_comparison(current, prior, group_col, total_label="TOTAL"):
    current_agg = current.groupby(group_col).agg(
        current_sections=(group_col, "count"),
        current_enrolled=("total_enrolled", "sum"),
        current_capacity=("enrollment_capacity", "sum"),
        critically_low=("critically_low", "sum"),
        low_not_growing=("low_not_growing", "sum"),
        cancelled=("class_stat", lambda s: (s == "Cancelled Section").sum()),
    ).reset_index()

    prior_agg = prior.groupby(group_col).agg(
        prior_sections=(group_col, "count"),
        prior_enrolled=("total_enrolled", "sum"),
    ).reset_index()

    combined = current_agg.merge(prior_agg, on=group_col, how="left")
    combined[["prior_sections", "prior_enrolled"]] = combined[
        ["prior_sections", "prior_enrolled"]
    ].fillna(0)

    combined["section_change"] = combined["current_sections"] - combined["prior_sections"]
    combined["enrolled_change"] = combined["current_enrolled"] - combined["prior_enrolled"]

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
        group_col: total_label,
        "current_sections": combined["current_sections"].sum(),
        "prior_sections": combined["prior_sections"].sum(),
        "section_change": combined["section_change"].sum(),
        "current_enrolled": total_enrolled,
        "prior_enrolled": combined["prior_enrolled"].sum(),
        "enrolled_change": total_enrolled - combined["prior_enrolled"].sum(),
        "current_capacity": total_capacity,
        "current_fill": total_fill,
        "critically_low": combined["critically_low"].sum(),
        "low_not_growing": combined["low_not_growing"].sum(),
        "cancelled": combined["cancelled"].sum(),
    }])

    result = pd.concat([combined, total_row], ignore_index=True)
    return result


def build_division_comparison(current, prior):
    return build_group_comparison(current, prior, "division", total_label="TOTAL / COLLEGE AVG")


def build_department_comparison(current, prior):
    return build_group_comparison(current, prior, "department", total_label="TOTAL / DIVISION AVG")


def build_modality_comparison(current, prior):
    return build_group_comparison(current, prior, "instruction_mode", total_label="TOTAL")
