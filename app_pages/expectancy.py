"""Expectancy explorer: how win rate and reward-to-risk drive long-run results.

Display only -- every calculation lives in `tfcore`.
"""

import plotly.express as px
import streamlit as st

from tfcore.expectancy import (
    ExpectancyInputs,
    breakeven_win_rate,
    expectancy,
    reward_to_risk,
)
from tfcore.simulation import max_drawdown, simulate_equity_curve, simulate_many_curves

with st.sidebar:
    st.header("System")
    win_rate = st.slider("Win rate", 0.0, 1.0, 0.45, step=0.01)
    avg_win = st.number_input("Average win (R)", min_value=0.0, value=2.0, step=0.1)
    avg_loss = st.number_input("Average loss (R)", min_value=0.1, value=1.0, step=0.1)

    st.header("Simulation")
    n_trades = st.slider("Number of trades", 10, 1000, 200, step=10)
    n_runs = st.slider("Number of runs", 1, 200, 50, step=1)
    seed = st.number_input("Random seed", min_value=0, value=42, step=1)

inputs = ExpectancyInputs(win_rate=win_rate, avg_win=avg_win, avg_loss=avg_loss)
edge = expectancy(inputs)
breakeven = breakeven_win_rate(avg_win, avg_loss)

a, b, c, d = st.columns(4)
a.metric("Expectancy (R/trade)", f"{edge:+.3f}")
b.metric("Reward : risk", f"{reward_to_risk(inputs):.2f} : 1")
c.metric("Breakeven win rate", f"{breakeven:.1%}")
d.metric("Edge over breakeven", f"{win_rate - breakeven:+.1%}")

if edge > 0:
    st.success(f"Positive expectancy: about {edge:+.3f}R per trade on average.")
else:
    st.error(f"Negative expectancy: about {edge:+.3f}R per trade on average.")

single = simulate_equity_curve(inputs, n_trades=n_trades, seed=int(seed))

left, right = st.columns(2)

with left:
    st.subheader("One possible run")
    fig = px.line(single, x="trade", y="equity_r", labels={"equity_r": "Cumulative R"})
    fig.add_hline(y=0, line_dash="dash", line_width=1)
    st.plotly_chart(fig, width="stretch")
    st.caption(
        f"Final: {single['equity_r'].iloc[-1]:+.1f}R  |  "
        f"Max drawdown: {max_drawdown(single['equity_r']):.1f}R"
    )

with right:
    st.subheader(f"{n_runs} runs of the same system")
    many = simulate_many_curves(inputs, n_trades=n_trades, n_runs=n_runs, seed=int(seed))
    fig = px.line(many, labels={"value": "Cumulative R", "index": "trade"})
    fig.add_hline(y=0, line_dash="dash", line_width=1)
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, width="stretch")
    finals = many.iloc[-1]
    st.caption(
        f"Final R across runs — worst {finals.min():+.1f}, "
        f"median {finals.median():+.1f}, best {finals.max():+.1f}  |  "
        f"{(finals > 0).mean():.0%} of runs profitable"
    )

with st.expander("Trade-by-trade data"):
    st.dataframe(single, width="stretch")
