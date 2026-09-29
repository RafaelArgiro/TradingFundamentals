"""Break-even win rate as a function of reward-to-risk.

Display only -- every calculation lives in `tfcore`.
"""

import plotly.graph_objects as go
import streamlit as st

from tfcore.expectancy import breakeven_curve, breakeven_points

RR_MIN, RR_MAX = 0.2, 10.0
LABEL_POINTS = (0.5, *range(1, 11))
GRID_POINTS = range(1, 11)

# Shading is drawn slightly wider than the data so it reaches the plot edges.
X_LO, X_HI = 0.05, RR_MAX + 0.5
Y_MAX = 95

WIN_FILL = "rgba(0, 160, 80, 0.12)"
LOSS_FILL = "rgba(214, 60, 60, 0.12)"
GRID_COLOR = "rgba(128, 128, 128, 0.25)"
LINE_COLOR = "#1f77b4"
SWEET_SPOT_COLOR = "#1b5e20"

st.latex(r"\text{Break-even win rate} = \frac{1}{1 + RR}")

toggles, lo_col, hi_col = st.columns([2, 1, 1], vertical_alignment="bottom")

with toggles:
    show_shading = st.toggle("Profit / loss shading", value=True)
    show_sweet_spot = st.toggle("Sweet spot", value=False)

rr_lo = lo_col.number_input(
    "Min RR",
    min_value=RR_MIN,
    max_value=RR_MAX,
    value=2.0,
    step=0.1,
    disabled=not show_sweet_spot,
)
rr_hi = hi_col.number_input(
    "Max RR",
    min_value=RR_MIN,
    max_value=RR_MAX,
    value=5.0,
    step=0.1,
    disabled=not show_sweet_spot,
)

if show_sweet_spot and rr_hi <= rr_lo:
    st.warning("Max RR must be greater than Min RR.")
    show_sweet_spot = False

curve = breakeven_curve(RR_MIN, RR_MAX)
marks = breakeven_points(LABEL_POINTS)

fig = go.Figure()

if show_shading:
    shade = breakeven_curve(X_LO, X_HI)
    fig.add_trace(
        go.Scatter(
            x=shade["rr"],
            y=shade["win_rate"] * 100,
            mode="lines",
            line=dict(width=0),
            fill="tozeroy",
            fillcolor=LOSS_FILL,
            hoverinfo="skip",
        )
    )
    # "tonexty" fills against the trace above, giving the region up to the top.
    fig.add_trace(
        go.Scatter(
            x=shade["rr"],
            y=[100] * len(shade),
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor=WIN_FILL,
            hoverinfo="skip",
        )
    )

fig.add_trace(
    go.Scatter(
        x=curve["rr"],
        y=curve["win_rate"] * 100,
        mode="lines",
        line=dict(width=3, color=LINE_COLOR),
        hovertemplate="RR %{x:.2f} → %{y:.1f}%<extra></extra>",
    )
)

fig.add_trace(
    go.Scatter(
        x=marks["rr"],
        y=marks["win_rate"] * 100,
        mode="markers+text",
        marker=dict(size=9, color=LINE_COLOR),
        text=[f"{w * 100:.1f}%" for w in marks["win_rate"]],
        textposition="top right",
        textfont=dict(size=13),
        hovertemplate="RR %{x:.1f} → %{y:.1f}%<extra></extra>",
    )
)

for r in GRID_POINTS:
    fig.add_vline(x=r, line_width=1, line_color=GRID_COLOR, layer="below")

if show_sweet_spot:
    fig.add_vrect(
        x0=rr_lo,
        x1=rr_hi,
        line_width=2,
        line_color=SWEET_SPOT_COLOR,
        fillcolor="rgba(0,0,0,0)",
        layer="above",
        annotation_text="Sweet spot",
        annotation_position="top",
        annotation_font=dict(size=14, color=SWEET_SPOT_COLOR),
    )

fig.update_layout(
    height=560,
    showlegend=False,
    margin=dict(t=40, r=40),
)
fig.update_xaxes(
    title="Reward-to-risk (R)",
    tickmode="array",
    tickvals=[RR_MIN, *LABEL_POINTS],
    ticktext=[f"{RR_MIN}R", *[f"{r}R" for r in LABEL_POINTS]],
    range=[0, X_HI],
    showgrid=False,
)
fig.update_yaxes(
    title="Required win rate (%)",
    ticksuffix="%",
    range=[0, Y_MAX],
    dtick=10,
    gridcolor="rgba(128,128,128,0.2)",
)

st.plotly_chart(fig, width="stretch")
