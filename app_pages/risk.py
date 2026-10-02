"""Risk: turning an edge measured in R into account growth.

Display only -- every calculation lives in `tfcore`.
"""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from tfcore.expectancy import expectancy
from tfcore.risk import (
    compound_equity,
    fixed_equity,
    growth_curve,
    kelly_fraction,
    log_growth_rate,
    max_relative_drawdowns,
    zero_growth_fraction,
)
from viz.systems import DEFAULT_SYSTEMS, rgba, system_colors, to_inputs
from viz.tables import show_table

ZERO_LINE_COLOR = "black"
GRID_COLOR = "rgba(128, 128, 128, 0.25)"
FIXED_COLOR = "#f58518"
PERCENT_COLOR = "#4c78a8"

systems = DEFAULT_SYSTEMS.copy()
systems["Expectancy (R)"] = [
    expectancy(to_inputs(wr, rr))
    for rr, wr in zip(systems["RR"], systems["Win rate (%)"], strict=True)
]
colors = system_colors(systems["System"])


@st.cache_data(show_spinner=False)
def trade_results(win_rate_pct: float, rr: float, n_trades: int, n_runs: int, seed: int):
    inputs = to_inputs(win_rate_pct, rr)
    rng = np.random.default_rng(seed)
    wins = rng.random((n_trades, n_runs)) < inputs.win_rate
    return np.where(wins, inputs.avg_win, -inputs.avg_loss)


st.subheader("Introduction")

st.markdown(
    """
The Expectancy and Variance pages both measure everything in **R**, the amount
risked on a single trade. That was deliberate: it keeps the analysis independent
of account size. This page asks the question that R was hiding — **how large
should R actually be?**

Position sizing is the only input here that is entirely under your control. You
cannot decide your win rate and you cannot decide your reward-to-risk, but you
decide what fraction of the account stands behind every trade. That one number
determines how fast the account grows, how deep the drawdowns go, and whether a
positive edge turns into a positive result at all.
"""
)

st.markdown(
    """
- **Percentual vs fixed** — should the stake follow the account, or stay the
  same size?
- **Kelly optimal** — how much risk maximises long-run growth, and why that
  number is larger than it looks?
- **Equity curves** — what the different choices actually produce.
- **Conclusions** — what to take away.
"""
)

st.caption("The same four systems used on the other pages:")
show_table(
    systems,
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

st.subheader("Percentual vs fixed")

st.markdown(
    """
There are two ways to decide how much to put behind a trade.

**Fixed amount.** Risk the same sum every time, for example 1000 currency units,
regardless of what the account is worth. Equity then moves in a straight line
with the cumulative R total.
"""
)

st.latex(r"\text{equity}_n = \text{equity}_0 + a \sum_{i=1}^{n} r_i")

st.markdown(
    """
**Fixed percentage.** Risk a fixed fraction $f$ of the *current* account, so the
stake grows as the account grows and shrinks as it falls. Each trade multiplies
equity rather than adding to it.
"""
)

st.latex(r"\text{equity}_n = \text{equity}_0 \prod_{i=1}^{n} \left(1 + f\,r_i\right)")

st.markdown(
    """
The difference between a sum and a product is the whole story.

- **Fixed amount cannot compound.** Doubling the account does not change the
  stake, so the second doubling takes just as many R as the first. Growth is
  linear.
- **Fixed amount can reach zero.** A long enough losing run subtracts the same
  sum each time until nothing is left.
- **Fixed percentage compounds.** Gains raise the stake, which raises the next
  gain. Growth is exponential while the edge holds.
- **Fixed percentage cannot reach zero.** Losing $f$ of what remains always
  leaves something behind, so the account can get very small but never
  technically die.
- **Fixed percentage self-corrects.** After a loss the stake automatically
  falls, which is exactly when you want to be risking less.
"""
)

compare_trades, compare_risk, compare_seed = st.columns(3)
compare_n = compare_trades.slider("Trades", 50, 1000, 300, step=10, key="risk_compare_n")
compare_f = compare_risk.slider(
    "Risk per trade (%)", 0.25, 5.0, 2.0, step=0.25, key="risk_compare_f"
)
compare_seed_value = compare_seed.number_input(
    "Random seed", min_value=0, value=7, step=1, key="risk_compare_seed"
)
compare_system = st.selectbox(
    "System", systems["System"], index=1, key="risk_compare_system"
)

row = systems[systems["System"] == compare_system].iloc[0]
single = trade_results(
    float(row["Win rate (%)"]), float(row["RR"]), compare_n, 1, int(compare_seed_value)
)

percent_path = compound_equity(single, compare_f / 100)[:, 0]
fixed_path = fixed_equity(single, compare_f / 100)[:, 0]
trade_axis = np.arange(1, compare_n + 1)

sizing = go.Figure()
sizing.add_trace(
    go.Scatter(
        x=trade_axis,
        y=percent_path,
        mode="lines",
        name=f"{compare_f:g}% of current equity",
        line=dict(width=2.5, color=PERCENT_COLOR),
        hovertemplate="Trade %{x} → %{y:.2f}×<extra></extra>",
    )
)
sizing.add_trace(
    go.Scatter(
        x=trade_axis,
        y=fixed_path,
        mode="lines",
        name=f"{compare_f:g}% of the starting equity, fixed",
        line=dict(width=2.5, color=FIXED_COLOR),
        hovertemplate="Trade %{x} → %{y:.2f}×<extra></extra>",
    )
)
sizing.add_hline(y=1.0, line_width=2, line_color=ZERO_LINE_COLOR)
sizing.update_layout(
    height=440,
    margin=dict(t=70, r=30, b=50, l=70),
    legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0),
)
sizing.update_xaxes(
    title="Trade number", showgrid=True, gridcolor=GRID_COLOR, griddash="dot"
)
sizing.update_yaxes(
    title="Equity (multiple of starting capital)",
    showgrid=True,
    gridcolor=GRID_COLOR,
    griddash="dot",
    zeroline=False,
)

