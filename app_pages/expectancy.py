"""Break-even win rate as a function of reward-to-risk.

Display only -- every calculation lives in `tfcore`.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from tfcore.expectancy import (
    breakeven_curve,
    breakeven_points,
    expectancy_from_rr,
    expectancy_vs_rr,
    expectancy_vs_win_rate,
    iso_expectancy_curve,
    rr_for_iso_win_rate,
)
from tfcore.robustness import (
    absolute_sensitivity_range,
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
ISO_COLOR = "rgba(125, 125, 125, 0.65)"
ISO_LEVELS = [round(0.1 * i, 1) for i in range(1, 11)]
# Each label is placed where its curve crosses this win rate, which spreads
# them diagonally instead of bunching at one edge.
ISO_LABEL_WIN_RATES = [0.75 - 0.061 * i for i in range(len(ISO_LEVELS))]
LINE_Y_RANGE = (-0.5, 1.0)

DEFAULT_SYSTEMS = pd.DataFrame(
    {
        "System": ["A", "B", "C", "D"],
        "RR": [0.88, 2.0, 3.0, 5.0],
        "Win rate (%)": [70.0, 44.0, 33.0, 22.0],
    }
)

def build_tornado_pair(
    left_bars: list[tuple[str, float, float, float, str]],
    right_bars: list[tuple[str, float, float, float, str]],
    *,
    left_title: str,
    right_title: str,
    colors: dict,
    x_title: str,
    delta_places: int,
    delta_unit: str,
    tick_suffix: str = "",
) -> go.Figure:
    """Two side-by-side tornado panels in one figure.

    Each bar entry is `(name, low, high, baseline, inside_label)`.
    """
    fig = make_subplots(
        rows=1,
        cols=2,
        horizontal_spacing=0.10,
        subplot_titles=(left_title, right_title),
    )

    for col, bars, panel_title in (
        (1, left_bars, left_title),
        (2, right_bars, right_title),
    ):
        for name, low, high, base, inside in bars:
            fig.add_trace(
                go.Bar(
                    y=[name],
                    x=[high - low],
                    base=[low],
                    orientation="h",
                    name=name,
                    legendgroup=name,
                    showlegend=col == 1,
                    marker_color=colors[name],
                    marker_line=dict(width=0),
                    text=[inside],
                    textposition="inside",
                    insidetextanchor="start",
                    constraintext="none",
                    textfont=dict(size=12, color="white"),
                    hovertemplate=(
                        f"{name} · {panel_title}<br>"
                        f"Shift ±{inside}<br>"
                        f"Change {low - base:+.{delta_places}f} to "
                        f"{high - base:+.{delta_places}f}{delta_unit}<br>"
                        f"Expectancy {low:+.{delta_places}f} to "
                        f"{high:+.{delta_places}f}{delta_unit}"
                        f"<br>Unchanged {base:+.{delta_places}f}{delta_unit}"
                        "<extra></extra>"
                    ),
                ),
                row=1,
                col=col,
            )
            # Anchored outward from each end so narrow bars do not collide.
            for value, anchor, pad in ((low, "right", -8), (high, "left", 8)):
                fig.add_annotation(
                    x=value,
                    y=name,
                    text=f"{value - base:+.{delta_places}f}{delta_unit}",
                    showarrow=False,
                    xanchor=anchor,
                    xshift=pad,
                    font=dict(size=12, color=colors[name]),
                    row=1,
                    col=col,
                )
            fig.add_trace(
                go.Scatter(
                    x=[base],
                    y=[name],
                    mode="markers",
                    marker=dict(
                        symbol="line-ns-open", size=16, color="#444", line=dict(width=2)
                    ),
                    showlegend=False,
                    hoverinfo="skip",
                ),
                row=1,
                col=col,
            )

        fig.add_vline(x=0, line_width=2, line_color=SYSTEM_COLOR, row=1, col=col)
        fig.update_xaxes(
            title=x_title,
            ticksuffix=tick_suffix,
            showgrid=True,
            gridcolor="rgba(128,128,128,0.35)",
            griddash="dot",
            zeroline=False,
            row=1,
            col=col,
        )

    fig.update_layout(
        height=170 + 52 * len(left_bars),
        barmode="overlay",
        bargap=0.45,
        margin=dict(t=90, r=55, b=50, l=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    # Plotly stacks categories bottom-up, so reverse to get A at the top.
    for col, bars in ((1, left_bars), (2, right_bars)):
        fig.update_yaxes(
            title="",
            tickfont=dict(size=13),
            categoryorder="array",
            categoryarray=[b[0] for b in reversed(bars)],
            row=1,
            col=col,
        )
    return fig


def system_colors(names) -> dict:
    return {
        name: SYSTEM_PALETTE[i % len(SYSTEM_PALETTE)] for i, name in enumerate(names)
    }


def include_picker(names, key_prefix: str) -> list:
    st.caption("Include system")
    with st.container(horizontal=True):
        return [
            name
            for i, name in enumerate(names)
            if st.checkbox(str(name), value=True, key=f"{key_prefix}_{i}")
        ]


def export_config(filename: str) -> dict:
    """Name the file the chart toolbar's download button produces."""
    return {
        "displaylogo": False,
        "toImageButtonOptions": {"format": "png", "filename": filename},
    }


