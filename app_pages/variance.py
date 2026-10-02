"""Variance: why identical expectancy still produces very different journeys.

Display only -- every calculation lives in `tfcore`.
"""

from math import ceil

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from tfcore.expectancy import expectancy, expectancy_from_rr, required_win_rate
from tfcore.measurement import (
    edge_bound_curve,
    expectancy_standard_error,
    normal_approximation_is_safe,
    normal_curve,
    trades_for_win_rate_margin,
    trades_to_prove_edge,
    win_rate_standard_error,
    z_for,
)
from tfcore.simulation import (
    equity_percentiles,
    expected_longest_losing_streak,
    final_outcomes,
    longest_losing_streaks,
    longest_underwater,
    max_drawdowns,
    simulate_many_curves,
)
from viz.systems import DEFAULT_SYSTEMS, rgba, system_colors, to_inputs
from viz.tables import show_table

BAND_ALPHA = 0.13
INNER_ALPHA = 0.22
PATH_ALPHA = 0.18
ZERO_LINE_COLOR = "black"
STAT_LINE_COLOR = "#444444"
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

You do not get infinitely many trades. You get a finite number of trades, in a particular
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

static_tables = st.toggle(
    "Copy-friendly tables",
    value=False,
    help=(
        "Renders tables as plain HTML so you can select them with the mouse and "
        "paste them into Word or Google Docs as a real table."
    ),
)

st.caption("All four systems carry essentially the same edge:")
show_table(
    systems,
    static=static_tables,
    column_config={
        "RR": st.column_config.NumberColumn(format="%.2f"),
        "Win rate (%)": st.column_config.NumberColumn(format="%.1f"),
        "Expectancy (R)": st.column_config.NumberColumn(format="%+.3f"),
    },
    formats={
        "RR": "{:.2f}",
        "Win rate (%)": "{:.1f}",
        "Expectancy (R)": "{:+.3f}",
    },
)

st.divider()

st.subheader("Equity curve")

st.markdown(
    """
Each trading system is simulated for the specified number of trades resulting in a single path.
This is repeated for a certain number of runs to capture the variability of outcomes.
The result is a distribution of possible outcomes, which are drawn as a **fan**: the solid line is the
median outcome, the darker band holds the middle 50% of runs, and the lighter
band holds 80%. The wider the fan, the larger the variance of that particular trading system.
"""
)

ctrl_trades, ctrl_runs, ctrl_pick = st.columns([1, 1, 2], vertical_alignment="bottom")
n_trades = ctrl_trades.slider("Number of trades", 20, 2000, 500, step=10)
n_runs = ctrl_runs.slider("Number of simulations", 1000, 20000, 10000, step=500)

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
simulated: list[dict] = []

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
The same simulations, reduced to their final result. Every panel shares one
x-axis, so the width of each histogram is directly comparable — that width *is*
the variance.
"""
    )

    st.markdown(
        """
**Why the shapes look like combs rather than smooth curves**

This is not a glitch, and more simulations will not fix it. The reason is that
a run can only ever finish on a small set of specific values.

Think about what determines the final result. Every trade either wins $R$ or
loses $1R$ — there is nothing in between. So the only thing that varies between
runs is **how many of the trades were winners**. Call that number $k$. Over 100
trades, $k$ can be 0, or 1, or 2, and so on up to 100 — 101 possibilities, and
nothing in between, because you cannot have half a winning trade.

Each value of $k$ produces exactly one final result: you collect $R$ from each
of the $k$ winners and pay $1R$ on each of the $n - k$ losers.
"""
    )
    st.latex(r"\text{final result} = k \cdot R - (n - k) \cdot 1")

    st.markdown(
        """
Now ask what happens if one extra trade had been a winner instead of a loser.
You gain $R$ that you did not have, and you avoid losing $1R$ — so the final
result jumps by $R + 1$. **That jump is the gap between neighbouring teeth in
the comb.**

For a 5R system the gap is $5 + 1 = 6$R. There is simply no run anywhere in the
simulation that finishes 1R or 2R or 3R away from another — the outcomes come in
steps of 6R, and the empty space between them stays empty forever. For a 0.88R
system the gap is only 1.88R, so its teeth sit much closer together and the
histogram looks far smoother.

