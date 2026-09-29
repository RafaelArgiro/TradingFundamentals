"""Entry point for the multipage app.

Page content lives in `app_pages/`, calculations in `tfcore/`. Run with:
    streamlit run streamlit_app.py
"""

import streamlit as st

st.set_page_config(page_title="Trading Fundamentals", layout="wide")

page = st.navigation(
    [
        st.Page("app_pages/home.py", title="Home", icon=":material/home:"),
        st.Page(
            "app_pages/expectancy.py",
            title="Expectancy",
            icon=":material/query_stats:",
        ),
    ],
    position="top",
)

st.title(page.title, icon=page.icon)
page.run()
