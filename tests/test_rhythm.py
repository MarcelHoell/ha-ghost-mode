"""Self-check for the rhythm maths. Run it directly: `python3 tests/test_rhythm.py`.

No Home Assistant, no pytest — `rhythm.py` is deliberately import-free so the
sampling and blending can be checked on their own.
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "ghost_mode"))

from rhythm import ALPHA, SLOTS, day_grid, empty_week, fold, is_on  # noqa: E402

DAY = dt.datetime(2026, 7, 20)  # a Monday


def test_is_on():
    assert is_on("on") and is_on("open") and is_on("playing")
    assert not is_on("off") and not is_on("closed") and not is_on("unavailable")
    assert not is_on("Unknown"), "state matching must be case-insensitive"


def test_grid_samples_the_whole_day():
    # On from 08:00, off again at 22:00.
    changes = [
        (DAY, "off"),
        (DAY + dt.timedelta(hours=8), "on"),
        (DAY + dt.timedelta(hours=22), "off"),
    ]
    grid = day_grid(changes, DAY)
    assert len(grid) == SLOTS
    assert grid[0] == 0.0, "midnight is off"
    assert grid[15] == 0.0, "07:30 is still off"
    assert grid[16] == 1.0, "08:00 turns on"
    assert grid[43] == 1.0, "21:30 still on"
    assert grid[44] == 0.0, "22:00 turns off"
    assert sum(grid) == 28, "14 hours on = 28 half-hour slots"


def test_grid_carries_state_in_from_before_the_day():
    # One change, days earlier: the entity was on for this whole day.
    changes = [(DAY - dt.timedelta(days=3), "on")]
    assert day_grid(changes, DAY) == [1.0] * SLOTS


def test_grid_is_reusable_across_days_in_one_range():
    # The same history list sampled for two different days must not bleed:
    # on all of Monday, off all of Tuesday.
    tuesday = DAY + dt.timedelta(days=1)
    changes = [(DAY, "on"), (tuesday, "off")]
    assert day_grid(changes, DAY) == [1.0] * SLOTS
    assert day_grid(changes, tuesday) == [0.0] * SLOTS


def test_no_history_is_not_an_empty_day():
    assert day_grid([], DAY) is None, "no rows must not be learned as 'always off'"


def test_fold_trusts_the_first_sighting_then_eases():
    observed = [1.0] * SLOTS
    first = fold(None, observed)
    assert first == observed

    # A contradicting day only moves the profile by alpha.
    second = fold(first, [0.0] * SLOTS)
    assert abs(second[0] - (1.0 - ALPHA)) < 1e-9

    # Repeated agreement converges towards the observation, never past it.
    value = second[0]
    for _ in range(50):
        value = fold([value], [0.0])[0]
    assert 0.0 <= value < 0.01


def test_empty_week_has_seven_unknown_days():
    week = empty_week()
    assert len(week) == 7 and all(day is None for day in week)


if __name__ == "__main__":
    for name, fn in sorted(vars().copy().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("\nall good")
