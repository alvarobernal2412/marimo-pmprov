from matplotlib.figure import Figure

_BAR = "#0EA5E9"
_INK = "#374151"


def _styled(figure: Figure):
    ax = figure.subplots()
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#D1D5DB")
    ax.tick_params(colors=_INK, labelsize=8)
    ax.yaxis.grid(True, color="#E5E7EB", linewidth=0.6)
    ax.set_axisbelow(True)
    return ax


def events_per_activity_chart(event_log, activity_col: str = "concept:name") -> Figure:
    """Horizontal bars: how many events each activity has."""
    counts = event_log[activity_col].value_counts().sort_values()
    figure = Figure(figsize=(6.4, 0.45 * len(counts) + 1.1), layout="constrained")
    ax = _styled(figure)
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color="#E5E7EB", linewidth=0.6)
    ax.barh(counts.index.astype(str), counts.to_numpy(), color=_BAR, height=0.62)
    ax.set_xlabel("events", color=_INK, fontsize=8)
    ax.set_title("Events per activity", loc="left", fontsize=10, color=_INK, fontweight="bold")
    ax.bar_label(ax.containers[0], labels=[f"{v:,}" for v in counts], padding=3, fontsize=7.5, color=_INK)
    ax.margins(x=0.12)
    return figure


def events_per_year_chart(event_log, time_col: str = "time:timestamp") -> Figure:
    """Columns: how many events happened in each year."""
    counts = event_log[time_col].dt.year.value_counts().sort_index()
    figure = Figure(figsize=(6.4, 2.8), layout="constrained")
    ax = _styled(figure)
    ax.bar(counts.index.astype(int), counts.to_numpy(), color=_BAR, width=0.7)
    ax.set_xticks(counts.index.astype(int))
    ax.set_ylabel("events", color=_INK, fontsize=8)
    ax.set_title("Events per year", loc="left", fontsize=10, color=_INK, fontweight="bold")
    return figure
