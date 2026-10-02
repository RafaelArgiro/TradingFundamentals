"""Position sizing: turning an edge measured in R into account growth.

The expectancy and variance work is all per-trade and expressed in R. Here R
itself becomes the decision variable: how much of the account to put behind each
trade, and what that choice does to growth and drawdown.
"""

import numpy as np
import pandas as pd

from tfcore.expectancy import ExpectancyInputs, expectancy


def kelly_fraction(inputs: ExpectancyInputs) -> float:
    """Fraction of equity to risk per trade that maximises long-run growth.

    Works out to `E / R`: the edge divided by the payoff. A system with no edge
    gets zero, and a losing system gets a negative number.
    """
    if inputs.avg_win <= 0:
        raise ValueError("avg_win must be positive")
    return expectancy(inputs) / inputs.avg_win


def log_growth_rate(inputs: ExpectancyInputs, fraction):
    """Expected log growth per trade when risking `fraction` of equity.

    A win multiplies equity by `1 + fR`, a loss by `1 - f`. Averaging the
    logarithm of those multipliers gives the compound growth rate.
    """
    values = np.asarray(fraction, dtype=float)
    if np.any(values < 0) or np.any(values >= 1):
        raise ValueError("fraction must be in [0, 1)")

    growth = inputs.win_rate * np.log1p(values * inputs.avg_win) + (
        1 - inputs.win_rate
    ) * np.log1p(-values * inputs.avg_loss)
    return float(growth) if np.isscalar(fraction) else growth


def growth_curve(
    inputs: ExpectancyInputs, fraction_max: float = 0.95, n_points: int = 300
) -> pd.DataFrame:
    """Compound growth rate across a range of risk fractions.

    Columns: `fraction`, `growth`.
    """
    if not 0 < fraction_max < 1:
        raise ValueError("fraction_max must be in (0, 1)")

    fractions = np.linspace(0.0, fraction_max, n_points)
    return pd.DataFrame(
        {"fraction": fractions, "growth": log_growth_rate(inputs, fractions)}
    )


def zero_growth_fraction(inputs: ExpectancyInputs, tolerance: float = 1e-6) -> float:
    """The risk fraction above which compounding destroys capital.

    Growth is zero at `f = 0`, rises to a peak at the Kelly fraction, then falls
    back through zero. This finds that second crossing by bisection.
    """
    peak = kelly_fraction(inputs)
    if peak <= 0:
        raise ValueError("a system without an edge has no positive growth range")

    low, high = peak, 1.0 - tolerance
    while high - low > tolerance:
        middle = (low + high) / 2
        if log_growth_rate(inputs, middle) > 0:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def compound_equity(
    results: np.ndarray, fraction: float, start: float = 1.0
) -> np.ndarray:
    """Equity path when risking a fixed *percentage* of current equity.

    `results` are per-trade outcomes in R. Each trade multiplies equity by
    `1 + fraction * result`, so the stake shrinks after losses and grows after
    wins.
    """
    if not 0 <= fraction < 1:
        raise ValueError("fraction must be in [0, 1)")
    return start * np.cumprod(1 + fraction * np.asarray(results, dtype=float), axis=0)


def fixed_equity(
    results: np.ndarray, risk_per_trade: float, start: float = 1.0
) -> np.ndarray:
    """Equity path when risking a fixed *amount* per trade.

    The stake never changes, so equity moves in a straight line with the
    cumulative R total.
    """
    if risk_per_trade <= 0:
        raise ValueError("risk_per_trade must be positive")
    return start + risk_per_trade * np.cumsum(np.asarray(results, dtype=float), axis=0)


def max_relative_drawdowns(equity: np.ndarray) -> np.ndarray:
    """Deepest peak-to-trough fall of each column, as a fraction of the peak."""
    values = np.asarray(equity, dtype=float)
    peaks = np.maximum.accumulate(values, axis=0)
    return ((peaks - values) / peaks).max(axis=0)


def volatility_drag(inputs: ExpectancyInputs, fraction: float) -> float:
    """Gap between the arithmetic return per trade and the compound growth rate.

    Compounding earns the geometric mean, which always sits below the arithmetic
    mean. The shortfall is what large positions quietly cost you.
    """
    arithmetic = fraction * expectancy(inputs)
    return float(np.log1p(arithmetic) - log_growth_rate(inputs, fraction))
