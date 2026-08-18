"""
classification.py
------------------
Shared logic for classifying section risk. Every table on both the
landing page and the drill-down page will eventually call these
functions, so we're building and testing them in isolation first,
separate from any dashboard code.
"""

import pandas as pd


def add_growth_column(df_current, df_prior):
    """
    Adds an 'enrolled_prior' and 'growth' column to df_current by
    matching each section (class_nbr) to its enrollment from a
    PRIOR week's snapshot.

    A section with no matching prior-week row (e.g. a brand-new
    section that didn't exist last week) gets growth = NaN — we
    genuinely don't know if it "grew," so we leave it undetermined
    rather than guessing.
    """
    prior_lookup = df_prior[["class_nbr", "total_enrolled"]].rename(
        columns={"total_enrolled": "enrolled_prior"}
    )
    df = df_current.merge(prior_lookup, on="class_nbr", how="left")
    df["growth"] = df["total_enrolled"] - df["enrolled_prior"]
    return df


def add_fill_rate(df):
    """
    Adds a 'fill_rate' column: enrolled / capacity.

    Sections with zero or missing capacity get fill_rate = NaN
    instead of a real value — dividing by zero would otherwise
    crash, or worse, silently give a meaningless result.
    """
    df = df.copy()
    has_valid_capacity = df["enrollment_capacity"] > 0
    df["fill_rate"] = None
    df.loc[has_valid_capacity, "fill_rate"] = (
        df.loc[has_valid_capacity, "total_enrolled"]
        / df.loc[has_valid_capacity, "enrollment_capacity"]
    )
    return df


def add_critically_low_flag(df):
    """
    Adds a boolean 'critically_low' column.

    Rule: 9 or fewer students enrolled, OR under 25% fill.
    """
    df = df.copy()
    has_valid_fill = df["fill_rate"].notna()
    df["critically_low"] = (
        (df["total_enrolled"] <= 9) |
        (has_valid_fill & (df["fill_rate"] < 0.25))
    )
    return df


def add_low_not_growing_flag(df):
    """
    Adds a boolean 'low_not_growing' column.

    Rule: under 50% fill AND no enrollment growth (growth <= 0)
    in the latest snapshot. Critically Low takes precedence.
    """
    df = df.copy()
    has_valid_fill = df["fill_rate"].notna()
    has_valid_growth = df["growth"].notna()

    df["low_not_growing"] = (
        has_valid_fill & has_valid_growth &
        (df["fill_rate"] < 0.50) &
        (df["growth"] <= 0) &
        (~df["critically_low"])
    )
    return df


def add_capacity_issue_flag(df):
    """
    Adds a boolean 'capacity_issue' column: True when capacity is
    zero, missing, or otherwise invalid.
    """
    df = df.copy()
    df["capacity_issue"] = df["fill_rate"].isna()
    return df


def classify_sections(df_current, df_prior):
    """
    Runs all steps in order and returns the enriched dataframe.
    """
    df =