st.subheader("Introduction")

st.markdown(
    """
**Expectancy** is the average result of a single trade, repeated many times. It
is the one number that decides whether a system makes or loses money in the long
run — everything else is detail.

Results are measured in **R**, where 1R is the amount risked on one trade.
Throughout this page the average loss is fixed at exactly **1R**, so a stop-out
costs 1R and the reward-to-risk ratio **RR** is simply how many R a typical
winner returns.
"""
)

st.latex(
    r"E \;=\; \underbrace{W \cdot R}_{\text{what you win}} \;-\;"
    r"\underbrace{(1 - W) \cdot 1}_{\text{what you lose}}"
    r"\;=\; W\,(R + 1) - 1"
)

st.markdown(
    "with $W$ the win rate and $R$ the reward-to-risk ratio."
)

st.markdown(
    """
**What is on this page**

- **Break-even line** — what win rate does a given RR need just to break even?
- **Trading systems** — where do my own systems sit, and what is each one worth
  per trade?
- **Robustness** — how much room does each system have before its edge
  disappears?
- **Elasticity** — if a parameter is off by a given *percentage*, what happens
  to expectancy?
- **Absolute sensitivity** — if a parameter is off by a fixed *amount*, what
  happens, and how steep is the relationship?
- **Conclusion** — what should I take away from all of it?
"""
)

st.divider()

st.subheader("Break-even line")

st.markdown(
    """
Setting $E = 0$ and solving for $W$ gives the win rate a system needs just to
stand still. Below the curve every system loses money, above it every system
makes money, and the dotted grey lines mark fixed levels of expectancy above
break-even.
"""
)

st.latex(r"\text{Break-even win rate} = W^{*} = \frac{1}{1 + R}")

with st.expander("Derivation"):
    st.markdown("Start from expectancy, with the average loss fixed at 1R:")
    st.latex(r"E = W \cdot R - (1 - W) \cdot 1")

    st.markdown("Expand the loss term:")
    st.latex(r"E = W R - 1 + W")

    st.markdown("Collect the two $W$ terms:")
    st.latex(r"E = W\,(R + 1) - 1")

    st.markdown("Break-even means earning nothing per trade, so set $E = 0$:")
    st.latex(r"W\,(R + 1) - 1 = 0")

    st.markdown("Move the constant across:")
    st.latex(r"W\,(R + 1) = 1")

    st.markdown("And divide by $(R + 1)$:")
    st.latex(r"W^{*} = \frac{1}{1 + R}")

    st.markdown(
        "Solving the same equation for $R$ instead gives the mirror image — the "
        "reward-to-risk a given win rate needs:"
    )
    st.latex(r"R^{*} = \frac{1 - W}{W}")

toggles, lo_col, hi_col = st.columns([2, 1, 1], vertical_alignment="bottom")

with toggles:
    show_shading = st.toggle("Profit / loss shading", value=True)
    show_sweet_spot = st.toggle("Sweet spot", value=False)
    show_systems = st.toggle("Trading systems", value=True)
    show_isobars = st.toggle("Iso-expectancy lines", value=True)

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

st.divider()

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
                "RR", min_value=0.01, max_value=RR_MAX, step=0.01, format="%.2f"
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
        st.plotly_chart(
            bar, width="stretch", config=export_config("expectancy_by_system")
        )

st.divider()

st.subheader("Robustness")

st.markdown(
    """
Expectancy says whether a system works; robustness says how much room it has
before it stops working. Each measure below is a **distance to break-even** —
how far a parameter can drift before the edge is gone.
"""
)