Running more simulations fills each tooth higher and makes the overall
**outline** of the distribution cleaner, but it can never place a bar in a gap,
because no such outcome exists. If you want a visually smoother shape you have
two options: raise the trade count, which makes the steps small relative to the
total range, or lower the bin count below, which merges neighbouring teeth into
a single bar.
"""
    )

    bin_count = st.number_input(
        "Histogram bins",
        min_value=10,
        max_value=500,
        value=60,
        step=10,
        help="Fewer bins merge neighbouring outcomes into a smoother shape.",
    )

    low = min(float(s["finals"].min()) for s in simulated)
    high = max(float(s["finals"].max()) for s in simulated)
    bin_size = (high - low) / bin_count or 1.0
    pad = (high - low) * 0.09 or 1.0

    spread = make_subplots(
        rows=len(simulated),
        cols=1,
        vertical_spacing=0.10,
        subplot_titles=[
            f"{s['name']} — {s['rr']:g}R at {s['win_rate']:g}%" for s in simulated
        ],
    )

    for index, system in enumerate(simulated):
        row = index + 1
        color = colors[system["name"]]
        finals = system["finals"]
        median = float(finals.median())
        worst = float(finals.quantile(0.10))
        best = float(finals.quantile(0.90))
        sigma = float(finals.std())
        profitable = float((finals > 0).mean())

        spread.add_trace(
            go.Histogram(
                x=finals,
                xbins=dict(start=low, end=high + bin_size, size=bin_size),
                marker_color=rgba(color, 0.75),
                marker_line=dict(width=0),
                showlegend=False,
                hovertemplate="%{x:+.1f}R → %{y} runs<extra></extra>",
            ),
            row=row,
            col=1,
        )
        spread.add_vline(
            x=0, line_width=2, line_color=ZERO_LINE_COLOR, row=row, col=1
        )

        # Percentile labels sit outside their line, the median inside, so none
        # of them overlap the bars or each other.
        for value, dash, label, height, anchor in (
            (worst, "dash", f"worst 10%  {worst:+.0f}R", 0.55, "right"),
            (median, "solid", f"median {median:+.0f}R", 0.40, "center"),
            (best, "dash", f"best 10%  {best:+.0f}R", 0.55, "left"),
        ):
            spread.add_vline(
                x=value,
                line_width=2,
                line_dash=dash,
                line_color=STAT_LINE_COLOR,
                row=row,
                col=1,
            )
            spread.add_annotation(
                x=value,
                yref="y domain",
                y=height,
                text=label,
                showarrow=False,
                xanchor=anchor,
                font=dict(size=11, color=STAT_LINE_COLOR),
                bgcolor="rgba(255,255,255,0.8)",
                borderpad=2,
                row=row,
                col=1,
            )

        # Mean +/- 1 sigma, drawn as a band so the spread is visible as width.
        mean = float(finals.mean())
        spread.add_vrect(
            x0=mean - sigma,
            x1=mean + sigma,
            fillcolor=rgba(color, 0.18),
            line_width=0,
            layer="below",
            row=row,
            col=1,
        )

        spread.add_annotation(
            xref="x domain",
            yref="y domain",
            x=0.01,
            y=0.95,
            text=f"{profitable:.1%} profitable",
            showarrow=False,
            xanchor="left",
            font=dict(size=13, color=color),
            bgcolor="rgba(255,255,255,0.75)",
            borderpad=3,
            row=row,
            col=1,
        )
        spread.add_annotation(
            xref="x domain",
            yref="y domain",
            x=0.01,
            y=0.78,
            text=f"σ = {sigma:.0f}R",
            showarrow=False,
            xanchor="left",
            font=dict(size=12, color=color),
            bgcolor="rgba(255,255,255,0.75)",
            borderpad=3,
            row=row,
            col=1,
        )

        spread.update_xaxes(
            title=f"Final result after {n_trades} trades (R)",
            range=[low - pad, high + pad],
            showticklabels=True,
            showgrid=True,
            gridcolor=GRID_COLOR,
            griddash="dot",
            row=row,
            col=1,
        )
        spread.update_yaxes(
            title="Runs",
            showgrid=True,
            gridcolor=GRID_COLOR,
            griddash="dot",
            row=row,
            col=1,
        )

    spread.update_layout(
        height=180 + 240 * len(simulated),
        showlegend=False,
        bargap=0.02,
        margin=dict(t=60, r=30, b=50, l=70),
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

    st.caption(
        "Solid line is the median, dashed lines the 10th and 90th percentiles, "
        "and the shaded band is one standard deviation either side of the mean. "
        "The black line is break-even."
    )

st.divider()

st.subheader("Drawdown")

st.markdown(
    """
Final results only describe the destination. Drawdown describes the journey —
and the journey is what decides whether you are still trading the system when it
pays off.

Every number below is computed across the same simulations as above, then
summarised over all runs.
"""
)

st.markdown(
    """
**How each metric is calculated**

- **Max drawdown** — within one run, track the *running peak* of the equity
  curve. At each trade the drawdown is `peak − current equity`. The max drawdown
  is the largest such gap anywhere in that run. This is the deepest hole
  measured from the best point reached so far, not from the start.
- **Average / median max drawdown** — the mean and median of that figure across
  all runs. Median is the more honest "typical" number, since the mean is pulled
  up by rare disasters.
- **Worst 5% max drawdown** — the 95th percentile: 1 run in 20 is *worse* than
  this. Plan around this number rather than the average.
- **Longest losing streak** — the most consecutive losing trades in a run,
  averaged across runs. It ignores size and counts only sign.
- **Worst 5% losing streak** — again the 95th percentile of that count.
- **Theoretical streak** — an analytical cross-check,
  $\\ln(n) \\,/\\, -\\ln(1-W)$, which is the streak length you would expect to
  occur about once in $n$ trades. It should land close to the simulated average;
  if it does not, something is wrong with the simulation.
- **Longest time underwater** — the most consecutive trades spent *below* a
  previous equity peak, averaged across runs. A run can be shallow yet take a
  very long time to recover, and that wait is what feels like failure.
"""
)

if not simulated:
    st.info("Select at least one system above.")
else:
    drawdown_rows = []
    for system in simulated:
        curves = system["curves"]
        depths = max_drawdowns(curves)
        streaks = longest_losing_streaks(curves)
        underwater = longest_underwater(curves)
        drawdown_rows.append(
            {
                "System": system["name"],
                "Avg max DD (R)": depths.mean(),
                "Median max DD (R)": depths.median(),
                "Worst 5% DD (R)": depths.quantile(0.95),
                "Avg losing streak": streaks.mean(),
                "Worst 5% streak": streaks.quantile(0.95),
                "Theoretical streak": expected_longest_losing_streak(
                    system["win_rate"] / 100, n_trades
                ),
                "Avg trades underwater": underwater.mean(),
            }
        )

    show_table(
        drawdown_rows,
        static=static_tables,
        column_config={
            "Avg max DD (R)": st.column_config.NumberColumn(
                format="%.1f", help="Mean of each run's deepest peak-to-trough fall."
            ),
            "Median max DD (R)": st.column_config.NumberColumn(
                format="%.1f", help="Half of all runs fell further than this."
            ),
            "Worst 5% DD (R)": st.column_config.NumberColumn(
                format="%.1f", help="1 run in 20 fell further than this."
            ),
            "Avg losing streak": st.column_config.NumberColumn(
                format="%.1f", help="Mean of the longest run of consecutive losses."
            ),
            "Worst 5% streak": st.column_config.NumberColumn(
                format="%.0f", help="1 run in 20 had a longer losing streak."
            ),
            "Theoretical streak": st.column_config.NumberColumn(
                format="%.1f",
                help="ln(n) / -ln(1 - W). A cross-check on the simulated average.",
            ),
            "Avg trades underwater": st.column_config.NumberColumn(
                format="%.0f",
                help="Longest stretch below a previous peak, averaged over runs.",
            ),
        },
        formats={
            "Avg max DD (R)": "{:.1f}",
            "Median max DD (R)": "{:.1f}",
            "Worst 5% DD (R)": "{:.1f}",
            "Avg losing streak": "{:.1f}",
            "Worst 5% streak": "{:.0f}",
            "Theoretical streak": "{:.1f}",
            "Avg trades underwater": "{:.0f}",
        },
    )

    st.caption(
        "Drawdown is measured in R. Note that even if systems share an edge yet "
        "they can differ sharply here — **variance, not expectancy, sets the pain.**"
    )

st.divider()

st.subheader("Measuring win rate and expectancy")

st.markdown(
    """
