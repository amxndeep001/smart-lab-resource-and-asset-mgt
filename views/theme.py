"""Chart palette and a common Plotly style (validated categorical order + reserved status colors)."""
import plotly.graph_objects as go

# Categorical hues, assigned in this fixed order (never cycled).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
NEUTRAL = "#9a9890"

# Status colors are reserved for state (good / warning / serious / critical).
GOOD, WARNING, SERIOUS, CRITICAL = "#0ca30c", "#fab219", "#ec835a", "#d03b3b"

EQUIPMENT_STATUS_COLORS = {
    "AVAILABLE": GOOD,
    "IN_USE": SERIES[0],
    "UNDER_CALIBRATION": WARNING,
    "UNDER_MAINTENANCE": SERIOUS,
    "RETIRED": NEUTRAL,
}
BOOKING_STATUS_COLORS = {
    "COMPLETED": SERIES[0],
    "APPROVED": GOOD,
    "PENDING": WARNING,
    "REJECTED": CRITICAL,
    "CANCELLED": NEUTRAL,
}
EQUIPMENT_TYPE_COLORS = {"COMPUTING": SERIES[0], "ELECTRONIC": SERIES[1], "MECHANICAL": SERIES[2],
                         "MEASURING": SERIES[3], "MEDICAL": SERIES[4]}
MAINTENANCE_TYPE_COLORS = {"Preventive": SERIES[0], "Repair": SERIES[1], "Inspection": SERIES[2]}
EVENT_COLORS = {"Purchase": SERIES[6], "Booking": SERIES[0], "Maintenance": SERIES[1], "Calibration": SERIES[2],
                "Transfer": SERIES[3], "Warranty": SERIES[4]}


def style_fig(fig: go.Figure, height=320, legend=True) -> go.Figure:
    titled = bool(fig.layout.title.text)
    # Title sits at the very top; a legend goes on its own row underneath it.
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=(84 if legend else 40) if titled else (48 if legend else 8), b=8),
        title=dict(y=0.98, yref="container", yanchor="top", x=0, xanchor="left", font_size=15),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0, title_text=""),
        hoverlabel=dict(namelength=-1),
        bargap=0.25,
    )
    fig.update_xaxes(showgrid=False, title_text=None)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.18)", zeroline=False, title_text=None)
    fig.update_traces(selector=dict(type="bar"), marker_line_width=0)
    fig.update_traces(selector=dict(type="scatter", mode="lines+markers"), line_width=2, marker_size=8)
    return fig
