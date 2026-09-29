"""Trade expectancy: the average result per trade of a trading system.

Results are expressed in **R**, where 1R is the amount risked on a single
trade. Working in R rather than currency makes systems comparable regardless of
account size.
"""

from dataclasses import dataclass


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
