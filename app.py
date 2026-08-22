today = pd.Timestamp.now().normalize()
latest["days_until_start"] = (pd.to_datetime(latest["start_date"], errors="coerce") - today).dt.days
latest["eligible_for_risk_lists"] = latest["days_until_start"] <= 30

latest["critically_low"] = (
    latest["critically_low"] & latest["eligible_for_risk_lists"] & (latest["class_stat"] != "Cancelled Section")
)
latest["low_not_growing"] = (
    latest["low_not_growing"] & latest["eligible_for_risk_lists"] & (latest["class_stat"] != "Cancelled Section")
)
