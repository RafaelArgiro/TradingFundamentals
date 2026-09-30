import numpy as np
import pandas as pd
import pytest

from tfcore.expectancy import ExpectancyInputs
from tfcore.simulation import (
    equity_percentiles,
    final_outcomes,
    simulate_many_curves,
)

SYSTEM = ExpectancyInputs(win_rate=0.45, avg_win=2.0, avg_loss=1.0)


def test_percentile_columns_are_named_after_their_level():
    curves = simulate_many_curves(SYSTEM, n_trades=20, n_runs=50, seed=1)
    bands = equity_percentiles(curves, (10, 50, 90))
    assert list(bands.columns) == ["p10", "p50", "p90"]


def test_percentiles_keep_the_trade_index():
    curves = simulate_many_curves(SYSTEM, n_trades=30, n_runs=40, seed=2)
    bands = equity_percentiles(curves)
    assert bands.index.equals(curves.index)


def test_percentile_bands_are_ordered():
    curves = simulate_many_curves(SYSTEM, n_trades=50, n_runs=200, seed=3)
    bands = equity_percentiles(curves, (10, 25, 50, 75, 90))
    assert (bands["p10"] <= bands["p25"]).all()
    assert (bands["p25"] <= bands["p50"]).all()
    assert (bands["p50"] <= bands["p75"]).all()
    assert (bands["p75"] <= bands["p90"]).all()


def test_band_widens_with_more_trades():
    """Dispersion grows with the square root of trade count."""
    curves = simulate_many_curves(SYSTEM, n_trades=200, n_runs=500, seed=4)
    bands = equity_percentiles(curves, (10, 90))
    width = bands["p90"] - bands["p10"]
    assert width.iloc[-1] > width.iloc[0]


def test_median_tracks_expectancy():
    curves = simulate_many_curves(SYSTEM, n_trades=300, n_runs=400, seed=5)
    bands = equity_percentiles(curves, (50,))
    assert bands["p50"].iloc[-1] == pytest.approx(300 * 0.35, rel=0.15)


def test_final_outcomes_is_the_last_row():
    curves = simulate_many_curves(SYSTEM, n_trades=25, n_runs=10, seed=6)
    np.testing.assert_array_equal(final_outcomes(curves), curves.iloc[-1])


def test_rejects_empty_percentiles():
    curves = simulate_many_curves(SYSTEM, n_trades=5, n_runs=5, seed=7)
    with pytest.raises(ValueError, match="percentile"):
        equity_percentiles(curves, ())


def test_rejects_out_of_range_percentiles():
    curves = simulate_many_curves(SYSTEM, n_trades=5, n_runs=5, seed=8)
    with pytest.raises(ValueError, match="between 0 and 100"):
        equity_percentiles(curves, (10, 150))


def test_single_run_collapses_to_that_run():
    curves = simulate_many_curves(SYSTEM, n_trades=15, n_runs=1, seed=9)
    bands = equity_percentiles(curves, (10, 50, 90))
    for column in bands.columns:
        pd.testing.assert_series_equal(
            bands[column], curves.iloc[:, 0], check_names=False
        )
