"""
division_summary.py
--------------------
Builds the "Division Comparison" table for the landing page: one row
per division, comparing current vs. prior week.

Kept separate from classification.py and app.py so we can test it
on its own with real numbers before wiring it into anything visual.
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
    # -------------------------------------------------------------
    # CURRENT WEEK, GROUPED BY DIVISION
    # .agg() lets us apply a DIFFERENT aggregate function to each
    # column in one step, instead of chaining several .groupby()
    # calls together. The lambda for "cancelled" counts how many
    # rows in that group have class_stat equal to "Cancelled Section".
    # -------------------------------------------------------------
    current_agg = current.groupby("division").agg(
        current_sections=("division", "count"),
        current_enrolled=("total_enrolled", "sum"),
        current_capacity=("enrollment_capacity", "sum"),
        critically_low=("critically_low", "sum"),
        low_not_growing=("low_not_growing", "sum"),
        cancelled=("class_stat", lambda s: (s == "Cancelled Section").sum()),
    ).reset_index()

    # -------------------------------------------------------------
    # PRIOR WEEK, GROUPED BY DIVISION (just sections + enrolled —
    # that's all we need for the "change" comparison)
    # -------------------------------------------------------------
    prior_agg = prior.groupby("division").agg(
        prior_sections=("division", "count"),
        prior_enrolled=("total_enrolled", "sum"),
    ).reset_index()

    # -------------------------------------------------------------
    # COMBINE THEM
    # how="left" keeps every current-week division even if it had
    # no prior-week data; fillna(0) turns any resulting blanks into
    # zeros so the math below doesn't break on missing values.
    # -------------------------------------------------------------
    combined = current_agg.merge(prior_agg, on="division", how="left")
    combined[["prior_sections", "prior_enrolled"]] = combined[
        ["prior_sections", "prior_enrolled"]
    ].fillna(0)

    combined["section_change"] = combined["current_sections"] - combined["prior_sections"]

    # -------------------------------------------------------------
    # GUARD AGAINST DIVIDING BY ZERO
    # A division with 0 total capacity (a data quality issue, same
    # one we found at the section level) would otherwise produce
    # "inf" (infinity) instead of a real percentage. We treat that
    # as "unknown" (NaN) instead — a percentage that doesn't exist
    # is more honest than a nonsense one.
    # -------------------------------------------------------------
    combined["current_fill"] = None
    has_capacity = combined["current_capacity"] > 0
    combined.loc[has_capacity, "current_fill"] = (
        combined.loc[has_capacity, "current_enrolled"]
        / combined.loc[has_capacity, "current_capacity"]
    )

    # -------------------------------------------------------------
    # ADD A TOTAL / COLLEGE AVG ROW
    # This isn't a normal groupby row — it's a hand-built summary
    # row appended at the end, using .sum() across every division.
    # College-wide fill rate is total enrolled / total capacity,
    # NOT the average of each division's fill rate (a small division
    # shouldn't count as much as a huge one).
    # -------------------------------------------------------------
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