st.markdown(
    """
- **Critical WR** — the win rate at which expectancy reaches zero, for this
  system's RR.
- **WR buffer** — percentage points the win rate can fall before that happens.
  Bigger is safer.
- **Critical RR** — the reward-to-risk at which expectancy reaches zero, for
  this system's win rate.
- **RR buffer** — how much R the average win can shrink before that happens.
"""
)

with st.expander("Derivation"):
    st.markdown(
        "Both critical values are the break-even equation solved for one "
        "parameter while the other is held fixed:"
    )
    st.latex(r"W^{*} = \frac{1}{1 + R} \qquad R^{*} = \frac{1 - W}{W}")

    st.markdown("A buffer is simply the distance from the break-even line to the system's nominal expectancy:")
    st.latex(
        r"\text{WR buffer} = W - W^{*} \qquad \text{RR buffer} = R - R^{*}"
    )

    st.markdown(
        "The buffers are not merely *related* to expectancy — they are "
        "expectancy, rescaled. Starting from $E = W(R+1) - 1$ and factoring out "
        "$(R+1)$:"
    )
    st.latex(
        r"E = (R + 1)\left(W - \frac{1}{R + 1}\right) = (R + 1)\,(W - W^{*})"
    )

    st.markdown("Doing the same with $W$ factored out instead:")
    st.latex(
        r"E = W\left(R - \frac{1 - W}{W}\right) = W\,(R - R^{*})"
    )

    st.markdown(
        "So $E = (R+1) \\times \\text{WR buffer} = W \\times \\text{RR buffer}$."
    )

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

st.divider()

st.subheader("Elasticity")

st.markdown(
    """
Robustness measured distance in fixed units; elasticity measures it in
**percentages**. Each parameter ($W$ and $R$) is varied by a chosen percentage of its own
value, and the bars show where expectancy lands — so systems of very different
size can be compared on the same footing.
"""
)

st.markdown(
    """
- **Elasticity $\\varepsilon$** — percent change in expectancy per 1% change in
  a parameter. Higher means more fragile.
- **Bar length** — how far expectancy moves when the parameter is varied down
  and up by the chosen percentage. The larger the bar, the more sensitive the system is to changes in that parameter.
- **In-bar label** — Absolute value of parameter change corresponding to the chosen variation percentage.
- **Tick** — Expectancy at system's nominal value.
- **Red line** — the break-even line ($E = 0$).
"""
)

with st.expander("Derivation"):
    st.markdown(
        "Elasticity is the ratio of two relative changes, which cancels the "
        "units and makes the two parameters comparable:"
    )
    st.latex(
        r"\varepsilon_x = \frac{\Delta E / E}{\Delta x / x}"
        r" = \frac{\partial E}{\partial x} \cdot \frac{x}{E}"
    )

    st.markdown(
        "Because $E = W(R+1) - 1$ is linear in each parameter separately, the "
        "two derivatives are constants:"
    )
    st.latex(
        r"\frac{\partial E}{\partial W} = R + 1 \qquad \frac{\partial E}{\partial R} = W"
    )

    st.markdown("Substituting, and using $W(R+1) = E + 1$ to simplify the first:")
    st.latex(
        r"\varepsilon_W = \frac{W (R + 1)}{E} = \frac{E + 1}{E}"
        r" \qquad \varepsilon_R = \frac{W R}{E}"
    )

    st.markdown(
        "The relative drop a system can absorb before breaking even is exactly "
        "the inverse:"
    )
    st.latex(
        r"\frac{W - W^{*}}{W} = 1 - \frac{1}{W(1+R)} = \frac{E}{E + 1}"
        r" = \frac{1}{\varepsilon_W}"
    )

    st.markdown(
        """
Three consequences:

- **Win rate is always the weaker link.** The ratio
  $\\varepsilon_W / \\varepsilon_R = (R+1)/R = 1 + 1/R$ is greater than 1 for
  every system — by 2× at 1R, but only 1.1× at 10R.
- **Win-rate fragility depends only on expectancy.** $\\varepsilon_W = (E+1)/E$
  contains no $W$ or $R$, so two systems with the same edge are equally fragile
  to a percentage win-rate error, whatever their RR. This does **not** carry
  over to $\\varepsilon_R = WR/E$, which still depends on the win rate:
  substituting $WR = E + 1 - W$ gives $\\varepsilon_R = \\varepsilon_W - W/E$,
  so a higher win rate makes a system *less* elastic to RR.
- **Thin edges are explosively fragile.** $\\varepsilon_W \\to \\infty$ as
  $E \\to 0$: at $E = 0.35$ a 1% win-rate error costs 3.9% of the edge, at
  $E = 0.01$ it costs 101%.

One caveat: because $E$ is linear in each parameter ($W$ and $R$), these results are **exact**
for any single-parameter deviation, not just small ones. They are only valid for single-parameter deviations and become an
approximation if both parameters move at once.
"""
    )

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
        included = include_picker(systems["System"], "tornado_include")

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
        colors = system_colors(systems["System"])

        def relative_bars(parameter: str, dev: int) -> list:
            is_win_rate = parameter == "win_rate"
            param_unit = "%" if is_win_rate else "R"
            rows = []
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
                step = (wr if is_win_rate else rr) * dev / 100
                rows.append((str(name), low, high, base, f"{step:.3g}{param_unit}"))
            return rows

        x_title = (
            "Expectancy (% of unchanged)" if normalize else "Expectancy (R per trade)"
        )
        shared = dict(
            colors=colors,
            x_title=x_title,
            delta_places=0 if normalize else 3,
            delta_unit="%" if normalize else "R",
            tick_suffix="%" if normalize else "",
        )

        st.plotly_chart(
            build_tornado_pair(
                relative_bars("win_rate", wr_dev),
                relative_bars("rr", rr_dev),
                left_title=f"Win rate ±{wr_dev}%",
                right_title=f"RR ±{rr_dev}%",
                **shared,
            ),
            width="stretch",
            config=export_config("elasticity_tornado"),
        )

        st.caption(
            "Each bar shows where expectancy lands if that one parameter is off by "
            "the chosen amount. The tick marks the nominal value, and the red "
            "line is break-even — **a bar crossing it means that error alone can "
            "wipe out the edge.** Longer bars mean greater sensitivity."
        )