st.plotly_chart(
    sizing,
    width="stretch",
    config={
        "displaylogo": False,
        "toImageButtonOptions": {"format": "png", "filename": "sizing_comparison"},
    },
)

st.caption(
    "Both lines trade the identical sequence of wins and losses. The only "
    "difference is whether the stake follows the account. The black line is the "
    "starting capital."
)

with st.expander("Why compounding earns less than the average trade"):
    st.markdown(
        """
A fixed percentage earns the **geometric** mean of its per-trade multipliers,
not the arithmetic mean. The geometric mean is always the smaller of the two,
and the gap widens with variance. This shortfall is usually called
**volatility drag**.

The simplest demonstration: gain 50%, then lose 50%.
"""
    )
    st.latex(r"1.5 \times 0.5 = 0.75")

    st.markdown(
        """
The arithmetic average of $+50\\%$ and $-50\\%$ is zero, yet the account is down
25%. Nothing went wrong — a product is not a sum.

For small risk fractions the drag is roughly $\\sigma^{2}/2$ per trade, where
$\\sigma$ is the standard deviation of the per-trade return. Doubling the risk
fraction doubles the expected gain but **quadruples** the drag, which is the
reason an optimum exists at all rather than "risk as much as possible".
"""
    )

st.divider()

st.subheader("Kelly optimal")

st.markdown(
    """
If percentage sizing compounds, there must be a fraction that compounds fastest.
Risk too little and the account creeps; risk too much and volatility drag eats
more than the edge adds. The fraction that maximises long-run growth is the
**Kelly fraction**.
"""
)

st.latex(r"f^{*} = W - \frac{1 - W}{R} = \frac{E}{R}")

st.markdown(
    """
The second form is the useful one: **the Kelly fraction is the edge divided by
the payoff.** A system earning 0.32R per trade at 2R payoff gives
$f^{*} = 0.16$, meaning risk 16% of the account on every trade.

That number should look alarming, and it is addressed below.
"""
)

