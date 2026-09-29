"""Monte Carlo style simulation of trade sequences from a system's statistics."""

import numpy as np
import pandas as pd

from tfcore.expectancy import ExpectancyInputs


def simulate_trades(
    inputs: ExpectancyInputs, n_trades: int, seed: int | None = None
) -> np.ndarray:
    """Generate `n_trades` outcomes in R, each a win or a loss.

    A fixed `seed` makes the sequence reproducible, so the chart does not
    reshuffle every time an unrelated control changes.
    """
    if n_trades < 1:
        raise ValueError(f"n_trades must be at least 1, got {n_trades}")

    rng = np.random.default_rng(seed)
    wins = rng.random(n_trades) < inputs.win_rate
    return np.where(wins, inputs.avg_win, -inputs.avg_loss)


def simulate_equity_curve(
    inputs: ExpectancyInputs, n_trades: int, seed: int | None = None
) -> pd.DataFrame:
    """One simulated run, as a table of trade number, result and running total.

    Columns: `trade`, `result_r`, `equity_r`.
    """
    results = simulate_trades(inputs, n_trades, seed)
    return pd.DataFrame(
        {
            "trade": np.arange(1, n_trades + 1),
            "result_r": results,
            "equity_r": results.cumsum(),
        }
    )


def simulate_many_curves(
    inputs: ExpectancyInputs, n_trades: int, n_runs: int, seed: int | None = None
) -> pd.DataFrame:
    """`n_runs` independent equity curves, to show the spread of outcomes.

    A single curve is one possible future and can mislead badly. Returns a
    wide table: one column per run, one row per trade.
    """
    if n_runs < 1:
        raise ValueError(f"n_runs must be at least 1, got {n_runs}")

    rng = np.random.default_rng(seed)
    wins = rng.random((n_trades, n_runs)) < inputs.win_rate
    results = np.where(wins, inputs.avg_win, -inputs.avg_loss)
    return pd.DataFrame(
        results.cumsum(axis=0),
        index=pd.RangeIndex(1, n_trades + 1, name="trade"),
        columns=[f"run_{i + 1}" for i in range(n_runs)],
    )


def max_drawdown(equity: pd.Series | np.ndarray) -> float:
    """Largest peak-to-trough fall in an equity curve, in R.

    Returned as a positive number. This is the pain a trader actually has to
    sit through, and it is what breaks people long before the maths fails.
    """
    equity = np.asarray(equity, dtype=float)
    if equity.size == 0:
        return 0.0
    running_peak = np.maximum.accumulate(equity)
    return float(np.max(running_peak - equity))
