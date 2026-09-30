"""How much room a system has before its edge disappears.

Tier 1 measures are distances to the break-even point in trader units; the
elasticity measures express the same thing as a percentage response.
"""

from typing import Literal

from tfcore.expectancy import expectancy_from_rr, required_win_rate

Parameter = Literal["win_rate", "rr"]


def critical_win_rate(rr: float) -> float:
    """Win rate at which expectancy hits zero, for a given reward-to-risk."""
    return required_win_rate(rr)


def critical_rr(win_rate: float) -> float:
    """Reward-to-risk at which expectancy hits zero, for a given win rate."""
    if not 0 < win_rate <= 1:
        raise ValueError(f"win_rate must be in (0, 1], got {win_rate}")
    return (1 - win_rate) / win_rate


def win_rate_buffer(win_rate: float, rr: float) -> float:
    """Percentage points the win rate can fall before breaking even."""
    return win_rate - critical_win_rate(rr)


def rr_buffer(win_rate: float, rr: float) -> float:
    """How much R the average win can shrink before breaking even."""
    return rr - critical_rr(win_rate)


def elasticity_win_rate(win_rate: float, rr: float) -> float:
    """Percent change in expectancy per 1% change in win rate."""
    edge = expectancy_from_rr(win_rate, rr)
    if edge == 0:
        raise ValueError("elasticity is undefined at break-even")
    return (edge + 1) / edge


def elasticity_rr(win_rate: float, rr: float) -> float:
    """Percent change in expectancy per 1% change in reward-to-risk."""
    edge = expectancy_from_rr(win_rate, rr)
    if edge == 0:
        raise ValueError("elasticity is undefined at break-even")
    return win_rate * rr / edge


def sensitivity_range(
    win_rate: float, rr: float, parameter: Parameter, pct: float
) -> tuple[float, float]:
    """Expectancy when `parameter` moves down and up by `pct` percent.

    Returns `(low, high)`. Win rate is capped at 100%, so a large upward
    deviation cannot produce an impossible system.
    """
    if not 0 < pct <= 100:
        raise ValueError(f"pct must be in (0, 100], got {pct}")

    lo_factor, hi_factor = 1 - pct / 100, 1 + pct / 100

    if parameter == "win_rate":
        lo = expectancy_from_rr(win_rate * lo_factor, rr)
        hi = expectancy_from_rr(min(win_rate * hi_factor, 1.0), rr)
    elif parameter == "rr":
        lo = expectancy_from_rr(win_rate, rr * lo_factor)
        hi = expectancy_from_rr(win_rate, rr * hi_factor)
    else:
        raise ValueError(f"unknown parameter: {parameter}")

    return lo, hi


def absolute_sensitivity_range(
    win_rate: float, rr: float, parameter: Parameter, delta: float
) -> tuple[float, float]:
    """Expectancy when `parameter` moves down and up by `delta` in its own units.

    `delta` is a fraction for win rate (0.05 = 5 percentage points) and R for
    reward-to-risk. Both parameters are clamped to their valid range.
    """
    if delta <= 0:
        raise ValueError(f"delta must be positive, got {delta}")

    if parameter == "win_rate":
        lo = expectancy_from_rr(max(win_rate - delta, 0.0), rr)
        hi = expectancy_from_rr(min(win_rate + delta, 1.0), rr)
    elif parameter == "rr":
        lo = expectancy_from_rr(win_rate, max(rr - delta, 0.0))
        hi = expectancy_from_rr(win_rate, rr + delta)
    else:
        raise ValueError(f"unknown parameter: {parameter}")

    return lo, hi