Everything so far assumed the win rate is *known*. It never is. You measure it
by counting winners over a finite number of trades, and that count is partly luck.
Flip a fair coin 100 times and you will most likely not get exactly 50 heads — you might get
44. Measure a 44% system over 100 trades and you might observe 52%, through no
fault of the system.

So the measured win rate is an **estimate**, written $\\hat{W}$ ("W-hat") to
distinguish it from the true value $W$ you will never actually see. The question
this section answers is: **how many trades before that estimate is worth
anything?**
"""
)

st.markdown(
    """
**The jargon, in plain terms**

- **Standard error (SE)** — this is nothing more than a **standard deviation**,
  of your *measurement* of your win rate. Imagine running the same
  100 trades over and over in parallel universes: each run would hand you a
  slightly different measured win rate. Those measurements scatter around the
  true value, and the SE is their σ. So "SE = 5 pp" means a typical measurement
  lands about 5 percentage points away from the truth.
- **Confidence interval** — the percentage range within which the true win rate is expected to lie.
  Saying "95% confident" means that if you repeated the whole exercise many times, this interval would
  contain the true win rate in about 19 attempts out of 20. In other words: the confidence interval is simply *measured win rate ± z·SE*.
- **$z$** — how many σ wide the confidence interval is.
  The familiar sigma rules apply directly: **±1σ catches 68%** of cases, **±2σ catches 95%**,
  **±3σ catches 99.7%**. The exact figure for 95% is 1.96σ, which is where the
  number 1.96 keeps coming from.
- **$n$** — the number of trades you have observed.



Everything below is just those three ideas applied to a win rate.
"""
)

schematic_curve = normal_curve()
band_68 = schematic_curve[schematic_curve["z"].abs() <= 1]
band_95 = schematic_curve[schematic_curve["z"].abs() <= 1.96]

schematic = go.Figure()
schematic.add_trace(
    go.Scatter(
        x=band_95["z"],
        y=band_95["density"],
        mode="lines",
        line=dict(width=0),
        fill="tozeroy",
        fillcolor="rgba(76, 120, 168, 0.20)",
        hoverinfo="skip",
    )
)
schematic.add_trace(
    go.Scatter(
        x=band_68["z"],
        y=band_68["density"],
        mode="lines",
        line=dict(width=0),
        fill="tozeroy",
        fillcolor="rgba(76, 120, 168, 0.45)",
        hoverinfo="skip",
    )
)
schematic.add_trace(
    go.Scatter(
        x=schematic_curve["z"],
        y=schematic_curve["density"],
        mode="lines",
        line=dict(width=2.5, color="#4c78a8"),
        hoverinfo="skip",
    )
)

for position, dash in ((0, "solid"), (-1, "dot"), (1, "dot"), (-1.96, "dash"), (1.96, "dash")):
    schematic.add_vline(
        x=position,
        line_width=1.5,
        line_dash=dash,
        line_color="#444444",
    )

schematic.add_annotation(
    x=0, y=0.20, text="68%  (±1σ)", showarrow=False, font=dict(size=13, color="#1b3a57")
)
schematic.add_annotation(
    x=0, y=0.055, text="95%  (±1.96σ)", showarrow=False, font=dict(size=13, color="#1b3a57")
)
schematic.add_annotation(
    x=0,
    y=0.425,
    text="your measurement",
    showarrow=False,
    font=dict(size=12, color="#444444"),
)
schematic.add_annotation(
    x=2.9,
    y=0.30,
    text="the true value lives<br>somewhere under this curve",
    showarrow=False,
    align="center",
    font=dict(size=11, color="#666666"),
)

schematic.update_layout(
    height=330,
    showlegend=False,
    margin=dict(t=30, r=20, b=50, l=20),
)
schematic.update_xaxes(
    title="Distance from the measurement, in standard errors (σ)",
    tickmode="array",
    tickvals=[-1.96, -1, 0, 1, 1.96],
    ticktext=["−1.96σ", "−1σ", "measured", "+1σ", "+1.96σ"],
    range=[-4, 4],
    zeroline=False,
)
schematic.update_yaxes(visible=False, range=[0, 0.47])

st.plotly_chart(
    schematic,
    width="stretch",
    config={
        "displaylogo": False,
        "staticPlot": True,
        "toImageButtonOptions": {"format": "png", "filename": "confidence_schematic"},
    },
)

st.caption(
    "One standard error is one σ. Widening the net to ±1.96σ raises the chance "
    "of capturing the true value from 68% to 95% — **higher confidence always "
    "costs you a wider, vaguer interval.** The only way to narrow it without "
    "losing confidence is to collect more trades, which shrinks σ itself."
)

st.markdown(
    """
The standard deviation of the win rate as a function of the true win rate and the number of trades, can be calculated using the formula below.
"""
)

st.latex(r"\mathrm{SE}(\hat{W}) = \sqrt{\frac{W(1-W)}{n}}")

st.markdown(
    """
Turning that around gives the number of trades needed to measure the win rate to
a chosen precision. If you want the interval to be no wider than $\\pm e$ — for
example $e = 0.05$ for five percentage points — then you need:
"""
)

st.latex(r"n_{\text{measure}} = \frac{z^{2}\,W(1-W)}{e^{2}}")

st.markdown(
    """
Reading the three parts:

- $z^{2}$ — **demanding more confidence costs trades.** Going from 95% to 99%
  raises $z$ from 1.96 to 2.576, so the requirement grows by
  $(2.576/1.96)^{2} \\approx 1.7$ times.
- $W(1-W)$ — **how unpredictable each trade is.** This peaks at 0.25 for a 50%
  win rate and falls towards zero at either extreme, so a coin-flip system takes
  the most trades to pin down and a lopsided one the fewest.
- $e^{2}$ — **precision is the expensive part.** The margin is squared, so
  asking for half the error means four times the trades, and a tenth of the
  error means a hundred times.

This is the formula behind the "Trades for ±X pp" column in the table below.
Note what is *absent*: reward-to-risk plays no role, because how often you win
has nothing to do with how much you win.
"""
)

st.markdown(
    """
The number of trades required to "prove" the expectancy within the desired confidence level can be calculated using the formula below.
"""
)

st.latex(r"n_{\text{prove}} = \frac{z^{2}\,(R+1)^{2}\,W(1-W)}{E^{2}}")


with st.expander("Derivation, step by step"):
    st.markdown(
        """
**Step 1 — one trade is a coin flip**

A **Bernoulli trial** is the simplest random event there is: it has two
outcomes, and one of them happens with a fixed probability. A coin flip is one.
So is a trade, if you only record win or lose. The probability of a win is $W$.
"""
    )

    st.markdown(
        """
