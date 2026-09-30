"""Trade expectancy: the average result per trade of a trading system.

Results are expressed in **R**, where 1R is the amount risked on a single
trade. Working in R rather than currency makes systems comparable regardless of
account size.
"""

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ExpectancyInputs:
    """The three numbers that characterise a trading system.

    Args:
        win_rate: Fraction of trades that are winners, between 0 and 1.
        avg_win: Average gain on a winning trade, in R. Positive.
        avg_loss: Average loss on a losing trade, in R. Given as a positive
            number -- the sign is applied by the formulas.
    """

    win_rate: float
    avg_win: float
    avg_loss: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.win_rate <= 1.0:
            raise ValueError(f"win_rate must be between 0 and 1, got {self.win_rate}")
        if self.avg_win < 0:
            raise ValueError(f"avg_win must be positive, got {self.avg_win}")
        if self.avg_loss < 0:
            raise ValueError(f"avg_loss must be positive, got {self.avg_loss}")


def expectancy(inputs: ExpectancyInputs) -> float:
    """Average R gained per trade over many trades.

    Positive means the system makes money in the long run; negative means it
    loses. This is the single most important number about a trading system.
    """
    return inputs.win_rate * inputs.avg_win - (1 - inputs.win_rate) * inputs.avg_loss


def breakeven_win_rate(avg_win: float, avg_loss: float) -> float:
    """The win rate at which expectancy is exactly zero.

    Win more often than this and the system is profitable; less often and it
    is not. Useful as a sanity target: a 2:1 reward-to-risk system only needs
    to be right 33% of the time.
    """
    total = avg_win + avg_loss
    if total == 0:
        raise ValueError("avg_win and avg_loss cannot both be zero")
    return avg_loss / total


def reward_to_risk(inputs: ExpectancyInputs) -> float:
    """How many R a typical win returns per R risked on a typical loss."""
    if inputs.avg_loss == 0:
        raise ValueError("avg_loss cannot be zero")
    return inputs.avg_win / inputs.avg_loss


def required_win_rate(rr: float) -> float:
    """Win rate needed to break even at a given reward-to-risk ratio.

    `rr` is reward per 1R risked, so rr=2 means a 2R win against a 1R loss.
    Equivalent to `breakeven_win_rate(rr, 1.0)`.
    """
    if rr <= 0:
        raise ValueError(f"rr must be positive, got {rr}")
    return 1.0 / (1.0 + rr)


def expectancy_from_rr(win_rate: float, rr: float) -> float:
    """Expectancy in R for a system described by win rate and reward-to-risk.

    Assumes the average loss is exactly 1R, which is what makes `rr` and the
    break-even curve directly comparable.
    """
    return expectancy(ExpectancyInputs(win_rate=win_rate, avg_win=rr, avg_loss=1.0))


def breakeven_curve(
    rr_min: float = 0.5, rr_max: float = 10.0, n_points: int = 400
) -> pd.DataFrame:
    """Required win rate across a range of reward-to-risk ratios.

    Columns: `rr`, `win_rate` (a fraction between 0 and 1).
    """
    if rr_min <= 0:
        raise ValueError(f"rr_min must be positive, got {rr_min}")
    if rr_max <= rr_min:
        raise ValueError(f"rr_max must exceed rr_min, got {rr_max} <= {rr_min}")
    if n_points < 2:
        raise ValueError(f"n_points must be at least 2, got {n_points}")

    rr = np.linspace(rr_min, rr_max, n_points)
    return pd.DataFrame({"rr": rr, "win_rate": 1.0 / (1.0 + rr)})


def breakeven_points(rr_values: Iterable[float]) -> pd.DataFrame:
    """Required win rate at specific reward-to-risk ratios, for labelling."""
    rr = np.asarray(list(rr_values), dtype=float)
    if np.any(rr <= 0):
        raise ValueError("all rr values must be positive")
    return pd.DataFrame({"rr": rr, "win_rate": 1.0 / (1.0 + rr)})


def iso_expectancy_curve(
    level: float, rr_min: float = 0.2, rr_max: float = 10.0, n_points: int = 300
) -> pd.DataFrame:
    """Win rate needed to earn exactly `level` R per trade, across a range of RR.

    The break-even curve is the special case `level = 0`. Points requiring an
    impossible win rate above 100% are dropped.

    Columns: `rr`, `win_rate`.
    """
    if level < 0:
        raise ValueError(f"level must be non-negative, got {level}")
    if not 0 < rr_min < rr_max:
        raise ValueError("rr bounds must satisfy 0 < min < max")

    rr = np.linspace(rr_min, rr_max, n_points)
    win_rate = (1.0 + level) / (1.0 + rr)
    curve = pd.DataFrame({"rr": rr, "win_rate": win_rate})
    return curve[curve["win_rate"] <= 1.0].reset_index(drop=True)


def rr_for_iso_win_rate(level: float, win_rate: float) -> float:
    """The RR at which `level` R of expectancy needs exactly `win_rate`."""
    if not 0 < win_rate <= 1:
        raise ValueError(f"win_rate must be in (0, 1], got {win_rate}")
    return (1.0 + level) / win_rate - 1.0


def expectancy_vs_win_rate(
    rr: float,
    win_rate_min: float = 0.0,
    win_rate_max: float = 1.0,
    n_points: int = 200,
) -> pd.DataFrame:
    """Expectancy across a range of win rates at fixed reward-to-risk.

    Columns: `win_rate`, `expectancy`.
    """
    if rr < 0:
        raise ValueError(f"rr must be positive, got {rr}")
    if not 0 <= win_rate_min < win_rate_max <= 1:
        raise ValueError("win_rate bounds must satisfy 0 <= min < max <= 1")

    win_rate = np.linspace(win_rate_min, win_rate_max, n_points)
    return pd.DataFrame(
        {"win_rate": win_rate, "expectancy": win_rate * (rr + 1) - 1}
    )


def expectancy_vs_rr(
    win_rate: float,
    rr_min: float = 0.0,
    rr_max: float = 10.0,
    n_points: int = 200,
) -> pd.DataFrame:
    """Expectancy across a range of reward-to-risk ratios at fixed win rate.

    Columns: `rr`, `expectancy`.
    """
    if not 0 <= win_rate <= 1:
        raise ValueError(f"win_rate must be between 0 and 1, got {win_rate}")
    if not 0 <= rr_min < rr_max:
        raise ValueError("rr bounds must satisfy 0 <= min < max")

    rr = np.linspace(rr_min, rr_max, n_points)
    return pd.DataFrame({"rr": rr, "expectancy": win_rate * (rr + 1) - 1})
