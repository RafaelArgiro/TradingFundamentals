"""Monte Carlo style simulation of trade sequences from a system's statistics."""

from collections.abc import Iterable

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


def equity_percentiles(
    curves: pd.DataFrame, percentiles: Iterable[float] = (10, 50, 90)
) -> pd.DataFrame:
    """Collapse many equity curves into one band per percentile.

    Takes the wide table from `simulate_many_curves` and returns a column named
    `p10`, `p50`, ... for each requested percentile, indexed by trade number.
    """
    levels = list(percentiles)
    if not levels:
        raise ValueError("at least one percentile is required")
    if any(not 0 <= p <= 100 for p in levels):
        raise ValueError("percentiles must lie between 0 and 100")

    values = np.percentile(curves.to_numpy(), levels, axis=1)
    return pd.DataFrame(
        values.T,
        index=curves.index,
        columns=[f"p{p:g}" for p in levels],
    )


def final_outcomes(curves: pd.DataFrame) -> pd.Series:
    """The closing equity of every simulated run."""
    return curves.iloc[-1]


def trade_results(curves: pd.DataFrame) -> pd.DataFrame:
    """Recover the per-trade results that produced each cumulative curve."""
    results = curves.diff()
    results.iloc[0] = curves.iloc[0]
    return results


def max_drawdowns(curves: pd.DataFrame) -> pd.Series:
    """Largest peak-to-trough fall within each run, in R.

    At every trade the drawdown is `running peak - current equity`; the maximum
    of that over a run is how far the account fell from its best point.
    """
    values = curves.to_numpy(dtype=float)
    peaks = np.maximum.accumulate(values, axis=0)
    return pd.Series((peaks - values).max(axis=0), index=curves.columns)


def _longest_run(flags: np.ndarray) -> np.ndarray:
    """Longest streak of True down each column of a boolean array."""
    running = np.zeros(flags.shape[1])
    longest = np.zeros(flags.shape[1])
    for row in flags:
        running = (running + 1) * row
        longest = np.maximum(longest, running)
    return longest


def longest_losing_streaks(curves: pd.DataFrame) -> pd.Series:
    """Most consecutive losing trades within each run."""
    losses = trade_results(curves).to_numpy(dtype=float) < 0
    return pd.Series(_longest_run(losses), index=curves.columns)


def longest_underwater(curves: pd.DataFrame) -> pd.Series:
    """Most consecutive trades spent below a previous equity peak.

    Counts the wait, in trades, before the account gets back to its high-water
    mark -- a run can be shallow and still take a long time to recover.
    """
    values = curves.to_numpy(dtype=float)
    peaks = np.maximum.accumulate(values, axis=0)
    return pd.Series(_longest_run(values < peaks), index=curves.columns)


def expected_longest_losing_streak(win_rate: float, n_trades: int) -> float:
    """Analytical estimate of the longest losing run, for cross-checking.

    Roughly `ln(n) / -ln(1 - W)`: the streak length whose expected number of
    occurrences in `n_trades` is about one.
    """
    if not 0 < win_rate < 1:
        raise ValueError(f"win_rate must be strictly between 0 and 1, got {win_rate}")
    if n_trades < 1:
        raise ValueError(f"n_trades must be at least 1, got {n_trades}")
    return float(np.log(n_trades) / -np.log(1 - win_rate))