st.divider()

st.subheader("Absolute sensitivity")

st.markdown(
    """
The mirror image of elasticity. There every system was knocked off by the same
*percentage* of its own value; here every system is knocked off by the same
*fixed amount* — the same percentage-point shift in $W$, the same shift in $R$.
That makes the bars directly comparable in R, and answers a different question:
not "who is most fragile relative to itself", but "who suffers most from the
same real-world mistake".
"""
)

st.markdown(
    """
- **Bar length** — how far expectancy moves when the parameter is shifted down
  and up by the chosen amount. Because the shift is identical for every system,
  a longer bar simply means that system converts the same error into a bigger
  loss of edge.
- **In-bar label** — what that fixed shift represents as a percentage of this
  system's own value, so you can see how severe it really is for each.
- **Tick** — the nominal value: expectancy at the parameters as entered, with no
  shift applied.
- **Red line** — the break-even line ($E = 0$).
- **Line plots** — expectancy across the full range of one parameter, with the
  other held at that system's value. The **slope** is the sensitivity and the
  crossing of the red line is the break-even point.
"""
)

with st.expander("Derivation"):
    st.markdown(
        "A fixed shift multiplied by the relevant derivative gives the change in "
        "expectancy directly. The derivatives are constants, so no approximation "
        "is involved:"
    )
    st.latex(
        r"\frac{\partial E}{\partial W} = R + 1 \qquad \frac{\partial E}{\partial R} = W"
    )

    st.markdown(
        "Shifting a parameter down and up by $\\delta$ therefore produces bars of "
        "width:"
    )
    st.latex(
        r"\text{width}_W = 2\,\delta\,(R + 1) \qquad \text{width}_R = 2\,\delta\,W"
    )

    st.markdown(
        """
These are also the slopes drawn on the line plots, which is why both are
straight lines.

The ranking is the striking part — and it is the **opposite** of what the
elasticity view suggests:

- The win-rate panel orders systems purely by $R$. A high-RR system multiplies
  every percentage point of win-rate error by a larger factor, so it loses the
  most edge from the same slip.
- The RR panel orders systems purely by $W$. A high-win-rate system takes its
  payoff more often, so a shrinking average win costs it more.

Neither ranking depends on the system's expectancy at all — only on the *other*
parameter.
"""
    )

if systems.empty:
    st.info("Enter at least one system to see its sensitivity.")
