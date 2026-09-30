"""Variance: why identical expectancy still produces very different journeys.

Display only -- every calculation lives in `tfcore`.
"""

from math import ceil

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from tfcore.expectancy import expectancy
from tfcore.measurement import (
    edge_bound_curve,
    expectancy_standard_error,
    trades_for_win_rate_margin,
    trades_to_prove_edge,
    win_rate_standard_error,
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

The shapes are **combs, not smooth curves**, and that is correct. After $n$
trades exactly $k$ can be winners, so the final result can only take the $n+1$
values $k R - (n - k)$ — spaced $(R+1)$ apart. A 5R system with 100 trades has
possible outcomes 6R apart, so its histogram is a picket fence no matter how
many simulations you run. More simulations make the *envelope* smoother, never
the gaps.
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
            x=0.99,
            y=0.95,
            text=f"{profitable:.1%} profitable",
            showarrow=False,
            xanchor="right",
            font=dict(size=13, color=color),
            bgcolor="rgba(255,255,255,0.75)",
            borderpad=3,
            row=row,
            col=1,
        )
        spread.add_annotation(
            xref="x domain",
            yref="y domain",
            x=0.99,
            y=0.78,
            text=f"σ = {sigma:.0f}R",
            showarrow=False,
            xanchor="right",
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

    st.dataframe(
        drawdown_rows,
        hide_index=True,
        width="stretch",
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
    )

    st.caption(
        "Drawdown is measured in R, so at 1% risk per trade a 20R drawdown is "
        "roughly a 20% account decline. Note that the systems share an edge yet "
        "differ sharply here — **variance, not expectancy, sets the pain.**"
    )

st.divider()

st.subheader("Measuring win rate")

st.markdown(
    """
Everything so far assumed the win rate is *known*. It never is — it is measured
from a finite run of trades, and that measurement carries an error. The question
this section answers is: **how many trades before the number means anything?**
"""
)

st.latex(
    r"\mathrm{SE}(\hat{W}) = \sqrt{\frac{W(1-W)}{n}}"
    r"\qquad\quad"
    r"n_{\text{prove}} = \frac{z^{2}\,(R+1)^{2}\,W(1-W)}{E^{2}}"
)

with st.expander("Derivation"):
    st.markdown(
        "Each trade is a **Bernoulli trial**: it wins with probability $W$ and "
        "loses otherwise. Over $n$ trades the number of winners $k$ follows a "
        "binomial distribution:"
    )
    st.latex(r"k \sim \mathrm{Binomial}(n, W) \qquad \mathrm{Var}(k) = n\,W(1-W)")

    st.markdown(
        "The measured win rate is $\\hat{W} = k/n$. Dividing a random variable "
        "by $n$ divides its variance by $n^{2}$:"
    )
    st.latex(
        r"\mathrm{Var}(\hat{W}) = \frac{n W (1-W)}{n^{2}} = \frac{W(1-W)}{n}"
        r"\qquad\Rightarrow\qquad \mathrm{SE}(\hat{W}) = \sqrt{\frac{W(1-W)}{n}}"
    )

    st.markdown(
        "Note the $\\sqrt{n}$: to **halve** the error you need **four times** "
        "the trades. Precision is expensive."
    )

    st.markdown(
        "For a confidence interval of $\\pm e$, set $z\\,\\mathrm{SE} = e$ and "
        "solve for $n$:"
    )
    st.latex(r"n = \frac{z^{2}\,W(1-W)}{e^{2}}")

    st.markdown(
        "That is the error on the *win rate*. What we actually care about is the "
        "error on the **edge**. Since $E = W(R+1) - 1$ is linear in $W$, the "
        "error passes straight through, multiplied by the slope:"
    )
    st.latex(r"\mathrm{SE}(E) = (R+1)\,\mathrm{SE}(\hat{W})")

    st.markdown(
        "The edge is only believable once its lower confidence bound clears "
        "zero, so require $E - z\\,\\mathrm{SE}(E) > 0$:"
    )
    st.latex(
        r"E > z\,(R+1)\sqrt{\frac{W(1-W)}{n}}"
        r"\qquad\Rightarrow\qquad"
        r"n > \frac{z^{2}(R+1)^{2}W(1-W)}{E^{2}}"
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
for name, rr, wr in zip(
    systems["System"], systems["RR"], systems["Win rate (%)"], strict=True
):
    win_rate = float(wr) / 100
    measurement.append(
        {
            "System": name,
            "RR": float(rr),
            "Win rate (%)": float(wr),
            f"Trades for ±{margin_pp:g}pp": trades_for_win_rate_margin(
                win_rate, margin_pp / 100, confidence
            ),
            "Trades to prove edge": trades_to_prove_edge(
                win_rate, float(rr), confidence
            ),
            "SE of W at 100 trades (pp)": win_rate_standard_error(win_rate, 100) * 100,
            "SE of E at 100 trades (R)": expectancy_standard_error(
                win_rate, float(rr), 100
            ),
        }
    )

st.dataframe(
    measurement,
    hide_index=True,
    width="stretch",
    column_config={
        "RR": st.column_config.NumberColumn(format="%.2f"),
        "Win rate (%)": st.column_config.NumberColumn(format="%.1f"),
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
    },
)

st.markdown(
    """
**The comparison that matters.** Look at the two "trades" columns — they rank
the systems in *opposite* directions.

- Measuring the **win rate** to a fixed precision is *easiest* for the low win
  rate system, because $W(1-W)$ is largest at 50% and shrinks towards either
  extreme.
- Proving the **edge** is *hardest* for that same system, because the
  $(R+1)^{2}$ factor magnifies every remaining scrap of win rate error.

So a high-RR system gives you a precise win rate and an unreliable edge at the
same time. Precision on the input is not the same thing as confidence in the
conclusion.
"""
)

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
    "after that many trades. Until a line crosses the black zero line you cannot "
    "rule out that the system loses money. The diamonds mark the crossing point."
)

st.divider()

st.subheader("Conclusion")

st.info("To be written once the sections above are complete.")
