"""How much room a system has before its edge disappears.

All Tier 1 measures: distances from the current parameters to the break-even
point, in the units a trader thinks in.
"""

from tfcore.expectancy import required_win_rate


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
