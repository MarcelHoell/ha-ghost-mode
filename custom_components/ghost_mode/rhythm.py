"""The rhythm maths: turning state history into per-weekday on/off odds.

Deliberately free of Home Assistant imports so it runs — and is testable —
on its own. `learner.py` and `discovery.py` are the glue that feed it.
"""
from __future__ import annotations

import datetime as dt


def collapse_groups(
    candidates: set[str], members_by_group: dict[str, list[str]]
) -> set[str]:
    """Drop entities that a group we already learn speaks for.

    Learning a light group *and* its three bulbs means replaying the same
    physical light four times. The group wins: it is the thing a person
    actually switches. Lives here, not in `discovery.py`, only so it can be
    tested without Home Assistant.
    """
    covered = {
        member
        for group, members in members_by_group.items()
        if group in candidates
        for member in members
    }
    return candidates - covered

SLOT_MINUTES = 30
SLOTS = 24 * 60 // SLOT_MINUTES

# ponytail: a flat "not off" test instead of per-domain state machines. A cover
# that is `open` and a media_player that is `playing` both mean the same thing
# to someone watching the house.
OFF_STATES = {"off", "closed", "idle", "standby", "unavailable", "unknown", ""}

# How fast a new observation overwrites the old profile. 0.2 puts a weekday's
# half-life at ~3 weeks of observations. Lower = steadier but slower to adapt
# to a new routine; this is the knob to turn if replay feels stale or twitchy.
ALPHA = 0.2


WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# Five levels, because three could not tell "briefly on" from "off" — and a
# motion-triggered hall light lives entirely in that gap.
BARS = "·▁▃▅█"


def sparkline(day: list[float] | None) -> str:
    """Render one weekday as 48 half-hour characters, midnight first.

    Any activity at all draws as at least `▁`. A light on for two minutes is
    a real thing that happened; rounding it away to `·` would make the picture
    lie in the one direction that matters.
    """
    if day is None:
        return "(never seen)"
    return "".join(
        BARS[0]
        if value <= 0
        else BARS[max(1, min(len(BARS) - 1, int(value * len(BARS))))]
        for value in day
    )


def is_on(state: str) -> bool:
    """Return whether this state string reads as 'on' to a passer-by."""
    return state.lower() not in OFF_STATES


def varies(week: list[list[float] | None]) -> bool:
    """Return whether this week has anything worth *drawing*.

    A light that is off all week, or a device setting that is on all week, is
    a flat line. Keep it in the profile, keep it out of the picture.

    Deliberately judged on the rendered characters, not the raw floats: a week
    of 0.0 and 0.2 differs numerically but draws as 48 identical dots, and
    showing the viewer a blank row is worse than showing nothing.
    """
    drawn = "".join(sparkline(day) for day in week if day is not None)
    return len(set(drawn)) > 1


def empty_week() -> list[list[float] | None]:
    """A profile with nothing learned yet: seven unknown weekdays."""
    return [None] * 7


def day_grid(
    changes: list[tuple[dt.datetime, str]], day_start: dt.datetime
) -> list[float] | None:
    """Measure what fraction of each half hour the entity was on.

    `changes` is that entity's state history over the whole queried range,
    ascending, starting with the state it held when the range began — so the
    same list can be sampled for each day in the range. Returns None when there
    is no history at all.

    Integrating rather than sampling the instant at each boundary matters for
    anything a motion sensor drives: a hall light that is on for two minutes
    would be invisible at 29 boundaries out of 30 and, on the thirtieth, would
    read as a solid half hour. Neither is true. Two minutes now stores as
    0.067, which replay can reproduce as a brief flick rather than a
    conspicuous half-hour block.
    """
    if not changes:
        return None

    slot = dt.timedelta(minutes=SLOT_MINUTES)
    idx = 0
    current = changes[0][1]

    # Wind forward to whatever was true as this day began.
    while idx < len(changes) and changes[idx][0] <= day_start:
        current = changes[idx][1]
        idx += 1

    grid: list[float] = []
    for index in range(SLOTS):
        slot_start = day_start + slot * index
        slot_end = slot_start + slot
        on = dt.timedelta()
        cursor = slot_start

        while idx < len(changes) and changes[idx][0] < slot_end:
            when, state = changes[idx]
            if is_on(current):
                on += when - cursor
            cursor = when
            current = state
            idx += 1

        if is_on(current):
            on += slot_end - cursor
        grid.append(on / slot)
    return grid


def fold(
    old: list[float] | None, observed: list[float], alpha: float = ALPHA
) -> list[float]:
    """Blend one observed day into the running profile for that weekday."""
    if old is None:
        return list(observed)  # first sighting: trust it outright
    return [o + alpha * (n - o) for o, n in zip(old, observed)]
