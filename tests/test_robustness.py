import pytest

from tfcore.expectancy import expectancy_from_rr
from tfcore.robustness import (
    critical_rr,
    critical_win_rate,
    rr_buffer,
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
