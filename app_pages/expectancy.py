"""Break-even win rate as a function of reward-to-risk.

Display only -- every calculation lives in `tfcore`.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tfcore.expectancy import breakeven_curve, breakeven_points, expectancy_from_rr
from tfcore.robustness import (
    critical_rr,
    critical_win_rate,
    rr_buffer,
    sensitivity_range,
    win_rate_buffer,
)

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
SYSTEM_COLOR = "#d62728"
POSITIVE_COLOR = "#2e7d32"
SYSTEM_PALETTE = ["#4c78a8", "#f58518", "#54a24b", "#b279a2"]

DEFAULT_SYSTEMS = pd.DataFrame(
    {
        "System": ["A", "B", "C", "D"],
        "RR": [0.8, 2.0, 3.0, 5.0],
        "Win rate (%)": [70.0, 45.0, 35.0, 22.0],
    }
)

st.latex(r"\text{Break-even win rate} = \frac{1}{1 + RR}")

toggles, lo_col, hi_col = st.columns([2, 1, 1], vertical_alignment="bottom")

with toggles:
    show_shading = st.toggle("Profit / loss shading", value=True)
    show_sweet_spot = st.toggle("Sweet spot", value=False)
    show_systems = st.toggle("Trading systems", value=False)

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
    value=4.5,
    step=0.1,
    disabled=not show_sweet_spot,
)

if show_sweet_spot and rr_hi <= rr_lo:
    st.warning("Max RR must be greater than Min RR.")
    show_sweet_spot = False

# Rendered at the end, once the trading systems below are known.
chart_slot = st.container()

st.subheader("Trading systems")

input_col, bar_col = st.columns(2)

with input_col:
    edited = st.data_editor(
        DEFAULT_SYSTEMS,
        key="systems_editor",
        hide_index=True,
        num_rows="fixed",
        column_config={
            "System": st.column_config.TextColumn("System", width="small"),
            "RR": st.column_config.NumberColumn(
                "RR", min_value=0.1, max_value=RR_MAX, step=0.1, format="%.1f"
            ),
            "Win rate (%)": st.column_config.NumberColumn(
                "Win rate (%)", min_value=0.0, max_value=100.0, step=1.0, format="%.1f"
            ),
        },
    )
    st.caption("Clear a row's numbers to leave it out.")

systems = edited.dropna(subset=["RR", "Win rate (%)"]).copy()
if not systems.empty:
    systems["Expectancy (R)"] = [
        expectancy_from_rr(wr / 100, rr)
        for rr, wr in zip(systems["RR"], systems["Win rate (%)"], strict=True)
    ]
    systems["Label"] = [
        f"{name}<br>{rr:.1f}R · {wr:.0f}%"
        for name, rr, wr in zip(
            systems["System"], systems["RR"], systems["Win rate (%)"], strict=True
        )
    ]

with bar_col:
    if systems.empty:
        st.info("Enter at least one system to see its expectancy.")
    else:
        bar = go.Figure(
            go.Bar(
                x=systems["Label"],
                y=systems["Expectancy (R)"],
                marker_color=[
                    POSITIVE_COLOR if e > 0 else SYSTEM_COLOR
                    for e in systems["Expectancy (R)"]
                ],
                text=[f"{e:+.2f}R" for e in systems["Expectancy (R)"]],
                textposition="outside",
                hovertemplate="%{x}<br>%{y:+.3f}R per trade<extra></extra>",
            )
        )
        bar.add_hline(y=0, line_width=1, line_color=GRID_COLOR)
        bar.update_layout(
            height=330,
            showlegend=False,
            margin=dict(t=30, r=20, b=60, l=60),
        )
        bar.update_yaxes(
            title="Expectancy (R per trade)",
            gridcolor="rgba(128,128,128,0.2)",
            zeroline=False,
        )
        bar.update_xaxes(title="", tickfont=dict(size=12))
        st.plotly_chart(bar, width="stretch")

st.subheader("Robustness")

if systems.empty:
    st.info("Enter at least one system to see its robustness.")
else:
    robustness = pd.DataFrame(
        {
            "System": systems["System"],
            "RR": systems["RR"],
            "Win rate (%)": systems["Win rate (%)"],
            "Expectancy (R)": systems["Expectancy (R)"],
            "Critical WR (%)": [critical_win_rate(rr) * 100 for rr in systems["RR"]],
            "WR buffer (pp)": [
                win_rate_buffer(wr / 100, rr) * 100
                for rr, wr in zip(systems["RR"], systems["Win rate (%)"], strict=True)
            ],
            "Critical RR": [critical_rr(wr / 100) for wr in systems["Win rate (%)"]],
            "RR buffer (R)": [
                rr_buffer(wr / 100, rr)
                for rr, wr in zip(systems["RR"], systems["Win rate (%)"], strict=True)
            ],
        }
    )

    st.dataframe(
        robustness,
        hide_index=True,
        width="stretch",
        column_config={
            "RR": st.column_config.NumberColumn(format="%.1f"),
            "Win rate (%)": st.column_config.NumberColumn(format="%.1f"),
            "Expectancy (R)": st.column_config.NumberColumn(format="%+.3f"),
            "Critical WR (%)": st.column_config.NumberColumn(
                format="%.1f", help="Win rate at which expectancy hits zero."
            ),
            "WR buffer (pp)": st.column_config.NumberColumn(
                format="%+.1f",
                help="Percentage points the win rate can fall before breaking even.",
            ),
            "Critical RR": st.column_config.NumberColumn(
                format="%.2f", help="Reward-to-risk at which expectancy hits zero."
            ),
            "RR buffer (R)": st.column_config.NumberColumn(
                format="%+.2f",
                help="How much R the average win can shrink before breaking even.",
            ),
        },
    )

st.subheader("Elasticity")

if systems.empty:
    st.info("Enter at least one system to see its sensitivity.")
else:
    ctrl_wr, ctrl_rr, ctrl_pick = st.columns([1, 1, 2], vertical_alignment="bottom")
    wr_dev = ctrl_wr.slider("Win rate deviation (%)", 1, 50, 5)
    rr_dev = ctrl_rr.slider("RR deviation (%)", 1, 50, 5)

    with ctrl_pick:
        normalize = st.toggle(
            "Normalise to % of unchanged expectancy",
            value=False,
            help="Aligns every system at 100% so relative sensitivity is comparable.",
        )
        st.caption("Include system")
        with st.container(horizontal=True):
            included = [
                name
                for i, name in enumerate(systems["System"])
                if st.checkbox(str(name), value=True, key=f"tornado_include_{i}")
            ]

    chosen = systems[systems["System"].isin(included)]

    if normalize:
        unprofitable = chosen[chosen["Expectancy (R)"] <= 0]["System"].tolist()
        if unprofitable:
            st.warning(
                "Normalising needs a positive baseline. Excluded: "
                + ", ".join(str(s) for s in unprofitable)
            )
        chosen = chosen[chosen["Expectancy (R)"] > 0]

    if chosen.empty:
        st.info("Select at least one system.")
    else:
        colors = {
            name: SYSTEM_PALETTE[i % len(SYSTEM_PALETTE)]
            for i, name in enumerate(systems["System"])
        }

        def tornado_figure(parameter: str, dev: int, title: str) -> go.Figure:
            is_win_rate = parameter == "win_rate"
            param_unit = "%" if is_win_rate else "R"

            bars = []
            for name, rr, wr, base in zip(
                chosen["System"],
                chosen["RR"],
                chosen["Win rate (%)"],
                chosen["Expectancy (R)"],
                strict=True,
            ):
                low, high = sensitivity_range(wr / 100, rr, parameter, dev)
                if normalize:
                    low, high, base = low / base * 100, high / base * 100, 100.0

                nominal = wr if is_win_rate else rr
                bars.append((str(name), low, high, base, nominal * dev / 100))

            unit = "%" if normalize else "R"
            places = 0 if normalize else 2
            delta_places = 0 if normalize else 3

            fig = go.Figure()
            for name, low, high, base, param_step in bars:
                param_text = f"{param_step:.3g}{param_unit}"
                fig.add_trace(
                    go.Bar(
                        y=[name],
                        x=[high - low],
                        base=[low],
                        orientation="h",
                        name=name,
                        legendgroup=name,
                        marker_color=colors[name],
                        marker_line=dict(width=0),
                        text=[param_text],
                        textposition="inside",
                        insidetextanchor="start",
                        constraintext="none",
                        textfont=dict(size=12, color="white"),
                        hovertemplate=(
                            f"{name} · {title} ±{dev}%<br>"
                            f"{title} shift ±{param_text}<br>"
                            f"Change {low - base:+.{delta_places}f} to "
                            f"{high - base:+.{delta_places}f}{unit}<br>"
                            f"Expectancy {low:+.{places}f} to {high:+.{places}f}{unit}"
                            f"<br>Unchanged {base:+.{places}f}{unit}<extra></extra>"
                        ),
                    )
                )
                # Anchored outward from each end so narrow bars do not collide.
                for value, anchor, pad in ((low, "right", -8), (high, "left", 8)):
                    fig.add_annotation(
                        x=value,
                        y=name,
                        text=f"{value - base:+.{delta_places}f}{unit}",
                        showarrow=False,
                        xanchor=anchor,
                        xshift=pad,
                        font=dict(size=12, color=colors[name]),
                    )
                fig.add_trace(
                    go.Scatter(
                        x=[base],
                        y=[name],
                        mode="markers",
                        marker=dict(
                            symbol="line-ns-open",
                            size=16,
                            color="#444",
                            line=dict(width=2),
                        ),
                        showlegend=False,
                        hoverinfo="skip",
                    )
                )

            fig.add_vline(x=0, line_width=2, line_color=SYSTEM_COLOR)
            fig.update_layout(
                title=dict(text=f"{title} ±{dev}%", font=dict(size=16)),
                height=150 + 48 * len(bars),
                barmode="overlay",
                bargap=0.45,
                margin=dict(t=80, r=55, b=50, l=10),
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0
                ),
            )
            fig.update_xaxes(
                title=(
                    "Expectancy (% of unchanged)"
                    if normalize
                    else "Expectancy (R per trade)"
                ),
                ticksuffix="%" if normalize else "",
                showgrid=True,
                gridcolor="rgba(128,128,128,0.35)",
                griddash="dot",
                zeroline=False,
            )
            # Plotly stacks categories bottom-up, so reverse to get A at the top.
            fig.update_yaxes(
                title="",
                tickfont=dict(size=13),
                categoryorder="array",
                categoryarray=[b[0] for b in reversed(bars)],
            )
            return fig

        wr_col, rr_col = st.columns(2)
        with wr_col:
            st.plotly_chart(
                tornado_figure("win_rate", wr_dev, "Win rate"), width="stretch"
            )
        with rr_col:
            st.plotly_chart(tornado_figure("rr", rr_dev, "RR"), width="stretch")


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

if show_systems and not systems.empty:
    fig.add_trace(
        go.Scatter(
            x=systems["RR"],
            y=systems["Win rate (%)"],
            mode="markers+text",
            marker=dict(
                size=13,
                color=SYSTEM_COLOR,
                line=dict(width=1.5, color="white"),
            ),
            text=systems["System"],
            textposition="middle right",
            textfont=dict(size=13, color=SYSTEM_COLOR),
            customdata=systems["Expectancy (R)"],
            hovertemplate=(
                "%{text}<br>RR %{x:.1f} at %{y:.1f}%"
                "<br>Expectancy %{customdata:+.3f}R<extra></extra>"
            ),
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

with chart_slot:
    st.plotly_chart(fig, width="stretch")
