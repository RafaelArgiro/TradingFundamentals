"""The trading systems the app compares, and their shared styling.

Kept here so every page uses the same definitions and the same colour per
system.
"""

import pandas as pd

from tfcore.expectancy import ExpectancyInputs

SYSTEM_PALETTE = ["#4c78a8", "#f58518", "#54a24b", "#b279a2"]

DEFAULT_SYSTEMS = pd.DataFrame(
    {
        "System": ["A", "B", "C", "D"],
        "RR": [0.88, 2.0, 3.0, 5.0],
        "Win rate (%)": [70.0, 44.0, 33.0, 22.0],
    }
)


def system_colors(names) -> dict:
    """Map each system name to a stable colour from the palette."""
    return {
        name: SYSTEM_PALETTE[i % len(SYSTEM_PALETTE)] for i, name in enumerate(names)
    }


def rgba(hex_color: str, alpha: float) -> str:
    """Convert a #rrggbb colour to an rgba() string with the given opacity."""
    raw = hex_color.lstrip("#")
    red, green, blue = (int(raw[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({red}, {green}, {blue}, {alpha})"


def to_inputs(win_rate_pct: float, rr: float) -> ExpectancyInputs:
    """Build the core input object from the units used in the tables."""
    return ExpectancyInputs(win_rate=win_rate_pct / 100, avg_win=rr, avg_loss=1.0)
