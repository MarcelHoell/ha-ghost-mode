"""Self-check for the rhythm maths. Run it directly: `python3 tests/test_rhythm.py`.

No Home Assistant, no pytest — `rhythm.py` is deliberately import-free so the
sampling and blending can be checked on their own.
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "ghost_mode"))

from rhythm import (  # noqa: E402
    ALPHA,
    SLOTS,
    WEEKDAYS,
    collapse_groups,
    day_grid,
    empty_week,
    fold,
    is_on,
    sparkline,
    varies,
)

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


def test_sparkline_reads_as_the_day():
    assert sparkline(None) == "(never seen)"
    assert sparkline([0.0] * SLOTS) == "·" * SLOTS
    assert sparkline([1.0] * SLOTS) == "█" * SLOTS, "1.0 must not index off the end"
    assert sparkline([0.5] * SLOTS) == "▪" * SLOTS
    assert len(sparkline([0.0] * SLOTS)) == SLOTS, "one character per slot"
    # A morning-only day should be readable at a glance.
    assert sparkline(day_grid([(DAY, "off"), (DAY + dt.timedelta(hours=8), "on")], DAY)) == (
        "·" * 16 + "█" * 32
    )


def test_weekdays_line_up_with_python():
    assert len(WEEKDAYS) == 7
    assert WEEKDAYS[DAY.weekday()] == "Mon", "index 0 must be Monday, as weekday() says"


def test_varies_hides_the_flat_lines():
    off_all_week = [[0.0] * SLOTS] * 7
    on_all_week = [[1.0] * SLOTS] * 7  # the vacuum's UV lamp setting
    assert not varies(off_all_week), "a light off all week is not worth drawing"
    assert not varies(on_all_week), "a permanently-on setting is not either"
    assert not varies(empty_week()), "nothing observed yet is not worth drawing"

    real = [[0.0] * SLOTS] * 6 + [day_grid([(DAY, "off"), (DAY + dt.timedelta(hours=20), "on")], DAY)]
    assert varies(real), "one real evening is enough to be worth drawing"

    # A single half-hour of activity in an otherwise dark week still counts.
    barely = [list([0.0] * SLOTS) for _ in range(7)]
    barely[3][40] = 1.0
    assert varies(barely)


def test_group_replaces_its_members():
    # The real case: one office group plus its two bulbs.
    candidates = {"light.buro", "light.buro_links", "light.buro_rechts", "light.kuche"}
    groups = {"light.buro": ["light.buro_links", "light.buro_rechts"]}
    assert collapse_groups(candidates, groups) == {"light.buro", "light.kuche"}


def test_members_survive_when_the_group_is_not_learned():
    # Group excluded by the user (or hidden): keep the bulbs, or we lose the room.
    candidates = {"light.buro_links", "light.buro_rechts"}
    groups = {"light.buro": ["light.buro_links", "light.buro_rechts"]}
    assert collapse_groups(candidates, groups) == candidates


def test_nested_groups_keep_only_the_outermost():
    candidates = {"light.all", "light.buro", "light.buro_links"}
    groups = {
        "light.all": ["light.buro"],
        "light.buro": ["light.buro_links"],
    }
    # light.all covers light.buro, which covers the bulb.
    assert collapse_groups(candidates, groups) == {"light.all"}


def test_no_groups_changes_nothing():
    candidates = {"light.a", "light.b"}
    assert collapse_groups(candidates, {}) == candidates


def test_empty_week_has_seven_unknown_days():
    week = empty_week()
    assert len(week) == 7 and all(day is None for day in week)


if __name__ == "__main__":
    for name, fn in sorted(vars().copy().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("\nall good")
