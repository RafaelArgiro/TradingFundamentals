import numpy as np
import pandas as pd
import pytest

from tfcore.expectancy import ExpectancyInputs
from tfcore.simulation import (
    equity_percentiles,
    expected_longest_losing_streak,
    final_outcomes,
    longest_losing_streaks,
    longest_underwater,
    max_drawdowns,
    simulate_many_curves,
    trade_results,
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


def test_trade_results_reconstruct_the_curve():
    curves = simulate_many_curves(SYSTEM, n_trades=40, n_runs=20, seed=10)
    np.testing.assert_allclose(trade_results(curves).cumsum(), curves)


def test_trade_results_only_contain_the_two_outcomes():
    curves = simulate_many_curves(SYSTEM, n_trades=40, n_runs=20, seed=11)
    assert set(np.unique(trade_results(curves).to_numpy())) <= {2.0, -1.0}


def test_max_drawdown_on_a_known_curve():
    curves = pd.DataFrame({"run_1": [1.0, 5.0, 1.0, 6.0, 4.0]})
    assert max_drawdowns(curves).iloc[0] == pytest.approx(4.0)


def test_max_drawdown_is_zero_for_a_rising_curve():
    curves = pd.DataFrame({"run_1": [1.0, 2.0, 3.0, 4.0]})
    assert max_drawdowns(curves).iloc[0] == pytest.approx(0.0)


def test_max_drawdown_is_never_negative():
    curves = simulate_many_curves(SYSTEM, n_trades=100, n_runs=100, seed=12)
    assert (max_drawdowns(curves) >= 0).all()


def test_longest_losing_streak_on_a_known_curve():
    # Results of -1, -1, -1, +2, -1 give a longest losing run of three.
    curves = pd.DataFrame({"run_1": [-1.0, -2.0, -3.0, -1.0, -2.0]})
    assert longest_losing_streaks(curves).iloc[0] == pytest.approx(3.0)


def test_losing_streak_is_bounded_by_trade_count():
    curves = simulate_many_curves(SYSTEM, n_trades=60, n_runs=100, seed=13)
    assert (longest_losing_streaks(curves) <= 60).all()


def test_simulated_streak_matches_the_analytical_estimate():
    """The closed form should land near the simulated mean."""
    curves = simulate_many_curves(SYSTEM, n_trades=500, n_runs=400, seed=14)
    simulated_mean = longest_losing_streaks(curves).mean()
    estimate = expected_longest_losing_streak(SYSTEM.win_rate, 500)
    assert estimate == pytest.approx(simulated_mean, rel=0.2)


def test_lower_win_rate_means_longer_streaks():
    assert expected_longest_losing_streak(0.22, 200) > expected_longest_losing_streak(
        0.70, 200
    )


def test_underwater_is_zero_for_a_monotonic_curve():
    curves = pd.DataFrame({"run_1": [1.0, 2.0, 3.0]})
    assert longest_underwater(curves).iloc[0] == pytest.approx(0.0)


def test_underwater_counts_trades_below_the_peak():
    curves = pd.DataFrame({"run_1": [1.0, 5.0, 4.0, 3.0, 6.0]})
    assert longest_underwater(curves).iloc[0] == pytest.approx(2.0)


def test_expected_streak_rejects_impossible_win_rate():
    with pytest.raises(ValueError, match="win_rate"):
        expected_longest_losing_streak(1.0, 100)