with st.expander("Derivation, step by step"):
    st.markdown(
        """
**Step 1 — what one trade does to the account**

Risking a fraction $f$ of equity, a win multiplies the account by $1 + fR$ and a
loss multiplies it by $1 - f$. Over $n$ trades the multipliers simply multiply
together, so the account after $n$ trades is a product.
"""
    )

    st.markdown(
        """
**Step 2 — turn the product into a sum**

Products are awkward to optimise, but the logarithm of a product is a sum of
logarithms. Maximising the account is the same as maximising its logarithm,
since the logarithm only ever increases. The expected log multiplier per trade
is therefore the quantity to maximise:
"""
    )
    st.latex(r"g(f) = W\,\ln(1 + fR) + (1 - W)\,\ln(1 - f)")

    st.markdown(
        """
**Step 3 — differentiate and set to zero**

A maximum sits where the slope is zero:
"""
    )
    st.latex(r"\frac{dg}{df} = \frac{WR}{1 + fR} - \frac{1 - W}{1 - f} = 0")

    st.markdown("**Step 4.** Move the second term across:")
    st.latex(r"\frac{WR}{1 + fR} = \frac{1 - W}{1 - f}")

    st.markdown("**Step 5.** Cross-multiply:")
    st.latex(r"WR\,(1 - f) = (1 - W)(1 + fR)")

    st.markdown("**Step 6.** Expand both sides:")
    st.latex(r"WR - WRf = 1 - W + fR - WfR")

    st.markdown(
        "**Step 7.** The $WRf$ term appears on both sides and cancels, leaving "
        "only one term in $f$:"
    )
    st.latex(r"WR = 1 - W + fR")

    st.markdown("**Step 8.** Solve for $f$:")
    st.latex(r"f^{*} = \frac{WR - (1 - W)}{R} = \frac{E}{R}")

    st.markdown(
        """
The numerator is exactly the expectancy from the first page. So Kelly is not a
separate idea bolted on — it is the same edge, divided by the size of the payoff
you are collecting it from.
"""
    )

kelly_rows = []
for name, rr, wr in zip(
    systems["System"], systems["RR"], systems["Win rate (%)"], strict=True
):
    inputs = to_inputs(float(wr), float(rr))
    full = kelly_fraction(inputs)
    kelly_rows.append(
        {
            "System": name,
            "Expectancy (R)": expectancy(inputs),
            "Kelly f* (%)": full * 100,
            "Half Kelly (%)": full * 50,
            "Growth at f* (per trade)": log_growth_rate(inputs, full),
            "Growth at half f*": log_growth_rate(inputs, full / 2),
            "Zero growth above (%)": zero_growth_fraction(inputs) * 100,
        }
    )

show_table(
    kelly_rows,
    column_config={
        "Expectancy (R)": st.column_config.NumberColumn(format="%+.3f"),
        "Kelly f* (%)": st.column_config.NumberColumn(
            format="%.1f", help="Risk per trade that maximises compound growth."
        ),
        "Half Kelly (%)": st.column_config.NumberColumn(
            format="%.1f", help="The usual practical compromise."
        ),
        "Growth at f* (per trade)": st.column_config.NumberColumn(
            format="%.4f", help="Expected log growth per trade at full Kelly."
        ),
        "Growth at half f*": st.column_config.NumberColumn(
            format="%.4f", help="Usually about three quarters of the full rate."
        ),
        "Zero growth above (%)": st.column_config.NumberColumn(
            format="%.1f",
            help="Risking more than this loses money despite a positive edge.",
        ),
    },
    formats={
        "Expectancy (R)": "{:+.3f}",
        "Kelly f* (%)": "{:.1f}",
        "Half Kelly (%)": "{:.1f}",
        "Growth at f* (per trade)": "{:.4f}",
        "Growth at half f*": "{:.4f}",
        "Zero growth above (%)": "{:.1f}",
    },
)

curves = go.Figure()
for name, rr, wr in zip(
    systems["System"], systems["RR"], systems["Win rate (%)"], strict=True
):
    inputs = to_inputs(float(wr), float(rr))
    curve = growth_curve(inputs, fraction_max=0.8)
    peak = kelly_fraction(inputs)
    curves.add_trace(
        go.Scatter(
            x=curve["fraction"] * 100,
            y=curve["growth"],
            mode="lines",
            name=str(name),
            line=dict(width=2.5, color=colors[name]),
            hovertemplate=f"{name}<br>risk %{{x:.1f}}% → growth %{{y:.4f}}"
            "<extra></extra>",
        )
    )
    curves.add_trace(
        go.Scatter(
            x=[peak * 100],
            y=[log_growth_rate(inputs, peak)],
            mode="markers",
            marker=dict(size=10, color=colors[name], symbol="diamond"),
            showlegend=False,
            hovertemplate=f"{name} optimum at %{{x:.1f}}%<extra></extra>",
        )
    )

curves.add_hline(y=0, line_width=2, line_color=ZERO_LINE_COLOR)
curves.update_layout(
    title=dict(text="Compound growth against risk per trade", font=dict(size=16)),
    height=460,
    margin=dict(t=80, r=30, b=50, l=70),
    legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0),
)
curves.update_xaxes(
    title="Risk per trade (% of equity)",
    ticksuffix="%",
    showgrid=True,
    gridcolor=GRID_COLOR,
    griddash="dot",
)
curves.update_yaxes(
    title="Expected log growth per trade",
    range=[-0.1, 0.07],
    showgrid=True,
    gridcolor=GRID_COLOR,
    griddash="dot",
    zeroline=False,
)