**Step 2 — many trades give a binomial count**

Run $n$ independent trades and count the winners. That count, call it $k$,
follows a **binomial distribution** — the standard description of "how many
successes in $n$ attempts". It has a known spread:
"""
    )
    st.latex(r"k \sim \mathrm{Binomial}(n, W) \qquad \mathrm{Var}(k) = n\,W(1-W)")

    st.markdown(
        """
**Variance** is a measure of spread: the average squared distance from the
mean. Its square root is the **standard deviation**, which is in the same units
as the thing being measured and is therefore easier to interpret.

Notice $W(1-W)$ is largest at $W = 0.5$ (giving 0.25) and shrinks towards either
extreme. A 50/50 system is the most unpredictable; a 95% system is nearly a
foregone conclusion each time.
"""
    )

    st.markdown(
        """
**Step 3 — turn the count into a rate**

You do not report "44 winners", you report "44%". That means dividing by $n$:
$\\hat{W} = k/n$. A rule of variance is that dividing a quantity by a constant
divides its variance by the **square** of that constant:
"""
    )
    st.latex(
        r"\mathrm{Var}(\hat{W}) = \frac{n\,W(1-W)}{n^{2}} = \frac{W(1-W)}{n}"
    )

    st.markdown("Taking the square root gives the standard error:")
    st.latex(r"\mathrm{SE}(\hat{W}) = \sqrt{\frac{W(1-W)}{n}}")

    st.markdown(
        """
**Why $\\sqrt{n}$ matters so much.** The $n$ sits under a square root, so error
falls *slowly*. To halve your uncertainty you need **four times** the trades; to
reduce it tenfold, a hundred times. This is the single most important practical
consequence on this page — precision is bought at a punishing exchange rate.
"""
    )

    st.markdown(
        """
**Worked example.** A 44% system measured over 100 trades:
"""
    )
    st.latex(
        r"\mathrm{SE} = \sqrt{\frac{0.44 \times 0.56}{100}}"
        r" = \sqrt{0.00246} = 0.0496 \approx 5\text{ pp}"
    )
    st.markdown(
        """
The 95% interval is $\\hat{W} \\pm 1.96 \\times 5 = \\pm 9.7$ percentage
points — so a measured 44% is consistent with anything from **34% to 54%**.
After a hundred trades you barely know which side of break-even you are on.
"""
    )

    st.markdown(
        """
**Step 4 — how many trades for a target precision**

The confidence interval has half-width $z\\,\\mathrm{SE}$. Call the precision you
want $e$, so the interval should be $\\pm e$.

**4a.** Set the half-width equal to the target:
"""
    )
    st.latex(r"z\,\mathrm{SE}(\hat{W}) = e")

    st.markdown("**4b.** Substitute the standard error from step 3:")
    st.latex(r"z\,\sqrt{\frac{W(1-W)}{n}} = e")

    st.markdown("**4c.** Divide both sides by $z$:")
    st.latex(r"\sqrt{\frac{W(1-W)}{n}} = \frac{e}{z}")

    st.markdown("**4d.** Square both sides, both being positive:")
    st.latex(r"\frac{W(1-W)}{n} = \frac{e^{2}}{z^{2}}")

    st.markdown("**4e.** Cross-multiply and solve for $n$:")
    st.latex(r"n = \frac{z^{2}\,W(1-W)}{e^{2}}")

    st.markdown(
        """
**Sanity check.** A 44% system, measured to $\\pm 5$ percentage points at 95%
confidence, so $z = 1.96$, $W(1-W) = 0.2464$ and $e = 0.05$:
"""
    )
    st.latex(
        r"n = \frac{1.96^{2} \times 0.2464}{0.05^{2}}"
        r" = \frac{3.842 \times 0.2464}{0.0025} \approx 379"
    )

    st.markdown(
        """
**Step 5 — carry the error through to the edge**

Knowing the win rate is not the goal; knowing the **edge** is. Recall from the
Expectancy page that $E = W(R+1) - 1$. This is a straight line in $W$ with slope
$(R+1)$, so an error in $W$ becomes an error in $E$ that is $(R+1)$ times
larger:
"""
    )
    st.latex(r"\mathrm{SE}(E) = (R+1)\,\mathrm{SE}(\hat{W})")

    st.markdown(
        """
For the 44% / 2R system above: $\\mathrm{SE}(E) = 3 \\times 0.0496 = 0.149$R.
The edge is 0.32R, so the 95% interval runs from **0.03R to 0.61R**. Positive,
but only just — and that is with a hundred trades behind you.
"""
    )

    st.markdown(
        """
**Step 6 — when is the edge believable?**

An edge is only credible once even the *pessimistic* end of the confidence
interval sits above zero. If the interval still includes zero, "this system
loses money" remains a live possibility.

**6a.** Write down the requirement. The interval runs from
$E - z\\,\\mathrm{SE}(E)$ to $E + z\\,\\mathrm{SE}(E)$, and we want its lower
end to be positive:
"""
    )
    st.latex(r"E - z\,\mathrm{SE}(E) > 0")

    st.markdown("**6b.** Move the second term to the right-hand side:")
    st.latex(r"E > z\,\mathrm{SE}(E)")

    st.markdown("**6c.** Substitute the result from step 5, $\\mathrm{SE}(E) = (R+1)\\,\\mathrm{SE}(\\hat{W})$:")
    st.latex(r"E > z\,(R+1)\,\mathrm{SE}(\hat{W})")

    st.markdown("**6d.** Substitute the standard error itself, from step 3:")
    st.latex(r"E > z\,(R+1)\sqrt{\frac{W(1-W)}{n}}")

    st.markdown(
        """
**6e.** Square both sides. This is only legitimate because both sides are
positive — we are considering a profitable system, so $E > 0$, and the
right-hand side is a square root multiplied by positive constants. Squaring a
positive inequality preserves its direction.
"""
    )
    st.latex(r"E^{2} > z^{2}\,(R+1)^{2}\,\frac{W(1-W)}{n}")

    st.markdown(
        "**6f.** Multiply both sides by $n$. Since $n$ is a positive trade "
        "count, the direction is again unchanged:"
    )
    st.latex(r"n\,E^{2} > z^{2}\,(R+1)^{2}\,W(1-W)")

    st.markdown("**6g.** Finally divide both sides by $E^{2}$, which is positive:")
    st.latex(r"n > \frac{z^{2}\,(R+1)^{2}\,W(1-W)}{E^{2}}")

    st.markdown(
        """
