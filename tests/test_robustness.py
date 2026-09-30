import pytest

from tfcore.expectancy import expectancy_from_rr
from tfcore.robustness import (
    absolute_sensitivity_range,
    critical_rr,
    critical_win_rate,
    elasticity_rr,
    elasticity_win_rate,
    rr_buffer,
    sensitivity_range,
    win_rate_buffer,
)


@pytest.mark.parametrize(
    ("rr", "expected"), [(1.0, 0.5), (2.0, 1 / 3), (3.0, 0.25), (0.5, 2 / 3)]
)
def test_critical_win_rate(rr, expected):
    assert critical_win_rate(rr) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("win_rate", "expected"), [(0.5, 1.0), (0.25, 3.0), (0.75, 1 / 3)]
)
def test_critical_rr(win_rate, expected):
    assert critical_rr(win_rate) == pytest.approx(expected)


def test_buffers_are_zero_at_breakeven():
    for rr in [0.5, 1.0, 2.0, 5.0]:
        wr = critical_win_rate(rr)
        assert win_rate_buffer(wr, rr) == pytest.approx(0.0)
        assert rr_buffer(wr, rr) == pytest.approx(0.0)


def test_buffers_positive_when_profitable():
    assert expectancy_from_rr(0.45, 2.0) > 0
    assert win_rate_buffer(0.45, 2.0) > 0
    assert rr_buffer(0.45, 2.0) > 0


def test_buffers_negative_when_losing():
    assert expectancy_from_rr(0.25, 2.0) < 0
    assert win_rate_buffer(0.25, 2.0) < 0
    assert rr_buffer(0.25, 2.0) < 0


def test_win_rate_buffer_scales_to_expectancy():
    """E = (R + 1) * win-rate buffer."""
    for wr, rr in [(0.45, 2.0), (0.7, 0.5), (0.22, 5.0)]:
        assert expectancy_from_rr(wr, rr) == pytest.approx((rr + 1) * win_rate_buffer(wr, rr))


def test_rr_buffer_scales_to_expectancy():
    """E = win rate * RR buffer."""
    for wr, rr in [(0.45, 2.0), (0.7, 0.5), (0.22, 5.0)]:
        assert expectancy_from_rr(wr, rr) == pytest.approx(wr * rr_buffer(wr, rr))


def test_rejects_zero_win_rate():
    with pytest.raises(ValueError, match="win_rate"):
        critical_rr(0.0)


def test_elasticity_win_rate_matches_worked_example():
    assert elasticity_win_rate(0.45, 2.0) == pytest.approx(1.35 / 0.35)


def test_elasticity_rr_matches_worked_example():
    assert elasticity_rr(0.45, 2.0) == pytest.approx(0.9 / 0.35)


def test_win_rate_is_always_the_more_elastic_parameter():
    """The ratio must equal 1 + 1/R for any profitable system."""
    for wr, rr in [(0.45, 2.0), (0.7, 0.5), (0.22, 5.0), (0.55, 1.0)]:
        ratio = elasticity_win_rate(wr, rr) / elasticity_rr(wr, rr)
        assert ratio == pytest.approx(1 + 1 / rr)
        assert ratio > 1


def test_relative_tolerance_is_inverse_elasticity():
    """1/e must equal the relative drop that takes the system to break-even."""
    for wr, rr in [(0.45, 2.0), (0.7, 0.5), (0.22, 5.0)]:
        tolerated = win_rate_buffer(wr, rr) / wr
        assert tolerated == pytest.approx(1 / elasticity_win_rate(wr, rr))

        tolerated_rr = rr_buffer(wr, rr) / rr
        assert tolerated_rr == pytest.approx(1 / elasticity_rr(wr, rr))


def test_elasticity_diverges_near_breakeven():
    just_above = critical_win_rate(2.0) + 1e-4
    assert elasticity_win_rate(just_above, 2.0) > 1000


def test_sensitivity_range_brackets_the_baseline():
    base = expectancy_from_rr(0.45, 2.0)
    lo, hi = sensitivity_range(0.45, 2.0, "win_rate", 10)
    assert lo < base < hi


def test_sensitivity_range_caps_win_rate_at_one():
    lo, hi = sensitivity_range(0.95, 2.0, "win_rate", 50)
    assert hi == pytest.approx(expectancy_from_rr(1.0, 2.0))
    assert lo < hi


def test_sensitivity_to_win_rate_exceeds_sensitivity_to_rr():
    wr_lo, wr_hi = sensitivity_range(0.45, 2.0, "win_rate", 10)
    rr_lo, rr_hi = sensitivity_range(0.45, 2.0, "rr", 10)
    assert (wr_hi - wr_lo) > (rr_hi - rr_lo)


def test_sensitivity_range_rejects_unknown_parameter():
    with pytest.raises(ValueError, match="parameter"):
        sensitivity_range(0.45, 2.0, "drawdown", 10)  # type: ignore[arg-type]


def test_absolute_win_rate_shift_width_is_2_delta_times_r_plus_1():
    """dE/dW = R + 1, so the bar width must be exactly 2 * delta * (R + 1)."""
    delta = 0.05
    for wr, rr in [(0.45, 2.0), (0.35, 3.0), (0.22, 5.0)]:
        low, high = absolute_sensitivity_range(wr, rr, "win_rate", delta)
        assert high - low == pytest.approx(2 * delta * (rr + 1))


def test_absolute_rr_shift_width_is_2_delta_times_win_rate():
    """dE/dR = W, so the bar width must be exactly 2 * delta * W."""
    delta = 0.1
    for wr, rr in [(0.45, 2.0), (0.7, 0.5), (0.22, 5.0)]:
        low, high = absolute_sensitivity_range(wr, rr, "rr", delta)
        assert high - low == pytest.approx(2 * delta * wr)


def test_absolute_range_is_centred_on_the_baseline():
    base = expectancy_from_rr(0.45, 2.0)
    low, high = absolute_sensitivity_range(0.45, 2.0, "win_rate", 0.05)
    assert (low + high) / 2 == pytest.approx(base)


def test_absolute_range_clamps_win_rate():
    low, high = absolute_sensitivity_range(0.97, 2.0, "win_rate", 0.10)
    assert high == pytest.approx(expectancy_from_rr(1.0, 2.0))
    assert low == pytest.approx(expectancy_from_rr(0.87, 2.0))


def test_absolute_range_clamps_rr_at_zero():
    low, _ = absolute_sensitivity_range(0.45, 0.05, "rr", 0.2)
    assert low == pytest.approx(expectancy_from_rr(0.45, 0.0))


def test_absolute_range_rejects_non_positive_delta():
    with pytest.raises(ValueError, match="delta"):
        absolute_sensitivity_range(0.45, 2.0, "win_rate", 0.0)