else:
    abs_wr, abs_rr, abs_pick = st.columns([1, 1, 2], vertical_alignment="bottom")
    wr_shift = abs_wr.number_input(
        "Win rate shift (pp)", min_value=0.5, max_value=25.0, value=5.0, step=0.5
    )
    rr_shift = abs_rr.number_input(
        "RR shift (R)", min_value=0.05, max_value=3.0, value=0.1, step=0.05
    )
    with abs_pick:
        abs_included = include_picker(systems["System"], "absolute_include")

    picked = systems[systems["System"].isin(abs_included)]

    if picked.empty:
        st.info("Select at least one system.")
    else:
        abs_colors = system_colors(systems["System"])

        def absolute_bars(parameter: str, delta: float) -> list:
            is_win_rate = parameter == "win_rate"
            rows = []
            for name, rr, wr, base in zip(
                picked["System"],
                picked["RR"],
                picked["Win rate (%)"],
                picked["Expectancy (R)"],
                strict=True,
            ):
                low, high = absolute_sensitivity_range(wr / 100, rr, parameter, delta)
                nominal = wr / 100 if is_win_rate else rr
                rows.append(
                    (str(name), low, high, base, f"{delta / nominal * 100:.3g}%")
                )
            return rows

        abs_shared = dict(
            colors=abs_colors,
            x_title="Expectancy (R per trade)",
            delta_places=3,
            delta_unit="R",
        )

        st.plotly_chart(
            build_tornado_pair(
                absolute_bars("win_rate", wr_shift / 100),
                absolute_bars("rr", rr_shift),
                left_title=f"Win rate ±{wr_shift:g} pp",
                right_title=f"RR ±{rr_shift:g}R",
                **abs_shared,
            ),
            width="stretch",
            config=export_config("absolute_sensitivity_tornado"),
        )

        st.caption(
            "The same shift is applied to every system, so bar length is directly "
            "comparable. Win rate bars all have width "
            f"2 × {wr_shift:g}pp × (R+1), so higher-RR systems react more; RR bars "
            f"all have width 2 × {rr_shift:g}R × W, so higher-win-rate systems react "
            "more."
        )

        fig_lines = make_subplots(
            rows=1,
            cols=2,
            horizontal_spacing=0.10,
            subplot_titles=("Expectancy vs win rate", "Expectancy vs reward-to-risk"),
        )

        def slope_label(curve, x_column, text, color, frac):
            """Annotate a line where it is inside the visible y range."""
            visible = curve[curve["expectancy"].between(*LINE_Y_RANGE)]
            if visible.empty:
                return None
            index = min(int(len(visible) * frac), len(visible) - 1)
            point = visible.iloc[index]
            return dict(
                x=point[x_column],
                y=point["expectancy"],
                text=text,
                showarrow=False,
                yshift=14,
                font=dict(size=11, color=color),
                bgcolor="rgba(255,255,255,0.75)",
                borderpad=2,
            )

        for i, (name, rr, wr, base) in enumerate(
            zip(
                picked["System"],
                picked["RR"],
                picked["Win rate (%)"],
                picked["Expectancy (R)"],
                strict=True,
            )
        ):
            spread = 0.8 - 0.15 * i
            curve_w = expectancy_vs_win_rate(rr)
            fig_lines.add_trace(
                go.Scatter(
                    x=curve_w["win_rate"] * 100,
                    y=curve_w["expectancy"],
                    mode="lines",
                    name=str(name),
                    legendgroup=str(name),
                    line=dict(width=2.5, color=abs_colors[name]),
                    hovertemplate=f"{name}<br>W %{{x:.1f}}% → %{{y:+.3f}}R"
                    "<extra></extra>",
                ),
                row=1,
                col=1,
            )
            curve_w = curve_w.assign(win_rate_pct=curve_w["win_rate"] * 100)
            note = slope_label(
                curve_w,
                "win_rate_pct",
                f"{(rr + 1) / 100:.3f} R/pp",
                abs_colors[name],
                spread,
            )
            if note:
                fig_lines.add_annotation(**note, row=1, col=1)

            curve_r = expectancy_vs_rr(wr / 100, rr_min=0.0, rr_max=RR_MAX)
            fig_lines.add_trace(
                go.Scatter(
                    x=curve_r["rr"],
                    y=curve_r["expectancy"],
                    mode="lines",
                    name=str(name),
                    legendgroup=str(name),
                    showlegend=False,
                    line=dict(width=2.5, color=abs_colors[name]),
                    hovertemplate=f"{name}<br>RR %{{x:.2f}} → %{{y:+.3f}}R"
                    "<extra></extra>",
                ),
                row=1,
                col=2,
            )
            note = slope_label(
                curve_r, "rr", f"{wr / 100:.2f} R/R", abs_colors[name], spread
            )
            if note:
                fig_lines.add_annotation(**note, row=1, col=2)

            for col, x_now in ((1, wr), (2, rr)):
                fig_lines.add_trace(
                    go.Scatter(
                        x=[x_now],
                        y=[base],
                        mode="markers",
                        marker=dict(
                            size=11,
                            color=abs_colors[name],
                            line=dict(width=1.5, color="white"),
                        ),
                        showlegend=False,
                        hovertemplate=f"{name} nominal<br>%{{x:.2f}} → %{{y:+.3f}}R"
                        "<extra></extra>",
                    ),
                    row=1,
                    col=col,
                )

        fig_lines.add_hline(y=0, line_width=2, line_color=SYSTEM_COLOR)
        fig_lines.update_layout(
            height=460,
            margin=dict(t=90, r=30, b=50, l=60),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        )
        fig_lines.update_xaxes(
            title="Win rate (%)",
            ticksuffix="%",
            showgrid=True,
            dtick=10,
            gridcolor="rgba(128,128,128,0.25)",
            griddash="dot",
            row=1,
            col=1,
        )
        fig_lines.update_xaxes(
            title="Reward-to-risk (R)",
            showgrid=True,
            dtick=1,
            gridcolor="rgba(128,128,128,0.25)",
            griddash="dot",
            row=1,
            col=2,
        )
        for col in (1, 2):
            fig_lines.update_yaxes(
                title="Expectancy (R per trade)",
                range=list(LINE_Y_RANGE),
                dtick=0.25,
                gridcolor="rgba(128,128,128,0.25)",
                griddash="dot",
                zeroline=False,
                row=1,
                col=col,
            )
        st.plotly_chart(
            fig_lines,
            width="stretch",
            config=export_config("expectancy_vs_parameters"),
        )

        st.caption(
            "Each line varies one parameter while the other stays at that system's "
            "value; the dot is the nominal value as entered. **The slope is the "
            "sensitivity** — steeper means a given error costs more — and the "
            "crossing of the red line is the break-even point."
        )


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

