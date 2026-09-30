"""Variance: why identical expectancy still produces very different journeys.

Display only -- every calculation lives in `tfcore`.
"""

from math import ceil

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from tfcore.expectancy import expectancy
from tfcore.simulation import equity_percentiles, final_outcomes, simulate_many_curves
from viz.systems import DEFAULT_SYSTEMS, rgba, system_colors, to_inputs

BAND_ALPHA = 0.13
INNER_ALPHA = 0.22
PATH_ALPHA = 0.18
ZERO_LINE_COLOR = "#d62728"
GRID_COLOR = "rgba(128, 128, 128, 0.25)"


@st.cache_data(show_spinner=False)
def run_simulation(win_rate_pct: float, rr: float, n_trades: int, n_runs: int, seed: int):
    return simulate_many_curves(
        to_inputs(win_rate_pct, rr), n_trades=n_trades, n_runs=n_runs, seed=seed
    )


def flattened_paths(curves, limit: int):
    """Many runs as one x/y pair, separated by gaps so Plotly breaks the line.

    A single trace draws far faster than one trace per run.
    """
    sample = curves.iloc[:, :limit]
    trades = sample.index.to_list()
    x: list = []
    y: list = []
    for column in sample.columns:
        x.extend(trades)
        x.append(None)
        y.extend(sample[column].to_list())
        y.append(None)
    return x, y


st.subheader("Introduction")

st.markdown(
    """
The Expectancy page answered one question: *does this system make money?* It
answers it with a single number, and that number is an **average over infinitely
many trades**.

You do not get infinitely many trades. You get a few hundred, in one particular
order, and what you actually experience is a single path drawn from a very wide
distribution of possible paths. Two systems with identical expectancy can deliver
completely different journeys — different swings, different drawdowns, and
different odds of looking like a failure at any given moment.

This page is about that spread. Same edge, different ride.
"""
)

st.markdown(
    """
- **Equity curve** — what range of outcomes does each system actually produce?
- **Drawdown** — how deep are the holes along the way?
- **Measuring win rate** — how many trades before the measured win rate can be
  trusted?
- **Conclusion** — what does this change about choosing a system?
"""
)

systems = DEFAULT_SYSTEMS.copy()
systems["Expectancy (R)"] = [
    expectancy(to_inputs(wr, rr))
    for rr, wr in zip(systems["RR"], systems["Win rate (%)"], strict=True)
]
colors = system_colors(systems["System"])

st.caption("All four systems carry essentially the same edge:")
st.dataframe(
    systems,
    hide_index=True,
    width="content",
    column_config={
        "RR": st.column_config.NumberColumn(format="%.2f"),
        "Win rate (%)": st.column_config.NumberColumn(format="%.1f"),
        "Expectancy (R)": st.column_config.NumberColumn(format="%+.3f"),
    },
)

st.divider()

st.subheader("Equity curve")

st.markdown(
    """
Each system is simulated many times over. Drawing every run would be an
unreadable mess, so each system is summarised as a **fan**: the solid line is the
median outcome, the darker band holds the middle 50% of runs, and the lighter
band holds 80%. The wider the fan, the less the single path you happen to live
through tells you about the system.
"""
)

ctrl_trades, ctrl_runs, ctrl_pick = st.columns([1, 1, 2], vertical_alignment="bottom")
n_trades = ctrl_trades.slider("Number of trades", 20, 1000, 100, step=10)
n_runs = ctrl_runs.slider("Number of simulations", 100, 5000, 1000, step=100)

with ctrl_pick:
    seed = st.number_input("Random seed", min_value=0, value=42, step=1)
    st.caption("Include system")
    with st.container(horizontal=True):
        included = [
            name
            for i, name in enumerate(systems["System"])
            if st.checkbox(str(name), value=True, key=f"variance_include_{i}")
        ]

chosen = systems[systems["System"].isin(included)]

view_col, option_col = st.columns([1, 1], vertical_alignment="bottom")
view = view_col.radio(
    "View",
    ["Percentile fan", "Individual runs"],
    horizontal=True,
    help="The fan summarises every run; individual runs show a sample of paths.",
)
with option_col:
    link_axes = st.toggle("Link axes across panels", value=True)
    n_paths = (
        st.slider("Runs to draw", 10, 500, 100, step=10)
        if view == "Individual runs"
        else 0
    )

if chosen.empty:
    st.info("Select at least one system.")