**Sanity check.** Put the 44% / 2R system in: $z = 1.96$, $R + 1 = 3$,
$W(1-W) = 0.2464$, $E = 0.32$.
"""
    )
    st.latex(
        r"n > \frac{1.96^{2} \times 3^{2} \times 0.2464}{0.32^{2}}"
        r" = \frac{3.842 \times 9 \times 0.2464}{0.1024} \approx 83"
    )

    st.markdown(
        """
So about **83 trades** before that system's edge is distinguishable from zero —
matching the table below.

Read the three factors:

- $(R+1)^{2}$ — **high reward-to-risk hurts badly here.** Going from 2R to 5R
  multiplies the required trades by $(6/3)^{2} = 4$.
- $W(1-W)$ — a win rate near 50% needs more trades, near the extremes fewer.
- $E^{2}$ — a **thin edge is brutally expensive**. Halving your edge quadruples
  the evidence required.
"""
    )

    st.markdown(
        """
**Two caveats.**

1. These formulas use the *true* $W$, which you do not have. In practice you
   substitute the measured $\\hat{W}$, which makes the answer itself uncertain.
2. They assume $R$ is known exactly. It is not — it is estimated from the
   winners only, and a low win rate system has very few of those. So every
   number below is an **optimistic floor**; reality needs more trades.

The normal approximation also requires roughly $nW \\ge 10$ and
$n(1-W) \\ge 10$; below that the binomial is too skewed for these intervals.
"""
    )

conf_col, margin_col = st.columns([1, 1], vertical_alignment="bottom")
confidence = conf_col.select_slider(
    "Confidence level (%)", options=[80, 90, 95, 99], value=95
)
margin_pp = margin_col.number_input(
    "Win rate precision (± percentage points)",
    min_value=0.5,
    max_value=15.0,
    value=5.0,
    step=0.5,
)

measurement = []
interval_column = f"{confidence}% interval at 100 trades (R)"
for name, rr, wr in zip(
    systems["System"], systems["RR"], systems["Win rate (%)"], strict=True
):
    win_rate = float(wr) / 100
    edge = expectancy(to_inputs(float(wr), float(rr)))
    se_edge = expectancy_standard_error(win_rate, float(rr), 100)
    half_width = z_for(confidence) * se_edge
    measurement.append(
        {
            "System": name,
            "RR": float(rr),
            "Win rate (%)": float(wr),
            "Expectancy (R)": edge,
            f"Trades for ±{margin_pp:g}pp": trades_for_win_rate_margin(
                win_rate, margin_pp / 100, confidence
            ),
            "Trades to prove edge": trades_to_prove_edge(
                win_rate, float(rr), confidence
            ),
            "SE of W at 100 trades (pp)": win_rate_standard_error(win_rate, 100) * 100,
            "SE of E at 100 trades (R)": se_edge,
            "E / SE at 100 trades": edge / se_edge,
            interval_column: (
                f"{edge - half_width:+.3f}  |  {edge:+.3f}  |  {edge + half_width:+.3f}"
            ),
        }
    )

show_table(
    measurement,
    static=static_tables,
    column_config={
        "RR": st.column_config.NumberColumn(format="%.2f"),
        "Win rate (%)": st.column_config.NumberColumn(format="%.1f"),
        "Expectancy (R)": st.column_config.NumberColumn(
            format="%+.3f", help="The edge implied by this RR and win rate."
        ),
        f"Trades for ±{margin_pp:g}pp": st.column_config.NumberColumn(
            format="%.0f",
            help="Trades needed to measure the win rate to this precision.",
        ),
        "Trades to prove edge": st.column_config.NumberColumn(
            format="%.0f",
            help="Trades before the lower confidence bound on expectancy clears zero.",
        ),
        "SE of W at 100 trades (pp)": st.column_config.NumberColumn(
            format="%.1f", help="One standard error on the win rate after 100 trades."
        ),
        "SE of E at 100 trades (R)": st.column_config.NumberColumn(
            format="%.3f", help="The same error carried through to expectancy."
        ),
        "E / SE at 100 trades": st.column_config.NumberColumn(
            format="%.2f",
            help="How many standard errors the edge sits above zero. Below 2, unproven.",
        ),
        interval_column: st.column_config.TextColumn(
            help="Lower bound | expectancy | upper bound, at the chosen confidence.",
        ),
    },
    formats={
        "RR": "{:.2f}",
        "Win rate (%)": "{:.1f}",
        "Expectancy (R)": "{:+.3f}",
        f"Trades for ±{margin_pp:g}pp": "{:.0f}",
        "Trades to prove edge": "{:.0f}",
        "SE of W at 100 trades (pp)": "{:.1f}",
        "SE of E at 100 trades (R)": "{:.3f}",
        "E / SE at 100 trades": "{:.2f}",
    },
)

st.markdown(
    """
**What each column means**

- **Expectancy** — the edge implied by the RR and win rate as entered, with no
  uncertainty attached. It is the number every other column is judged against.
- **Trades for ±X pp** — how many trades you need before the win rate itself is
  pinned down to within X percentage points, at the confidence level chosen
  above. Read it as: *"until I have this many trades, I do not really know my
  win rate to that precision."* It depends only on the win rate and the
  confidence demanded, not on the reward-to-risk — measuring how often you win
  has nothing to do with how much you win.
- **Trades to prove edge** — how many trades before the pessimistic end of the
  confidence interval on expectancy rises above zero. Below this count, "the
  system loses money" is still a possibility you cannot rule out. This is the
  more demanding and more honest of the two, because it is the question you
  actually care about. A backtest shorter than this number has not demonstrated
  an edge, however good the equity curve looks.
- **SE of W at 100 trades** — the one-sigma standard deviation on the measured win rate
  after a fixed 100 trades, in percentage points. It is a snapshot of
  measurement quality at a common sample size, so systems can be compared
  like-for-like. Multiply by roughly 2 to get the 95% interval: an SE of 4 pp
  means a measured win rate could plausibly be 8 points either side of the
  truth.
- **SE of E at 100 trades** — the same one-sigma standard deviation uncertainty, carried through to
  expectancy in R. It is the win rate error multiplied by $(R+1)$, so a
  high reward-to-risk system amplifies the same measurement wobble into a much
  larger uncertainty about its edge. **Compare this number against the system's
  actual expectancy**: if the standard error is a large fraction of the edge,
  the edge is not yet established, regardless of what the point estimate says.