if show_isobars:
    for level, label_wr in zip(ISO_LEVELS, ISO_LABEL_WIN_RATES, strict=True):
        iso = iso_expectancy_curve(level, rr_min=RR_MIN, rr_max=X_HI)
        if iso.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=iso["rr"],
                y=iso["win_rate"] * 100,
                mode="lines",
                line=dict(width=1, color=ISO_COLOR, dash="dot"),
                hovertemplate=(
                    f"E = {level:.1f}R<br>RR %{{x:.2f}} → %{{y:.1f}}%<extra></extra>"
                ),
            )
        )
        label_rr = rr_for_iso_win_rate(level, label_wr)
        if RR_MIN <= label_rr <= X_HI:
            fig.add_annotation(
                x=label_rr,
                y=label_wr * 100,
                text=f"{level:.1f}R",
                showarrow=False,
                font=dict(size=11, color=ISO_COLOR),
                bgcolor="rgba(255,255,255,0.75)",
                borderpad=2,
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
    st.plotly_chart(
        fig, width="stretch", config=export_config("breakeven_win_rate")
    )

st.divider()

st.subheader("Conclusions")

st.markdown(
    "Expectancy tells you *whether* a system works. The sections above tell you "
    "*how much you can trust that answer* — and the two are far less related "
    "than they look."
)

st.markdown(
    """
- **Expectancy is per trade, not per year.** A system with half the expectancy
  but three times the trade frequency earns more. Frequency is not modelled here.
- **Equal expectancy does not mean equal quality.** Two systems can share the
  same $E$ and behave completely differently under a small estimation error.
  That is what the robustness sections are for.
- **Win rate is always the more fragile input.** For any profitable system the
  ratio of the two elasticities is $1 + 1/R$, which is greater than 1 — so a
  given *percentage* error in $W$ always costs more than the same error in $R$.
  The gap is widest at low RR.
- **A thin edge is not slightly fragile, it is extremely fragile.** Relative
  sensitivity to win rate is $(E+1)/E$, which grows without bound as $E$
  approaches zero. Demand a buffer, not merely a positive number.
- **Costs are neutral.** A fixed cost of $c$ R per trade reduces every system's
  expectancy by exactly $c$, regardless of its RR, since
  $W(R - c) - (1 - W)(1 + c) = E - c$.
- **Defend the win rate.** It is the binding constraint for every system, and it
  is the input that degrades in live trading through slippage, hesitation and
  missed entries. RR is set by your exit rules and is far more controllable.
"""
    )
