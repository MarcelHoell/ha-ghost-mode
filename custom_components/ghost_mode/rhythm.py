"""The rhythm maths: turning state history into per-weekday on/off odds.

Deliberately free of Home Assistant imports so it runs — and is testable —
on its own. `learner.py` and `discovery.py` are the glue that feed it.
"""
from __future__ import annotations

import datetime as dt
import hashlib

# How far a replayed transition may drift from the learned time. Without this
# the house switches on at exactly 20:00 every evening, which is the tell that
# gives away every timer-based presence simulation.
JITTER_MINUTES = 20


def stable_random(*parts: object) -> float:
    """A repeatable 0.0-1.0 drawn from the given parts.

    Repeatable matters more than random here: the same entity on the same day
    must reach the same answer every tick, or a light 60% likely to be on
    would flicker every few minutes instead of simply being on.
    """
    seed = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(hashlib.sha256(seed).digest()[:8], "big") / 2**64


def desired_on(
    entity_id: str,
    week: list[list[float] | None],
    when: dt.datetime,
    jitter_minutes: int = JITTER_MINUTES,
) -> bool | None:
    """Return whether this entity should be on at `when`, or None if unlearned.

    The stored value is a probability, not a schedule: 1.0 is always on, 0.0
    never, and 0.07 — a hall light that gets a couple of minutes of motion in
    a half hour — comes on in roughly one such half hour in fourteen. Drawing
    per slot rather than thresholding is what keeps the pattern from repeating
    identically every week.
    """
    drift = (stable_random(entity_id, when.date()) * 2 - 1) * jitter_minutes
    shifted = when - dt.timedelta(minutes=drift)

    if (day := week[shifted.weekday()]) is None:
        return None

    slot = (shifted.hour * 60 + shifted.minute) // SLOT_MINUTES
    probability = day[slot]
    if probability <= 0:
        return False
    if probability >= 1:
        return True
    return stable_random(entity_id, shifted.date(), slot) < probability


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
OFF_STATES = {"off", "closed", "idle", "standby"}

# Not off — *unknown*. A Zigbee bulb that drops off the mesh for three days
# tells us nothing about whether the room was lit; counting it as darkness
# would train the profile hard toward "never on", which is the opposite of
# what happened. These periods are left out of the average entirely.
UNKNOWN_STATES = {"unavailable", "unknown", "none", ""}

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


def is_known(state: str) -> bool:
    """Return whether this state says anything about the house at all."""
    return state.lower() not in UNKNOWN_STATES


def is_on(state: str) -> bool:
    """Return whether this state string reads as 'on' to a passer-by."""
    return is_known(state) and state.lower() not in OFF_STATES


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
) -> list[float | None] | None:
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

    A slot is the fraction of its *known* time the entity was on. A slot with
    no known time at all comes back as None, meaning "no evidence" — `fold`
    leaves the stored value alone rather than pulling it toward darkness.
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

    grid: list[float | None] = []
    for index in range(SLOTS):
        slot_start = day_start + slot * index
        slot_end = slot_start + slot
        on = dt.timedelta()
        known = dt.timedelta()
        cursor = slot_start

        while idx < len(changes) and changes[idx][0] < slot_end:
            when, state = changes[idx]
            if is_known(current):
                known += when - cursor
                if is_on(current):
                    on += when - cursor
            cursor = when
            current = state
            idx += 1

        if is_known(current):
            known += slot_end - cursor
            if is_on(current):
                on += slot_end - cursor

        grid.append(on / known if known else None)
    return grid


def fold(
    old: list[float] | None, observed: list[float | None], alpha: float = ALPHA
) -> list[float]:
    """Blend one observed day into the running profile for that weekday.

    A `None` slot in `observed` means the entity was unavailable for that whole
    half hour. There is nothing to learn from it, so the stored value stays put
    — an offline device must not slowly erase a real habit.
    """
    if old is None:
        # First sighting: trust it outright. Slots with no evidence start at
        # zero, which is the only honest guess when nothing has been seen.
        return [0.0 if value is None else value for value in observed]
    return [
        previous if value is None else previous + alpha * (value - previous)
        for previous, value in zip(old, observed)
    ]
