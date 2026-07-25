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

# Coarse enough to read at a glance in a diagnostics dump: off / sometimes / on.
BARS = "·▪█"


def sparkline(day: list[float] | None) -> str:
    """Render one weekday as 48 half-hour characters, midnight first."""
    if day is None:
        return "(never seen)"
    return "".join(BARS[min(len(BARS) - 1, int(value * len(BARS)))] for value in day)


def is_on(state: str) -> bool:
    """Return whether this state string reads as 'on' to a passer-by."""
    return state.lower() not in OFF_STATES


def empty_week() -> list[list[float] | None]:
    """A profile with nothing learned yet: seven unknown weekdays."""
    return [None] * 7


def day_grid(
    changes: list[tuple[dt.datetime, str]], day_start: dt.datetime
) -> list[float] | None:
    """Sample one entity's history into SLOTS on/off values for one day.

    `changes` is that entity's state history over the whole queried range,
    ascending, starting with the state it held when the range began — so the
    same list can be sampled for each day in the range. Returns None when there
    is no history at all.
    """
    if not changes:
        return None

    grid: list[float] = []
    idx = 0
    current = changes[0][1]
    for slot in range(SLOTS):
        at = day_start + dt.timedelta(minutes=slot * SLOT_MINUTES)
        while idx < len(changes) and changes[idx][0] <= at:
            current = changes[idx][1]
            idx += 1
        grid.append(1.0 if is_on(current) else 0.0)
    return grid


def fold(
    old: list[float] | None, observed: list[float], alpha: float = ALPHA
) -> list[float]:
    """Blend one observed day into the running profile for that weekday."""
    if old is None:
        return list(observed)  # first sighting: trust it outright
    return [o + alpha * (n - o) for o, n in zip(old, observed)]
