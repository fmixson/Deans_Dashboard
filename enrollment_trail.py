"""
enrollment_trail.py
--------------------
Builds the "4-Week Enrollment" trail — e.g. "2 → 2 → 3 → 0" — a
quick visual history of how a section's enrollment moved over the
last several snapshots.
"""

import pandas as pd


def build_trail(df_all_weeks, n_weeks=4):
    """
    df_all_weeks: the full multi-week dataframe — needs class_nbr,
                  snapshot_date, total_enrolled columns, covering
                  every week you want considered.
    n_weeks: how many of the MOST RECENT weeks to include in the trail.

    Returns a DataFrame with one row per class_nbr and two columns:
      - trail: the arrow-joined history string, e.g. "2 → 2 → 3 → 0"
      - latest_change: the difference between the last two weeks
    """
    all_dates = sorted(df_all_weeks["snapshot_date"].unique())
    trail_dates = all_dates[-n_weeks:]

    pivot = df_all_weeks.pivot_table(
        index="class_nbr", columns="snapshot_date", values="total_enrolled", aggfunc="first"
    )
    pivot = pivot.reindex(columns=trail_dates)

    def row_to_trail(row):
        parts = []
        for value in row:
            parts.append("—" if pd.isna(value) else str(int(value)))
        return " → ".join(parts)

    trail_strings = pivot.apply(row_to_trail, axis=1)

    if len(trail_dates) >= 2:
        last_col, second_last_col = trail_dates[-1], trail_dates[-2]
        latest_change = pivot[last_col] - pivot[second_last_col]
    else:
        latest_change = pd.Series(None, index=pivot.index)

    result = pd.DataFrame({
        "trail": trail_strings,
        "latest_change": latest_change,
    }).reset_index()

    return result
