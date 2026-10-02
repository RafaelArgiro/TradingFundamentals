"""How many trades it takes before a measured win rate means anything.

Everything here rests on one fact: a sequence of trades is a sequence of
Bernoulli trials, so the number of winners follows a binomial distribution and
the measured win rate carries a known sampling error.
"""

import numpy as np
import pandas as pd

from tfcore.expectancy import expectancy_from_rr

# Two-sided normal critical values for the usual confidence levels.
Z_SCORES = {80: 1.282, 90: 1.645, 95: 1.960, 99: 2.576}


def z_for(confidence: int) -> float:
    """Critical value for a two-sided interval at `confidence` percent."""
    if confidence not in Z_SCORES:
        raise ValueError(f"confidence must be one of {sorted(Z_SCORES)}")
    return Z_SCORES[confidence]


def win_rate_standard_error(win_rate: float, n_trades: int) -> float:
    """Standard error of a win rate measured over `n_trades`.

    Var(k) = n W (1 - W) for the win count, so the proportion k/n has
    variance W(1 - W)/n.
    """
    if not 0 <= win_rate <= 1:
        raise ValueError(f"win_rate must be between 0 and 1, got {win_rate}")
    if n_trades < 1:
        raise ValueError(f"n_trades must be at least 1, got {n_trades}")
    return float(np.sqrt(win_rate * (1 - win_rate) / n_trades))


def expectancy_standard_error(win_rate: float, rr: float, n_trades: int) -> float:
    """Standard error of expectancy caused by win rate sampling error.

    E is linear in W with slope (R + 1), so the error scales by exactly that.
    Reward-to-risk is assumed known, which makes this an optimistic floor.
    """
    return (rr + 1) * win_rate_standard_error(win_rate, n_trades)


def trades_for_win_rate_margin(
    win_rate: float, margin: float, confidence: int = 95
) -> float:
    """Trades needed to pin the win rate down to +/- `margin` (a fraction)."""
    if not 0 < margin < 1:
        raise ValueError(f"margin must be between 0 and 1, got {margin}")
    z = z_for(confidence)
    return float(z**2 * win_rate * (1 - win_rate) / margin**2)


def trades_to_prove_edge(win_rate: float, rr: float, confidence: int = 95) -> float:
    """Trades needed before the measured edge is distinguishable from zero.

    Solves `E - z * SE(E) > 0` for the trade count.
    """
    edge = expectancy_from_rr(win_rate, rr)
    if edge <= 0:
        raise ValueError("a non-positive edge can never be proven positive")
    z = z_for(confidence)
    return float(z**2 * (rr + 1) ** 2 * win_rate * (1 - win_rate) / edge**2)


def edge_lower_bound(
    win_rate: float, rr: float, n_trades: int, confidence: int = 95
) -> float:
    """Worst-case expectancy still consistent with the data at `confidence`."""
    edge = expectancy_from_rr(win_rate, rr)
    return edge - z_for(confidence) * expectancy_standard_error(win_rate, rr, n_trades)


def edge_bound_curve(
    win_rate: float,
    rr: float,
    max_trades: int,
    confidence: int = 95,
    min_trades: int = 10,
    n_points: int = 250,
) -> pd.DataFrame:
    """Lower confidence bound on expectancy as the trade count grows.

    Columns: `trades`, `lower`. Where the curve crosses zero is the point at
    which the edge becomes statistically believable.
    """
    if max_trades <= min_trades:
        raise ValueError("max_trades must exceed min_trades")

    trades = np.unique(
        np.linspace(min_trades, max_trades, n_points).round().astype(int)
    )
    edge = expectancy_from_rr(win_rate, rr)
    spread = z_for(confidence) * (rr + 1) * np.sqrt(win_rate * (1 - win_rate) / trades)
    return pd.DataFrame({"trades": trades, "lower": edge - spread})


def normal_approximation_is_safe(win_rate: float, n_trades: int) -> bool:
    """Whether the usual rule of thumb for the normal approximation holds."""
    return min(n_trades * win_rate, n_trades * (1 - win_rate)) >= 10


def normal_curve(lo: float = -4.0, hi: float = 4.0, n_points: int = 400) -> pd.DataFrame:
    """Standard normal density, in units of standard deviations from the mean.

    Columns: `z`, `density`. Used to draw the confidence interval schematic.
    """
    if hi <= lo:
        raise ValueError("hi must exceed lo")
    z = np.linspace(lo, hi, n_points)
    return pd.DataFrame({"z": z, "density": np.exp(-0.5 * z**2) / np.sqrt(2 * np.pi)})
