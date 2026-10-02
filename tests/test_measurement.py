import numpy as np
import pytest

from tfcore.expectancy import expectancy_from_rr
from tfcore.measurement import (
    edge_bound_curve,
    edge_lower_bound,
    expectancy_standard_error,
    normal_approximation_is_safe,
    normal_curve,
    trades_for_win_rate_margin,
    trades_to_prove_edge,
    win_rate_standard_error,
    z_for,
)


def test_standard_error_matches_binomial_formula():
    assert win_rate_standard_error(0.5, 100) == pytest.approx(0.05)


def test_standard_error_shrinks_with_the_square_root_of_n():
    """Four times the trades must halve the error."""
    small = win_rate_standard_error(0.45, 100)
    large = win_rate_standard_error(0.45, 400)
    assert large == pytest.approx(small / 2)


def test_standard_error_peaks_at_a_fifty_percent_win_rate():
    middle = win_rate_standard_error(0.50, 200)
    assert middle > win_rate_standard_error(0.22, 200)
    assert middle > win_rate_standard_error(0.70, 200)


def test_expectancy_error_scales_with_rr_plus_one():
    base = win_rate_standard_error(0.44, 300)
    assert expectancy_standard_error(0.44, 2.0, 300) == pytest.approx(3 * base)


def test_required_trades_invert_the_standard_error():
    """Running the required count back through the margin reproduces it."""
    needed = trades_for_win_rate_margin(0.44, 0.05, confidence=95)
    margin = z_for(95) * win_rate_standard_error(0.44, round(needed))
    assert margin == pytest.approx(0.05, rel=0.01)


def test_tighter_margin_needs_quadratically_more_trades():
    loose = trades_for_win_rate_margin(0.44, 0.05)
    tight = trades_for_win_rate_margin(0.44, 0.025)
    assert tight == pytest.approx(4 * loose)


def test_higher_confidence_needs_more_trades():
    assert trades_for_win_rate_margin(0.44, 0.05, 99) > trades_for_win_rate_margin(
        0.44, 0.05, 90
    )


@pytest.mark.parametrize(
    ("win_rate", "rr", "expected"),
    [(0.70, 0.88, 29), (0.44, 2.0, 83), (0.33, 3.0, 133), (0.22, 5.0, 232)],
)
def test_trades_to_prove_edge_for_the_reference_systems(win_rate, rr, expected):
    assert trades_to_prove_edge(win_rate, rr) == pytest.approx(expected, abs=1)


def test_low_win_rate_systems_need_far_more_evidence():
    assert trades_to_prove_edge(0.22, 5.0) > 7 * trades_to_prove_edge(0.70, 0.88)


def test_edge_is_exactly_marginal_at_the_required_trade_count():
    needed = trades_to_prove_edge(0.44, 2.0)
    assert edge_lower_bound(0.44, 2.0, round(needed)) == pytest.approx(0.0, abs=1e-3)


def test_lower_bound_rises_towards_the_true_edge():
    edge = expectancy_from_rr(0.44, 2.0)
    assert edge_lower_bound(0.44, 2.0, 10_000) == pytest.approx(edge, abs=0.02)
    assert edge_lower_bound(0.44, 2.0, 20) < edge_lower_bound(0.44, 2.0, 200)


def test_bound_curve_crosses_zero_at_the_required_count():
    curve = edge_bound_curve(0.44, 2.0, max_trades=400)
    crossing = curve.loc[curve["lower"] >= 0, "trades"].min()
    assert crossing == pytest.approx(trades_to_prove_edge(0.44, 2.0), rel=0.05)


def test_bound_curve_is_monotonic():
    curve = edge_bound_curve(0.33, 3.0, max_trades=600)
    assert np.all(np.diff(curve["lower"]) > 0)


def test_negative_edge_cannot_be_proven():
    with pytest.raises(ValueError, match="never be proven"):
        trades_to_prove_edge(0.20, 2.0)


def test_unknown_confidence_is_rejected():
    with pytest.raises(ValueError, match="confidence"):
        z_for(97)


def test_normal_approximation_guard():
    assert not normal_approximation_is_safe(0.22, 20)
    assert normal_approximation_is_safe(0.22, 200)


def test_normal_curve_peaks_at_the_mean():
    curve = normal_curve()
    peak = curve.loc[curve["density"].idxmax()]
    assert peak["z"] == pytest.approx(0.0, abs=0.02)
    assert peak["density"] == pytest.approx(1 / np.sqrt(2 * np.pi), rel=1e-3)


def test_normal_curve_is_symmetric():
    curve = normal_curve(-3, 3, n_points=301)
    np.testing.assert_allclose(
        curve["density"].to_numpy(), curve["density"].to_numpy()[::-1], atol=1e-12
    )


def test_normal_curve_integrates_to_one():
    curve = normal_curve(-6, 6, n_points=4001)
    area = np.trapezoid(curve["density"], curve["z"])
    assert area == pytest.approx(1.0, abs=1e-4)


def test_normal_curve_rejects_inverted_range():
    with pytest.raises(ValueError, match="hi must exceed lo"):
        normal_curve(2, 1)