else:
    simulated = []
    for name, rr, wr in zip(
        chosen["System"], chosen["RR"], chosen["Win rate (%)"], strict=True
    ):
        curves = run_simulation(float(wr), float(rr), n_trades, n_runs, int(seed))
        simulated.append(
            {
                "name": str(name),
                "rr": float(rr),
                "win_rate": float(wr),
                "curves": curves,
                "bands": equity_percentiles(curves, (10, 25, 50, 75, 90)),
                "finals": final_outcomes(curves),
            }
        )

    columns = 2 if len(simulated) > 1 else 1
    rows = ceil(len(simulated) / columns)

    fan = make_subplots(
        rows=rows,
        cols=columns,
        horizontal_spacing=0.10,
        vertical_spacing=0.16,
        subplot_titles=[
            f"{s['name']} — {s['rr']:g}R at {s['win_rate']:g}%" for s in simulated
        ],
    )

    for index, system in enumerate(simulated):
        row, col = divmod(index, columns)
        row, col = row + 1, col + 1
        bands = system["bands"]
        color = colors[system["name"]]

        if view == "Percentile fan":
            for upper, lower, alpha in (
                ("p90", "p10", BAND_ALPHA),
                ("p75", "p25", INNER_ALPHA),
            ):
                fan.add_trace(
                    go.Scatter(
                        x=bands.index,
                        y=bands[upper],
                        mode="lines",
                        line=dict(width=0),
                        showlegend=False,
                        hoverinfo="skip",
                    ),
                    row=row,
                    col=col,
                )
                fan.add_trace(
                    go.Scatter(
                        x=bands.index,
                        y=bands[lower],
                        mode="lines",
                        line=dict(width=0),
                        fill="tonexty",
                        fillcolor=rgba(color, alpha),
                        showlegend=False,
                        hoverinfo="skip",
                    ),
                    row=row,
                    col=col,
                )
        else:
            path_x, path_y = flattened_paths(system["curves"], n_paths)
            fan.add_trace(
                go.Scatter(
                    x=path_x,
                    y=path_y,
                    mode="lines",
                    line=dict(width=0.8, color=rgba(color, PATH_ALPHA)),
                    showlegend=False,
                    hoverinfo="skip",
                ),
                row=row,
                col=col,
            )

        fan.add_trace(
            go.Scatter(
                x=bands.index,
                y=bands["p50"],
                mode="lines",
                line=dict(width=2.5, color=color),
                showlegend=False,
                hovertemplate=(
                    f"{system['name']} · median<br>"
                    "Trade %{x} → %{y:+.1f}R<extra></extra>"
                ),
            ),
            row=row,
            col=col,
        )

        fan.add_hline(
            y=0, line_width=2, line_color=ZERO_LINE_COLOR, row=row, col=col
        )
        fan.update_xaxes(
            title="Trade number",
            showgrid=True,
            gridcolor=GRID_COLOR,
            griddash="dot",
            row=row,
            col=col,
        )
        fan.update_yaxes(
            title="Cumulative result (R)",
            showgrid=True,
            gridcolor=GRID_COLOR,
            griddash="dot",
            zeroline=False,
            row=row,
            col=col,
        )

    if link_axes:
        fan.update_xaxes(matches="x")
        fan.update_yaxes(matches="y")

    fan.update_layout(
        height=110 + 330 * rows,
        showlegend=False,
        margin=dict(t=70, r=30, b=50, l=70),
    )

    st.plotly_chart(
        fan,
        width="stretch",
        config={
            "displaylogo": False,
            "toImageButtonOptions": {
                "format": "png",
                "filename": (
                    "equity_fan" if view == "Percentile fan" else "equity_paths"
                ),
            },
        },
    )

    drawn = (
        f"{min(n_paths, n_runs)} of the {n_runs:,} runs drawn individually"
        if view == "Individual runs"
        else f"all {n_runs:,} runs summarised as percentile bands"
    )
    scale_note = (
        "Panels share one scale, so panel size is directly comparable."
        if link_axes
        else "Each panel is on its own scale — compare shape, not size."
    )
    st.caption(f"{n_trades} trades per run, {drawn}. {scale_note}")

    st.markdown("**Where the runs finish**")

    st.markdown(
        """
The same simulations, reduced to their final result. Every system is drawn on
one shared axis, so the width of each shape is directly comparable — that width
*is* the variance. The box marks the middle 50% and the dashed line the mean.
"""
    )

    spread = go.Figure()
    for system in simulated:
        spread.add_trace(
            go.Violin(
                y=system["finals"],
                name=system["name"],
                line_color=colors[system["name"]],
                fillcolor=rgba(colors[system["name"]], 0.35),
                box_visible=True,
                meanline_visible=True,
                points=False,
                spanmode="hard",
                width=0.85,
                hovertemplate="%{y:+.1f}R<extra></extra>",
            )
        )

    spread.add_hline(y=0, line_width=2, line_color=ZERO_LINE_COLOR)
    spread.update_layout(
        height=520,
        showlegend=False,
        margin=dict(t=40, r=30, b=50, l=70),
        violingap=0.25,
    )
    spread.update_xaxes(title="System")
    spread.update_yaxes(
        title="Final result after %d trades (R)" % n_trades,
        showgrid=True,
        gridcolor=GRID_COLOR,
        griddash="dot",
        zeroline=False,
    )

    st.plotly_chart(
        spread,
        width="stretch",
        config={
            "displaylogo": False,
            "toImageButtonOptions": {
                "format": "png",
                "filename": "final_outcome_distribution",
            },
        },
    )

    summary = [
        {
            "System": system["name"],
            "Median final (R)": system["finals"].median(),
            "Worst 10% (R)": system["finals"].quantile(0.10),
            "Best 10% (R)": system["finals"].quantile(0.90),
            "Spread (R)": system["finals"].quantile(0.90)
            - system["finals"].quantile(0.10),
            "Profitable runs": (system["finals"] > 0).mean(),
        }
        for system in simulated
    ]

    st.dataframe(
        summary,
        hide_index=True,
        width="stretch",
        column_config={
            "Median final (R)": st.column_config.NumberColumn(format="%+.1f"),
            "Worst 10% (R)": st.column_config.NumberColumn(
                format="%+.1f", help="1 run in 10 finished at or below this."
            ),
            "Best 10% (R)": st.column_config.NumberColumn(
                format="%+.1f", help="1 run in 10 finished at or above this."
            ),
            "Spread (R)": st.column_config.NumberColumn(
                format="%.1f", help="Width of the 10-90% range of final outcomes."
            ),
            "Profitable runs": st.column_config.NumberColumn(format="percent"),
        },
    )

st.divider()

st.subheader("Drawdown")

st.info("Next up: how deep the holes get, and how long they last.")

st.divider()

st.subheader("Measuring win rate")

st.info(
    "Next up: how many trades before a measured win rate is trustworthy, and "
    "what that implies for low win rate systems."
)

st.divider()

st.subheader("Conclusion")

st.info("To be written once the sections above are complete.")