st.plotly_chart(
    curves,
    width="stretch",
    config={
        "displaylogo": False,
        "toImageButtonOptions": {"format": "png", "filename": "kelly_growth_curves"},
    },
)

st.markdown(
    """
**How to read this curve.** Growth starts at zero when nothing is risked, rises
to the diamond at $f^{*}$, then falls back through the black line. Past that
second crossing a system with a genuine positive edge still loses money, purely
because the position is too large.

Three features matter more than the peak itself:

- **The curve is flat near the top.** Risking half the Kelly fraction usually
  retains about three quarters of the growth rate. You give up little by sizing
  down.
- **The curve is steep on the right.** Over-betting costs far more than
  under-betting by the same margin. The penalty is asymmetric, so errors should
  be made on the small side.
- **$f^{*}$ assumes the inputs are exact.** The Variance page showed that $W$
  and $E$ are estimates with a standard error attached. Kelly computed from an
  overstated edge sits past the true optimum, which is the dangerous side of the
  curve. Treating full Kelly as a **ceiling you never approach** rather than a
  target follows directly from that.
"""
)

st.divider()

st.subheader("Equity curves")

st.markdown(
    """
The growth curve above is a long-run average. This section simulates what
different risk fractions actually produce over a finite number of trades,
including the drawdowns that come with them.
"""
)

sim_system_col, sim_trades_col, sim_runs_col = st.columns(3)
sim_system = sim_system_col.selectbox(
    "System", systems["System"], index=1, key="risk_sim_system"
)
sim_trades = sim_trades_col.slider("Trades", 100, 2000, 500, step=50, key="risk_sim_n")
sim_runs = sim_runs_col.slider(
    "Simulations", 200, 5000, 2000, step=100, key="risk_sim_runs"
)
sim_seed = st.number_input("Random seed", min_value=0, value=42, step=1, key="risk_seed")

sim_row = systems[systems["System"] == sim_system].iloc[0]
sim_inputs = to_inputs(float(sim_row["Win rate (%)"]), float(sim_row["RR"]))
full_kelly = kelly_fraction(sim_inputs)

results = trade_results(
    float(sim_row["Win rate (%)"]),
    float(sim_row["RR"]),
    sim_trades,
    sim_runs,
    int(sim_seed),
)

multiples = [0.25, 0.5, 1.0, 1.5, 2.0]
palette = ["#4c78a8", "#54a24b", "#b279a2", "#f58518", "#e45756"]

