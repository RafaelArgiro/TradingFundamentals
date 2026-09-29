"""Landing page: what this project is and where things live."""

import streamlit as st

st.write(
    "A set of small, self-contained tools for building intuition about trading "
    "fundamentals. Pick a topic from the navigation above."
)

st.subheader("Topics")

with st.container(border=True):
    st.markdown("**Expectancy** &nbsp;:material/query_stats:")
    st.write(
        "How win rate and reward-to-risk combine into an average result per "
        "trade, and how widely outcomes scatter around it."
    )

st.subheader("How this is organised")

st.markdown(
    """
| Location | Contains |
| --- | --- |
| `tfcore/` | All calculations. Never imports Streamlit, so it can be tested on its own. |
| `app_pages/` | One file per page. Display only. |
| `tests/` | Checks for everything in `tfcore/`. Run with `pytest`. |
"""
)

st.caption(
    "Calculations are kept separate from display so the maths can be validated "
    "without launching the interface."
)
