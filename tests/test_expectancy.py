import pytest

from tfcore.expectancy import (
    ExpectancyInputs,
    breakeven_win_rate,
    expectancy,
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


@pytest.mark.parametrize("bad_rate", [-0.1, 1.1])
def test_rejects_impossible_win_rate(bad_rate):
    with pytest.raises(ValueError, match="win_rate"):
        ExpectancyInputs(win_rate=bad_rate, avg_win=2.0, avg_loss=1.0)


def test_rejects_negative_avg_loss():
    with pytest.raises(ValueError, match="avg_loss"):
        ExpectancyInputs(win_rate=0.5, avg_win=2.0, avg_loss=-1.0)
