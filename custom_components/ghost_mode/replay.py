"""Replays the learned rhythm while the house is empty.

Active only when the master switch is on *and* — if one is configured — the
alarm says away. Both, deliberately: the switch alone would replay while you
are on the sofa, and the alarm alone would take the decision out of your hands.

On the way back it undoes its own work and nothing else.
"""
from __future__ import annotations

import datetime as dt
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ALARM,
    CONF_DRIVE,
    DEFAULT_DRIVE,
    DOMAIN,
    SIGNAL_ENABLED,
    SIGNAL_REPLAY,
)
from .learner import Learner
from .rhythm import SLOT_MINUTES, desired_on, is_on

_LOGGER = logging.getLogger(__name__)

# An alarm in either of these means nobody is expected home.
AWAY_STATES = {"armed_away", "armed_vacation"}

# How often to reconsider. Fine enough that a 30-minute slot lands roughly on
# time, coarse enough that it is not doing work every minute all night.
TICK = dt.timedelta(minutes=5)

# ponytail: `homeassistant.turn_on` covers most domains, but `cover` registers
# open_cover/close_cover and no turn_on at all — calling the generic service
# would skip covers in silence.
_SERVICES: dict[str, tuple[str, str, str]] = {
    "cover": ("cover", "open_cover", "close_cover")
}
_GENERIC = ("homeassistant", "turn_on", "turn_off")


class Replay:
    """Drives the learned profile while away, and cleans up after itself."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, learner: Learner
    ) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry
        self.learner = learner
        # entity_id -> (state before we touched it, whether we switched it on)
        self._driven: dict[str, tuple[str, bool]] = {}
        # entity_id -> when we last acted, so we never fight a motion
        # automation that switches our light straight back off.
        self._acted: dict[str, dt.datetime] = {}
        self._running = False
        self._announced: tuple | None = None

    @property
    def is_running(self) -> bool:
        """Return whether replay is driving the house at this moment."""
        return self._running

    @property
    def held(self) -> list[str]:
        """Return the entities replay would put back if you walked in now."""
        return sorted(self._driven)

    @callback
    def blocked_by(self) -> str | None:
        """Return why replay is not running, or None if nothing is stopping it."""
        if self.hass.data[DOMAIN].get("forced"):
            # The force switch overrides everything, including the master
            # switch: it exists precisely for when the alarm is the wrong
            # signal — testing what replay does, or being away without arming.
            return None
        if not self.hass.data[DOMAIN].get("enabled"):
            return "the Ghost Mode switch is off"
        if not (alarm := self.entry.options.get(CONF_ALARM)):
            return None
        if (state := self.hass.states.get(alarm)) is None:
            return f"{alarm} is unavailable"
        if state.state not in AWAY_STATES:
            return f"{alarm} is {state.state}"
        return None

    @callback
    def _announce(self) -> None:
        """Tell the binary sensor, but only when something actually changed."""
        snapshot = (self._running, frozenset(self._driven))
        if snapshot == self._announced:
            return
        self._announced = snapshot
        async_dispatcher_send(self.hass, SIGNAL_REPLAY)

    @property
    def _domains(self) -> set[str]:
        """Return the domains the user allows replay to switch."""
        return set(self.entry.options.get(CONF_DRIVE, DEFAULT_DRIVE))

    @callback
    def is_away(self) -> bool:
        """Return whether replay should be driving the house right now.

        With no alarm configured the switch decides alone: it is an explicit
        human action, so honour it rather than refusing to do anything.
        """
        return self.blocked_by() is None

    async def async_evaluate(self, _trigger: object = None) -> None:
        """Bring the house into line with the profile, or stand down.

        Called from the timer, the switch dispatcher and the alarm listener,
        each of which hands over something different. None of it is used.
        """
        if not self.is_away():
            await self.async_stand_down()
            return

        if not self._running:
            _LOGGER.info("Replay starting: the house is empty and Ghost Mode is on")
            self._running = True

        now = dt_util.now()
        self.learner.note_replayed(now.date())

        for entity_id, week in list(self.learner.profile.items()):
            if entity_id.split(".", 1)[0] not in self._domains:
                continue
            if (want := desired_on(entity_id, week, now)) is None:
                continue
            if (state := self.hass.states.get(entity_id)) is None:
                continue
            if is_on(state.state) is want:
                continue
            # One command per entity per slot. If something switches our light
            # back off in between — a motion automation usually — let it.
            last = self._acted.get(entity_id)
            if last is not None and now - last < dt.timedelta(minutes=SLOT_MINUTES):
                continue

            await self._async_set(entity_id, want, state.state)

        self._announce()

    async def _async_set(self, entity_id: str, on: bool, before: str) -> None:
        """Switch one entity, remembering what it was first."""
        domain = entity_id.split(".", 1)[0]
        service_domain, on_service, off_service = _SERVICES.get(domain, _GENERIC)
        self._acted[entity_id] = dt_util.now()
        try:
            await self.hass.services.async_call(
                service_domain,
                on_service if on else off_service,
                {"entity_id": entity_id},
                blocking=False,
            )
        except Exception:  # noqa: BLE001 - one bad bulb must not end the show
            _LOGGER.warning("Could not switch %s; carrying on", entity_id)
            return
        # Only claim it once the call actually went out, or standing down
        # would try to "restore" something we never changed.
        self._driven.setdefault(entity_id, (before, on))

    async def async_stand_down(self) -> None:
        """Undo our own changes and stop. Anything else stays as it is."""
        if not self._running and not self._driven:
            return
        self._running = False

        reverted = 0
        for entity_id, (before, we_set_on) in list(self._driven.items()):
            state = self.hass.states.get(entity_id)
            if state is None or is_on(state.state) is not we_set_on:
                # Somebody — or some automation — has changed it since. Not
                # ours to undo any more.
                continue
            await self._async_set(entity_id, is_on(before), state.state)
            reverted += 1

        self._driven.clear()
        self._acted.clear()
        self._announce()
        if reverted:
            _LOGGER.info("Replay stopped; put %s entit%s back", reverted,
                         "y" if reverted == 1 else "ies")


async def async_setup_replay(
    hass: HomeAssistant, entry: ConfigEntry, learner: Learner
) -> Replay:
    """Start the replay coordinator and wire up what wakes it."""
    replay = Replay(hass, entry, learner)

    # The tick is the slow path. The switch and the alarm are the fast one:
    # coming home has to stop replay now, not within five minutes.
    unsubs = [
        async_track_time_interval(hass, replay.async_evaluate, TICK),
        async_dispatcher_connect(hass, SIGNAL_ENABLED, replay.async_evaluate),
    ]
    if alarm := entry.options.get(CONF_ALARM):
        # Hand over the coroutine itself. A plain lambda here would be treated
        # as a sync callback and run in an executor thread, and scheduling loop
        # work from there is exactly what Home Assistant now refuses to allow.
        unsubs.append(
            async_track_state_change_event(hass, [alarm], replay.async_evaluate)
        )
    hass.data[DOMAIN]["unsub_replay"] = unsubs
    return replay