- **E / SE at 100 trades** — how many standard
  errors the edge sits above zero after 100 trades. This is the single most
  useful column. Under 1, the edge is indistinguishable from noise; around 2 it
  becomes statistically credible; above 3 it is solid. The same ratio at a
  different trade count scales with $\\sqrt{n}$, so quadrupling the trades
  doubles it.
- **Interval** — the pessimistic bound, the expectancy, and the optimistic
  bound, after 100 trades at the confidence you selected. Read the left-hand
  number first: that is the worst the system might really be, given what a
  100-trade sample can tell you. **If it is negative, the system has not been
  shown to work.** The width of the whole range is a direct picture of how much
  you still do not know.
"""
)

st.markdown(
    """
**The comparison that matters**

The two "trades" columns answer questions that sound almost identical — *how
long until I know my win rate?* and *how long until I know I have an edge?* —
yet they can rank the same set of systems in **opposite** directions. Seeing why
is the point of this whole section.

The first column is driven by $W(1-W)$, which measures how unpredictable an
individual trade is. It peaks at 0.25 when the win rate is 50% and falls away
towards either extreme, because a lopsided system is already fairly predictable:
if you win 9 times in 10, very few samples are needed to establish that. The
reward-to-risk never enters this calculation at all.

The second column keeps that same $W(1-W)$ term but multiplies it by
$(R+1)^{2}$ and divides by $E^{2}$. Those two extra factors change everything.
A large reward-to-risk means each remaining scrap of win rate error is magnified
into a much bigger uncertainty about the edge, and a thin edge leaves less room
for that uncertainty to live in. So the very systems whose win rate is easiest
to measure can be the hardest to validate.

- Measuring the **win rate** to a fixed precision is easiest when the win rate
  sits far from 50%, because $W(1-W)$ peaks in the middle and shrinks towards
  either extreme.
- Proving the **edge** gets harder as reward-to-risk rises, because the
  $(R+1)^{2}$ factor magnifies whatever win rate error remains.

The practical consequence is worth stating plainly: a high reward-to-risk system
can hand you a precise win rate and an unreliable edge at the same time.
**Precision on the input is not the same thing as confidence in the
conclusion**, and only the second one tells you whether the system is worth
trading.
"""
)

with st.expander("Worst-case edge still consistent with the data"):
    bound_colors = system_colors(systems["System"])
    max_trades = int(
        max(
            trades_to_prove_edge(float(wr) / 100, float(rr), confidence)
            for rr, wr in zip(systems["RR"], systems["Win rate (%)"], strict=True)
        )
        * 1.6
    )

    bounds = go.Figure()
    for name, rr, wr in zip(
        systems["System"], systems["RR"], systems["Win rate (%)"], strict=True
    ):
        curve = edge_bound_curve(float(wr) / 100, float(rr), max_trades, confidence)
        needed = trades_to_prove_edge(float(wr) / 100, float(rr), confidence)
        bounds.add_trace(
            go.Scatter(
                x=curve["trades"],
                y=curve["lower"],
                mode="lines",
                name=str(name),
                line=dict(width=2.5, color=bound_colors[name]),
                hovertemplate=(
                    f"{name}<br>%{{x}} trades → worst case %{{y:+.3f}}R<extra></extra>"
                ),
            )
        )
        bounds.add_trace(
            go.Scatter(
                x=[needed],
                y=[0],
                mode="markers+text",
                marker=dict(size=11, color=bound_colors[name], symbol="diamond"),
                text=[f"{needed:.0f}"],
                textposition="bottom center",
                textfont=dict(size=12, color=bound_colors[name]),
                showlegend=False,
                hovertemplate=f"{name} needs %{{x:.0f}} trades<extra></extra>",
            )
        )

    bounds.add_hline(y=0, line_width=2, line_color=ZERO_LINE_COLOR)
    bounds.update_layout(
        title=dict(
            text=f"Worst-case edge still consistent with the data ({confidence}%)",
            font=dict(size=16),
        ),
        height=460,
        margin=dict(t=80, r=30, b=50, l=70),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0),
    )
    bounds.update_xaxes(
        title="Trades observed",
        showgrid=True,
        gridcolor=GRID_COLOR,
        griddash="dot",
    )
    bounds.update_yaxes(
        title="Lower bound on expectancy (R per trade)",
        range=[-0.6, 0.45],
        showgrid=True,
        gridcolor=GRID_COLOR,
        griddash="dot",
        zeroline=False,
    )

    st.plotly_chart(
        bounds,
        width="stretch",
        config={
            "displaylogo": False,
            "toImageButtonOptions": {"format": "png", "filename": "edge_confidence"},
        },
    )

    st.caption(
        "Each line is the **worst** expectancy still compatible with the evidence "
        "after that many trades. Until a line crosses the black zero line you "
        "cannot rule out that the system loses money. The diamonds mark the "
        "crossing point."
    )

st.divider()

st.subheader("Calculator")

st.markdown(
    """
Everything above compares hypothetical systems. This section turns the same
maths on **your own trading record**: enter what you have actually done so far
and it reports how much of what you see is real and how much is still noise.
"""
)

st.markdown(
    """
**What to enter**

- **Trades taken** — every closed trade in the sample, winners and losers.
- **Winning trades** — how many of those finished in profit.
- **Average win / average loss (R)** — the typical size of a winner and of a
  loser, both as positive numbers. If you always risk the same amount and always
  stop out at your stop, the average loss is 1R. Enter what you actually got,
  not what you planned.
- **Confidence level** — how certain you want to be. Higher means wider, more
  cautious intervals.
