import numpy as np
import pytest

from tfcore.expectancy import ExpectancyInputs
from tfcore.risk import (
    compound_equity,
    fixed_equity,
    growth_curve,
    kelly_fraction,
    log_growth_rate,
    max_relative_drawdowns,
    volatility_drag,
    zero_growth_fraction,
)

SYSTEM = ExpectancyInputs(win_rate=0.44, avg_win=2.0, avg_loss=1.0)


def test_kelly_matches_the_classic_form():
    """f* = W - (1 - W)/R is the textbook result for a two-outcome bet."""
    expected = SYSTEM.win_rate - (1 - SYSTEM.win_rate) / SYSTEM.avg_win
    assert kelly_fraction(SYSTEM) == pytest.approx(expected)


def test_kelly_equals_edge_over_payoff():
    assert kelly_fraction(SYSTEM) == pytest.approx(0.32 / 2.0)


def test_kelly_is_zero_at_breakeven():
    breakeven = ExpectancyInputs(win_rate=1 / 3, avg_win=2.0, avg_loss=1.0)
    assert kelly_fraction(breakeven) == pytest.approx(0.0, abs=1e-12)


def test_kelly_is_negative_for_a_losing_system():
    assert kelly_fraction(ExpectancyInputs(0.25, 2.0, 1.0)) < 0


def test_growth_is_zero_when_nothing_is_risked():
    assert log_growth_rate(SYSTEM, 0.0) == pytest.approx(0.0)


def test_growth_peaks_at_the_kelly_fraction():
    peak = kelly_fraction(SYSTEM)
    best = log_growth_rate(SYSTEM, peak)
    assert best > log_growth_rate(SYSTEM, peak * 0.5)
    assert best > log_growth_rate(SYSTEM, peak * 1.5)


def test_growth_curve_maximum_lands_on_kelly():
    curve = growth_curve(SYSTEM, fraction_max=0.6, n_points=2001)
    best = curve.loc[curve["growth"].idxmax(), "fraction"]
    assert best == pytest.approx(kelly_fraction(SYSTEM), abs=1e-3)


def test_zero_growth_is_above_kelly_and_loses_beyond():
    crossing = zero_growth_fraction(SYSTEM)
    assert crossing > kelly_fraction(SYSTEM)
    assert log_growth_rate(SYSTEM, crossing * 1.05) < 0


def test_zero_growth_rejects_a_system_without_an_edge():
    with pytest.raises(ValueError, match="no positive growth"):
        zero_growth_fraction(ExpectancyInputs(0.25, 2.0, 1.0))


def test_compound_equity_applies_the_multipliers():
    results = np.array([[2.0], [-1.0]])
    equity = compound_equity(results, fraction=0.1)
    assert equity[0, 0] == pytest.approx(1.2)
    assert equity[1, 0] == pytest.approx(1.2 * 0.9)


def test_compound_equity_never_reaches_zero():
    results = np.full((200, 1), -1.0)
    assert (compound_equity(results, fraction=0.5) > 0).all()


def test_fixed_equity_is_linear_in_the_r_total():
    results = np.array([[2.0], [-1.0], [2.0]])
    equity = fixed_equity(results, risk_per_trade=0.01)
    np.testing.assert_allclose(equity[:, 0], [1.02, 1.01, 1.03])


def test_fixed_sizing_can_wipe_out_but_percentage_cannot():
    losses = np.full((150, 1), -1.0)
    assert fixed_equity(losses, risk_per_trade=0.01).min() < 0
    assert compound_equity(losses, fraction=0.01).min() > 0


def test_relative_drawdown_on_a_known_path():
    equity = np.array([[1.0], [2.0], [1.0], [4.0]])
    assert max_relative_drawdowns(equity)[0] == pytest.approx(0.5)


def test_relative_drawdown_is_zero_for_a_rising_path():
    equity = np.array([[1.0], [1.5], [2.0]])
    assert max_relative_drawdowns(equity)[0] == pytest.approx(0.0)


def test_volatility_drag_is_positive_and_grows_with_size():
    assert volatility_drag(SYSTEM, 0.05) > 0
    assert volatility_drag(SYSTEM, 0.20) > volatility_drag(SYSTEM, 0.05)


def test_growth_rate_rejects_full_risk():
    with pytest.raises(ValueError, match="fraction"):
        log_growth_rate(SYSTEM, 1.0)
