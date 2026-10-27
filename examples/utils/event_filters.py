import pandas as pd


def filter_events_by_activity(
    event_log: pd.DataFrame, activities, activity_col: str = "concept:name"
) -> pd.DataFrame:
    """Keep only the events whose activity is in *activities*."""
    return event_log[event_log[activity_col].isin(list(activities))].copy()


def filter_events_since(
    event_log: pd.DataFrame, year: int, time_col: str = "time:timestamp"
) -> pd.DataFrame:
    """Keep only the events that happened in *year* or later."""
    return event_log[event_log[time_col].dt.year >= year].copy()