"""
)

calc_trades, calc_wins, calc_conf = st.columns(3)
taken = calc_trades.number_input("Trades taken", min_value=1, value=60, step=1)
won = calc_wins.number_input("Winning trades", min_value=0, value=27, step=1)
calc_confidence = calc_conf.select_slider(
    "Confidence level (%)", options=[80, 90, 95, 99], value=95, key="calc_confidence"
)

calc_win_col, calc_loss_col = st.columns(2)
avg_win = calc_win_col.number_input(
    "Average win (R)", min_value=0.01, value=2.0, step=0.05
)
avg_loss = calc_loss_col.number_input(
    "Average loss (R)", min_value=0.01, value=1.0, step=0.05
)

if won > taken:
    st.error("Winning trades cannot exceed trades taken.")
else:
    measured_w = won / taken
    # Expressing the payoff relative to the average loss is what makes it an R
    # multiple, so a 2.0R win against a 0.5R loss behaves like 4R.
    measured_rr = avg_win / avg_loss
    measured_edge = expectancy_from_rr(measured_w, measured_rr)
    z = z_for(calc_confidence)

    se_w = win_rate_standard_error(measured_w, taken)
    se_e = expectancy_standard_error(measured_w, measured_rr, taken)
    breakeven = required_win_rate(measured_rr)

    row_a = st.columns(4)
    row_a[0].metric("Measured win rate", f"{measured_w:.1%}")
    row_a[1].metric("Reward-to-risk", f"{measured_rr:.2f}R")
    row_a[2].metric("Expectancy", f"{measured_edge:+.3f}R")
    row_a[3].metric(
        "Total result", f"{measured_edge * taken:+.1f}R", help="Expectancy × trades."
    )

    row_b = st.columns(4)
    row_b[0].metric("σ of win rate", f"{se_w * 100:.1f} pp")
    row_b[1].metric("σ of expectancy", f"{se_e:.3f}R")
    row_b[2].metric(
        "Break-even win rate",
        f"{breakeven:.1%}",
        delta=f"{(measured_w - breakeven) * 100:+.1f} pp buffer",
    )
    row_b[3].metric(
        "Edge in σ",
        f"{measured_edge / se_e:.2f}σ" if se_e > 0 else "—",
        help="How many standard errors the edge sits above zero. Below 2, unproven.",
    )

    st.markdown(f"**{calc_confidence}% confidence interval — win rate**")
    row_c = st.columns(4)
    row_c[0].metric("Lower bound", f"{(measured_w - z * se_w):.1%}")
    row_c[1].metric("Measured", f"{measured_w:.1%}")
    row_c[2].metric("Upper bound", f"{(measured_w + z * se_w):.1%}")
    row_c[3].metric("Half-width", f"± {z * se_w * 100:.1f} pp")

    st.markdown(f"**{calc_confidence}% confidence interval — expectancy**")
    row_d = st.columns(4)
    row_d[0].metric("Lower bound", f"{measured_edge - z * se_e:+.3f}R")
    row_d[1].metric("Measured", f"{measured_edge:+.3f}R")
    row_d[2].metric("Upper bound", f"{measured_edge + z * se_e:+.3f}R")
    row_d[3].metric("Half-width", f"± {z * se_e:.3f}R")

    estimate_curve = normal_curve()
    estimates = make_subplots(
        rows=1,
        cols=2,
        horizontal_spacing=0.10,
        subplot_titles=(
            "Where the true win rate could be",
            "Where the true expectancy could be",
        ),
    )

    panels = (
        (1, measured_w * 100, se_w * 100, breakeven * 100, "break-even", "#4c78a8"),
        (2, measured_edge, se_e, 0.0, "zero", "#54a24b"),
    )

    for col, centre, sigma, threshold, threshold_label, colour in panels:
        x_all = centre + estimate_curve["z"] * sigma
        inside = estimate_curve["z"].abs() <= z

        estimates.add_trace(
            go.Scatter(
                x=x_all[inside],
                y=estimate_curve["density"][inside],
                mode="lines",
                line=dict(width=0),
                fill="tozeroy",
                fillcolor=rgba(colour, 0.35),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=1,
            col=col,
        )
        estimates.add_trace(
            go.Scatter(
                x=x_all,
                y=estimate_curve["density"],
                mode="lines",
                line=dict(width=2.5, color=colour),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=1,
            col=col,
        )

        estimates.add_vline(
            x=centre, line_width=2, line_color=colour, row=1, col=col
        )
        for bound in (centre - z * sigma, centre + z * sigma):
            estimates.add_vline(
                x=bound,
                line_width=1.5,
                line_dash="dash",
                line_color=colour,
                row=1,
                col=col,
            )
        estimates.add_vline(
            x=threshold,
            line_width=2.5,
            line_color=ZERO_LINE_COLOR,
            annotation_text=threshold_label,
            annotation_position="top",
            annotation_font=dict(size=12, color=ZERO_LINE_COLOR),
            row=1,
            col=col,
        )

        # Keep the threshold in view even when the interval sits far from it.
        span = max(4 * sigma, abs(centre - threshold) * 1.25)
        estimates.update_xaxes(
            range=[
                min(centre - span, threshold - 0.3 * span),
                max(centre + span, threshold + 0.3 * span),
            ],
            showgrid=True,
            gridcolor=GRID_COLOR,
            griddash="dot",
            row=1,
            col=col,
        )
        estimates.update_yaxes(visible=False, row=1, col=col)

    estimates.update_xaxes(title="Win rate (%)", ticksuffix="%", row=1, col=1)
    estimates.update_xaxes(title="Expectancy (R per trade)", row=1, col=2)
    estimates.update_layout(
        height=360,
        showlegend=False,
        margin=dict(t=60, r=30, b=50, l=30),
    )

    st.plotly_chart(
        estimates,
        width="stretch",
        config={
            "displaylogo": False,
            "toImageButtonOptions": {"format": "png", "filename": "calculator_intervals"},
        },
    )

    st.caption(
        "Each curve shows where the true value plausibly sits given your record: "
        "centred on your measurement, with a width set by the standard error. "
        "The shaded band is the "
        f"{calc_confidence}% interval. **If the black line falls inside the "
        "shaded band, you cannot yet rule out that the system is break-even or "
        "worse.** Collecting more trades narrows both curves."
    )

    if measured_edge <= 0:
        st.error(
            f"The measured edge is {measured_edge:+.3f}R per trade. On this "
            "record the system loses money, so there is nothing to confirm — "
            "the win rate would need to exceed "
            f"{breakeven:.1%} to break even at this reward-to-risk."
        )
    else:
        required = trades_to_prove_edge(measured_w, measured_rr, calc_confidence)
        remaining = max(0, ceil(required - taken))
        if remaining == 0:
            st.success(
                f"With {taken} trades you are past the {required:.0f} needed. The "
                f"edge is distinguishable from zero at {calc_confidence}% "
                "confidence — the lower bound above is positive."
            )
        else:
            st.warning(
                f"About **{required:.0f} trades** are needed before this edge is "
                f"distinguishable from zero at {calc_confidence}% confidence. You "
                f"have {taken}, so roughly **{remaining} more** to go. Until then "
                "the lower bound above stays negative and a losing system cannot "
                "be ruled out."
            )

    if not normal_approximation_is_safe(measured_w, taken):
        st.info(
            "With this few trades (or this lopsided a win rate) the normal "
            "approximation is shaky — the rule of thumb wants at least 10 "
            "winners and 10 losers. Treat the intervals as rough."
        )

    st.markdown(
        """
