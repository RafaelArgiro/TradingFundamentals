import numpy as np
import pytest

from tfcore.expectancy import ExpectancyInputs, expectancy
from tfcore.simulation import (
    max_drawdown,
    simulate_equity_curve,
    simulate_many_curves,
    simulate_trades,
)

SYSTEM = ExpectancyInputs(win_rate=0.45, avg_win=2.0, avg_loss=1.0)


def test_simulate_trades_length_and_values():
    trades = simulate_trades(SYSTEM, n_trades=50, seed=1)
    assert len(trades) == 50
    assert set(np.unique(trades)) <= {2.0, -1.0}


def test_same_seed_is_reproducible():
    a = simulate_trades(SYSTEM, n_trades=100, seed=7)
    b = simulate_trades(SYSTEM, n_trades=100, seed=7)
    np.testing.assert_array_equal(a, b)


def test_different_seeds_differ():
    a = simulate_trades(SYSTEM, n_trades=100, seed=1)
    b = simulate_trades(SYSTEM, n_trades=100, seed=2)
    assert not np.array_equal(a, b)


def test_mean_converges_on_expectancy():
    """Over many trades the average result should approach the expectancy."""
    trades = simulate_trades(SYSTEM, n_trades=200_000, seed=42)
    assert trades.mean() == pytest.approx(expectancy(SYSTEM), abs=0.01)


def test_equity_curve_columns_and_running_total():
    df = simulate_equity_curve(SYSTEM, n_trades=10, seed=3)
    assert list(df.columns) == ["trade", "result_r", "equity_r"]
    assert df["trade"].tolist() == list(range(1, 11))
    np.testing.assert_allclose(df["equity_r"], df["result_r"].cumsum())


def test_many_curves_shape():
    df = simulate_many_curves(SYSTEM, n_trades=30, n_runs=5, seed=11)
    assert df.shape == (30, 5)
    assert df.index.name == "trade"


@pytest.mark.parametrize(
    ("equity", "expected"),
    [
        ([1, 2, 3, 4], 0.0),
        ([0, 5, 1, 6], 4.0),
        ([0, -1, -2, -3], 3.0),
        ([], 0.0),
    ],
)
def test_max_drawdown(equity, expected):
    assert max_drawdown(np.array(equity, dtype=float)) == pytest.approx(expected)


def test_rejects_zero_trades():
    with pytest.raises(ValueError, match="n_trades"):
        simulate_trades(SYSTEM, n_trades=0)
