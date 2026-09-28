"""Smoke test: verifies Streamlit, pandas, numpy, matplotlib and plotly all work."""

import sys

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

matplotlib.use("Agg")  # no GUI backend needed; Streamlit renders the figure itself

st.set_page_config(page_title="Setup smoke test", layout="wide")
st.title("Setup smoke test")

st.subheader("1. Environment")
st.code(
    f"python     {sys.version.split()[0]}\n"
    f"executable {sys.executable}\n"
    f"streamlit  {st.__version__}\n"
    f"pandas     {pd.__version__}\n"
    f"numpy      {np.__version__}\n"
    f"matplotlib {matplotlib.__version__}",
    language="text",
)

st.subheader("2. Interactivity")
n_trades = st.slider("Number of trades", 10, 500, 100, step=10)
win_rate = st.slider("Win rate", 0.0, 1.0, 0.45, step=0.01)
avg_win = st.number_input("Average win (R)", value=2.0, step=0.1)
avg_loss = st.number_input("Average loss (R)", value=1.0, step=0.1)

rng = np.random.default_rng(42)
wins = rng.random(n_trades) < win_rate
results = np.where(wins, avg_win, -avg_loss)

df = pd.DataFrame(
    {
        "trade": np.arange(1, n_trades + 1),
        "result_r": results,
        "equity_r": results.cumsum(),
    }
)

expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss
st.metric("Expectancy per trade (R)", f"{expectancy:.3f}")

st.subheader("3. DataFrame")
st.dataframe(df.head(10), width="stretch")

col_left, col_right = st.columns(2)

with col_left:
    st.caption("matplotlib")
    fig, ax = plt.subplots()
    ax.plot(df["trade"], df["equity_r"])
    ax.axhline(0, linestyle="--", linewidth=0.8)
    ax.set_xlabel("Trade")
    ax.set_ylabel("Cumulative R")
    st.pyplot(fig)

with col_right:
    st.caption("plotly (interactive)")
    st.plotly_chart(
        px.line(df, x="trade", y="equity_r", labels={"equity_r": "Cumulative R"}),
        width="stretch",
    )

st.success("If you can see both charts and the table, every part of the stack works.")