**How to read the output**

- **Measured win rate** and **expectancy** are what your record shows. They are
  estimates, not truths.
- **σ of win rate / σ of expectancy** are the standard errors: the typical gap
  between those estimates and reality, given how many trades you have.
- **Break-even win rate** is what this reward-to-risk needs to merely break
  even; the delta beneath it is your buffer.
- **Edge in σ** is the single most useful number here. It is expectancy divided
  by its own standard error, so it says how many sigma your edge sits above
  zero. Under 2, the result is not yet statistically convincing however good the
  total looks.
- The **confidence intervals** give the range of true values consistent with
  your record. If the expectancy interval includes zero, you do not yet have
  evidence of an edge.
"""
    )

with st.expander("Formulas used"):
    st.markdown("Measured win rate, from $k$ winners in $n$ trades:")
    st.latex(r"\hat{W} = \frac{k}{n}")

    st.markdown(
        "Reward-to-risk expressed as an R multiple, so the average loss becomes "
        "the unit of risk:"
    )
    st.latex(r"R = \frac{\text{average win}}{\text{average loss}}")

    st.markdown("Expectancy per trade, in R:")
    st.latex(r"E = \hat{W}(R + 1) - 1")

    st.markdown("Standard error of the win rate, and of the expectancy:")
    st.latex(
        r"\mathrm{SE}(\hat{W}) = \sqrt{\frac{\hat{W}(1-\hat{W})}{n}}"
    )
    st.latex(r"\mathrm{SE}(E) = (R+1)\,\mathrm{SE}(\hat{W})")

    st.markdown("Confidence intervals at the chosen $z$:")
    st.latex(r"\hat{W} \pm z\,\mathrm{SE}(\hat{W}) \qquad E \pm z\,\mathrm{SE}(E)")

    st.markdown("Break-even win rate for this reward-to-risk:")
    st.latex(r"W^{*} = \frac{1}{1 + R}")

    st.markdown("Trades needed before the edge clears zero:")
    st.latex(r"n_{\text{prove}} = \frac{z^{2}(R+1)^{2}\hat{W}(1-\hat{W})}{E^{2}}")

    st.markdown(
        """
Note that these use the **measured** $\\hat{W}$ in place of the true $W$, so the
required trade count is itself an estimate — it will move as your record grows.
"""
    )

st.divider()

st.subheader("Conclusion")

st.markdown(
    """
**Expectancy of a trading system describes the theoretical destination. Variance describes the journey — and the
journey is the part you have to live through.** Two systems built to the same
edge produced the same median outcome in every simulation above, yet one arrived
there in a narrow band while the other swung across a range several times wider.
When looking at the median, both are equally profitable, however a system with
higher variance is more difficult to hold on to as you need the psychological fortitude to withstand larger swings.
"""
)

st.markdown(
    """
**What the simulations showed**

The fan charts and histograms make the same point from two directions: the
average outcome is not the typical experience. Expectancy is the centre of a
distribution, and the width of that distribution grows with the reward-to-risk
ratio. A system that wins rarely but large collects its edge in infrequent
lumps, so over any realistic number of trades the result depends heavily on how
many of those lumps happened to land inside your sample.

The drawdown table turns that abstraction into something concrete. Losing
streaks are governed almost entirely by the win rate, not by expectancy at all:
the lower the win rate, the longer the stretches of consecutive losses and the
deeper the holes. Because drawdown is measured in R, the translation to your
account is direct — a 20R drawdown at 1% risk per trade is a 20% decline. The
systems being compared share an identical edge, and yet the pain they inflict
differs significantly. **Variance, not expectancy, sets how hard a
system is to trade.**
"""
)

st.markdown(
    """
**What the measurement maths showed**

The second half of the page attacks a different illusion. Every win rate you
quote is an estimate taken from a finite sample, and it carries a standard error
of $\\sqrt{W(1-W)/n}$. That error does not vanish quickly: it shrinks with the
square root of the trade count, so quadrupling your sample only halves your
uncertainty.

What makes this sharper than it first appears is that the corresponding error for the expectancy $E$ does not stay
confined to the win rate. It is multiplied by $(R+1)$ on its way into the edge,
so the higher the reward-to-risk, the more a small misreading of the win rate
distorts your view of profitability.

That leads to an awkward pairing. A high reward-to-risk system normally comes
with a low win rate, and a low win rate is **easy** to measure precisely —
there is not much ambiguity in a system that wins twice in ten. Yet the *edge*
of that same system is the **hardest** of all to confirm, because the $(R+1)$
multiplier turns even a small win rate error into a large uncertainty about
whether the system makes money at all. Knowing an input precisely is not the
same thing as knowing the conclusion confidently.

Now combine that with the first half of the page, and a trap appears. A high
reward-to-risk system works against you in two ways at once:

1. **Its outcomes are widely spread.** An ordinary unlucky stretch can leave you
   far below the median for a long time, with nothing actually wrong.
2. **Its edge takes many trades to confirm.** During that same stretch you have
   no statistical grounds to argue the system is fine.

The result is a long window in which the system looks broken and you cannot
prove that it is not — which is precisely the window in which most people
abandon it.
"""
)

st.markdown(
    """
**What to do with this**

- **Be careful to judge a system from a trading trajectory as this is only a single path you happened to get.**
  Remember this when looking at the results of a backtest or a live trading trajectory.
- **Expect the losing streaks.** They are a prediction of the model, not a sign
  that anything has broken. Knowing in advance that a given win rate implies a
  streak of a certain length removes most of its power to make you abandon a
  working system.
- **Treat an edge as unproven until you have enough data to confidenly say that the expectancy
  is at least two standard errors above zero.** The calculator reports exactly this. Below 2σ, the honest statement is
  "I do not yet know", regardless of how good the running total looks.
- **Winrates are hard to verify as you need a lot of trades (large sample size) irrespective of the exact trading system.**
- **Expectancy (edges) is easier to verify early.**
- **Remember what is still missing.** Everything here is measured per trade and
  assumes the win rate and reward-to-risk stay constant. Trade frequency,
  changing market conditions, and your own consistency are not modelled, and all
  three matter.
"""
)

st.markdown(
    """
The single sentence worth carrying away: **a positive expectancy tells you a
system is worth trading in the long run, but the variance tells you what to expect along the way.**
"""
)
