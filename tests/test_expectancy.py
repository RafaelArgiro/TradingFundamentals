import numpy as np
import pytest

from tfcore.expectancy import (
    ExpectancyInputs,
    breakeven_curve,
    breakeven_points,
    breakeven_win_rate,
    expectancy,
    expectancy_from_rr,
    expectancy_vs_rr,
    expectancy_vs_win_rate,
    required_win_rate,
    reward_to_risk,
)


def test_known_positive_system():
    got = expectancy(ExpectancyInputs(win_rate=0.45, avg_win=2.0, avg_loss=1.0))
    assert got == pytest.approx(0.35)


def test_known_negative_system():
    got = expectancy(ExpectancyInputs(win_rate=0.30, avg_win=1.0, avg_loss=1.0))
    assert got == pytest.approx(-0.40)


def test_always_wins_returns_avg_win():
    got = expectancy(ExpectancyInputs(win_rate=1.0, avg_win=2.5, avg_loss=1.0))
    assert got == pytest.approx(2.5)


def test_always_loses_returns_negative_avg_loss():
    got = expectancy(ExpectancyInputs(win_rate=0.0, avg_win=2.5, avg_loss=1.0))
    assert got == pytest.approx(-1.0)


@pytest.mark.parametrize(
    ("avg_win", "avg_loss", "expected"),
    [
        (1.0, 1.0, 0.50),
        (2.0, 1.0, 1 / 3),
        (3.0, 1.0, 0.25),
        (1.0, 2.0, 2 / 3),
    ],
)
def test_breakeven_win_rate(avg_win, avg_loss, expected):
    assert breakeven_win_rate(avg_win, avg_loss) == pytest.approx(expected)


def test_breakeven_win_rate_gives_zero_expectancy():
    """The two formulas must agree -- this is the cross-check that matters."""
    for avg_win, avg_loss in [(2.0, 1.0), (1.5, 0.5), (1.0, 3.0)]:
        wr = breakeven_win_rate(avg_win, avg_loss)
        assert expectancy(ExpectancyInputs(wr, avg_win, avg_loss)) == pytest.approx(0.0)


def test_reward_to_risk():
    assert reward_to_risk(ExpectancyInputs(0.5, 3.0, 1.5)) == pytest.approx(2.0)


def test_expectancy_from_rr():
    assert expectancy_from_rr(0.45, 2.0) == pytest.approx(0.35)


def test_expectancy_from_rr_is_zero_on_the_breakeven_curve():
    for rr in [0.5, 1.0, 2.0, 5.0, 10.0]:
        assert expectancy_from_rr(required_win_rate(rr), rr) == pytest.approx(0.0)


@pytest.mark.parametrize("bad_rate", [-0.1, 1.1])
def test_rejects_impossible_win_rate(bad_rate):
    with pytest.raises(ValueError, match="win_rate"):
        ExpectancyInputs(win_rate=bad_rate, avg_win=2.0, avg_loss=1.0)


def test_rejects_negative_avg_loss():
    with pytest.raises(ValueError, match="avg_loss"):
        ExpectancyInputs(win_rate=0.5, avg_win=2.0, avg_loss=-1.0)


@pytest.mark.parametrize(
    ("rr", "expected"),
    [(0.5, 2 / 3), (1.0, 0.5), (2.0, 1 / 3), (3.0, 0.25), (10.0, 1 / 11)],
)
def test_required_win_rate(rr, expected):
    assert required_win_rate(rr) == pytest.approx(expected)


def test_required_win_rate_matches_breakeven_win_rate():
    """Both must describe the same thing -- rr is just avg_win at avg_loss=1."""
    for rr in [0.5, 1.0, 2.5, 7.0, 10.0]:
        assert required_win_rate(rr) == pytest.approx(breakeven_win_rate(rr, 1.0))


def test_breakeven_curve_shape_and_bounds():
    curve = breakeven_curve(0.5, 10.0, n_points=100)
    assert list(curve.columns) == ["rr", "win_rate"]
    assert len(curve) == 100
    assert curve["rr"].iloc[0] == pytest.approx(0.5)
    assert curve["rr"].iloc[-1] == pytest.approx(10.0)
    assert curve["win_rate"].between(0, 1).all()


def test_breakeven_curve_decreases_monotonically():
    """Better reward-to-risk must always mean a lower required win rate."""
    curve = breakeven_curve(0.5, 10.0, n_points=200)
    assert np.all(np.diff(curve["win_rate"]) < 0)


def test_breakeven_curve_points_are_zero_expectancy():
    curve = breakeven_curve(0.5, 10.0, n_points=25)
    for rr, wr in zip(curve["rr"], curve["win_rate"], strict=True):
        assert expectancy(ExpectancyInputs(wr, rr, 1.0)) == pytest.approx(0.0)


def test_breakeven_points_at_integers():
    pts = breakeven_points(range(1, 11))
    assert len(pts) == 10
    assert pts["win_rate"].iloc[0] == pytest.approx(0.5)
    assert pts["win_rate"].iloc[-1] == pytest.approx(1 / 11)


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"rr_min": 0.0}, "rr_min"),
        ({"rr_min": 5.0, "rr_max": 2.0}, "rr_max"),
        ({"n_points": 1}, "n_points"),
    ],
)
def test_breakeven_curve_rejects_bad_ranges(kwargs, match):
    with pytest.raises(ValueError, match=match):
        breakeven_curve(**kwargs)


def test_expectancy_vs_win_rate_is_a_straight_line():
    """Slope must be exactly R + 1."""
    curve = expectancy_vs_win_rate(2.0, n_points=50)
    slopes = np.diff(curve["expectancy"]) / np.diff(curve["win_rate"])
    assert np.allclose(slopes, 3.0)


def test_expectancy_vs_win_rate_crosses_zero_at_breakeven():
    curve = expectancy_vs_win_rate(3.0, n_points=1001)
    crossing = curve.loc[curve["expectancy"].abs().idxmin(), "win_rate"]
    assert crossing == pytest.approx(required_win_rate(3.0), abs=1e-3)


def test_expectancy_vs_rr_is_a_straight_line():
    """Slope must be exactly W."""
    curve = expectancy_vs_rr(0.45, n_points=50)
    slopes = np.diff(curve["expectancy"]) / np.diff(curve["rr"])
    assert np.allclose(slopes, 0.45)


def test_expectancy_curves_agree_at_the_shared_point():
    by_win_rate = expectancy_vs_win_rate(2.0, n_points=3)
    assert by_win_rate["expectancy"].iloc[-1] == pytest.approx(
        expectancy_from_rr(1.0, 2.0)
    )