fan = go.Figure()
risk_rows = []
for multiple, colour in zip(multiples, palette, strict=True):
    fraction = full_kelly * multiple
    if fraction >= 0.95:
        continue
    equity = compound_equity(results, fraction)
    median_path = np.median(equity, axis=1)
    lower = np.percentile(equity, 10, axis=1)
    upper = np.percentile(equity, 90, axis=1)
    trades = np.arange(1, sim_trades + 1)

    fan.add_trace(
        go.Scatter(
            x=trades,
            y=upper,
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fan.add_trace(
        go.Scatter(
            x=trades,
            y=lower,
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor=rgba(colour, 0.12),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fan.add_trace(
        go.Scatter(
            x=trades,
            y=median_path,
            mode="lines",
            name=f"{multiple:g}× Kelly  ({fraction * 100:.1f}%)",
            line=dict(width=2.5, color=colour),
            hovertemplate=f"{multiple:g}× Kelly<br>trade %{{x}} → %{{y:.2f}}×"
            "<extra></extra>",
        )
    )

    finals = equity[-1]
    risk_rows.append(
        {
            "Risk": f"{multiple:g}× Kelly",
            "Risk per trade (%)": fraction * 100,
            "Median final equity (×)": float(np.median(finals)),
            "Worst 10% final (×)": float(np.percentile(finals, 10)),
            "Runs below start (%)": float((finals < 1).mean() * 100),
            "Median max drawdown (%)": float(
                np.median(max_relative_drawdowns(equity)) * 100
            ),
        }
    )

fan.add_hline(y=1.0, line_width=2, line_color=ZERO_LINE_COLOR)
fan.update_layout(
    height=520,
    margin=dict(t=70, r=30, b=50, l=70),
    legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0),
)
fan.update_xaxes(
    title="Trade number", showgrid=True, gridcolor=GRID_COLOR, griddash="dot"
)
fan.update_yaxes(
    title="Equity (multiple of starting capital)",
    type="log",
    showgrid=True,
    gridcolor=GRID_COLOR,
    griddash="dot",
    zeroline=False,
)

st.plotly_chart(
    fan,
    width="stretch",
    config={
        "displaylogo": False,
        "toImageButtonOptions": {"format": "png", "filename": "risk_equity_fan"},
    },
)

st.caption(
    "Solid lines are the median outcome, shaded bands the middle 80% of runs. "
    "The vertical axis is logarithmic, so a straight line is steady compound "
    "growth. The black line is the starting capital."
)

show_table(
    risk_rows,
    column_config={
        "Risk per trade (%)": st.column_config.NumberColumn(format="%.1f"),
        "Median final equity (×)": st.column_config.NumberColumn(
            format="%.2f", help="Half the runs finished above this multiple."
        ),
        "Worst 10% final (×)": st.column_config.NumberColumn(
            format="%.2f", help="One run in ten finished at or below this."
        ),
        "Runs below start (%)": st.column_config.NumberColumn(
            format="%.1f", help="Share of runs that lost money overall."
        ),
        "Median max drawdown (%)": st.column_config.NumberColumn(
            format="%.1f", help="Typical deepest fall from a peak, in percent."
        ),
    },
    formats={
        "Risk per trade (%)": "{:.1f}",
        "Median final equity (×)": "{:.2f}",
        "Worst 10% final (×)": "{:.2f}",
        "Runs below start (%)": "{:.1f}",
        "Median max drawdown (%)": "{:.1f}",
    },
)

st.markdown(
    """
**What to look for in the table.** Moving from a quarter of Kelly to full Kelly
raises the median result, but it raises the median drawdown far faster. Moving
beyond full Kelly usually raises the drawdown again while the median result
stops improving or starts falling. The worst 10% column deteriorates throughout.

That pattern is the practical content of this page: **the risk fraction that
maximises the median outcome is not the risk fraction you can live with.**
"""
)

st.divider()

st.subheader("Conclusions")

st.markdown(
    """
Expectancy decides whether a system is worth trading, variance decides how hard
it is to hold, and position sizing decides what either of those is actually
worth to the account. It is the only one of the three you set directly.
"""
)

st.markdown(
    """
**On fixed versus percentage**

Percentage sizing compounds and fixed sizing does not, which over any long run
is decisive. Percentage sizing also reduces the stake automatically after
losses, so it cannot be wiped out by a losing streak the way a fixed stake can.
The cost is that a product is not a sum: compounding earns the geometric mean,
which sits below the arithmetic mean by an amount that grows with the square of
the position size.
"""
)

st.markdown(
    """
**On how much to risk**

The Kelly fraction, $f^{*} = E/R$, is the risk level that maximises long-run
growth. For a typical system it comes out far larger than anyone trades, and
there are three good reasons not to use it:

1. **The optimum assumes exact inputs.** $E$ is an estimate with a standard
   error, and an overstated edge produces an overstated $f^{*}$, landing you on
   the wrong side of the peak.
2. **The penalty is asymmetric.** The growth curve is flat to the left of the
   peak and steep to the right, so the cost of risking too little is small and
   the cost of risking too much is large.
3. **The drawdowns are unacceptable.** Full Kelly routinely produces declines
   that no one keeps trading through, which converts a theoretical optimum into
   a practical failure.
"""
)

st.markdown(
    """
**What to do with this**

- **Size as a percentage of current equity, not as a fixed amount.** This is the
  single highest-value change if you are not already doing it.
- **Treat the Kelly fraction as a ceiling, not a target.** A half or a quarter of
  it keeps most of the growth and removes most of the pain.
- **Set the risk from the drawdown you will tolerate, then check the growth.**
  Choosing the growth first and hoping to survive the drawdown is the wrong way
  round.
- **Reduce the risk fraction when the edge is unproven.** If the Variance page
  says you have not yet demonstrated an edge, you have also not yet earned the
  right to size up.
- **Remember what is still missing.** This page assumes a constant edge,
  independent trades, no costs, and perfect execution of the stated size. All
  four assumptions favour larger positions than reality supports.
"""
)

st.markdown(
    """
The single sentence worth carrying away: **expectancy decides whether you make
money, and position sizing decides how much of it you keep.**
"""
)
