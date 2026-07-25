"""Folds recorder history into a per-weekday occupancy profile.

Recorder is already the recorder — nothing here listens to state changes. Once
a day this reads back the days it has not seen yet and blends them into a
running profile: for every entity, every weekday, every half hour, how likely
that entity was on while the home was lived in.

Recorder purges after `purge_keep_days` (10 by default), so a four-week profile
cannot be re-derived on demand. It has to be accumulated, which is what the
exponential moving average in `rhythm.py` does — old weeks fade instead of
being stored.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from homeassistant.components.recorder import get_instance, history
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .discovery import ghostable_entities
from .rhythm import day_grid, empty_week, fold

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}.profile"
STORAGE_VERSION = 1

# Never look further back than recorder is likely to hold. Beyond this the
# query just returns nothing and costs time.
MAX_BACKFILL_DAYS = 10

# Learn overnight, off the hour, so it does not pile onto recorder's own purge.
LEARN_HOUR, LEARN_MINUTE = 3, 17


class Learner:
    """Owns the stored profile and the nightly fold."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the learner."""
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = {"last_day": None, "entities": {}}

    @property
    def profile(self) -> dict[str, list[list[float] | None]]:
        """Return the learned profile, keyed by entity id then weekday."""
        return self._data["entities"]

    async def async_load(self) -> None:
        """Load the profile from disk."""
        if (stored := await self._store.async_load()) is not None:
            self._data = stored

    async def async_update(self) -> None:
        """Fold every complete day we have not seen yet into the profile."""
        today = dt_util.start_of_local_day()
        start = dt_util.start_of_local_day(today - dt.timedelta(days=MAX_BACKFILL_DAYS))

        if (last_day := self._data.get("last_day")) is not None:
            resume = dt_util.start_of_local_day(
                dt.datetime.fromisoformat(last_day)
            ) + dt.timedelta(days=1)
            start = max(start, resume)

        if start >= today:
            return  # nothing has completed since the last run

        if not (entity_ids := ghostable_entities(self.hass)):
            return

        states = await get_instance(self.hass).async_add_executor_job(
            lambda: history.get_significant_states(
                self.hass,
                dt_util.as_utc(start),
                dt_util.as_utc(today),
                entity_ids,
                no_attributes=True,
            )
        )
        changes = {
            entity_id: [(s.last_changed, s.state) for s in entity_states]
            for entity_id, entity_states in states.items()
        }

        days = 0
        day_start = start
        while day_start < today:
            for entity_id, entity_changes in changes.items():
                if (grid := day_grid(entity_changes, day_start)) is None:
                    continue
                week = self.profile.setdefault(entity_id, empty_week())
                week[day_start.weekday()] = fold(week[day_start.weekday()], grid)
            # Not timedelta(days=1) on a naive clock: DST days are 23h or 25h,
            # and start_of_local_day keeps every day anchored to real midnight.
            day_start = dt_util.start_of_local_day(day_start + dt.timedelta(days=1, hours=1))
            days += 1

        # Entities that left the registry stop being replayed.
        for gone in set(self.profile) - set(entity_ids):
            del self.profile[gone]

        self._data["last_day"] = (today - dt.timedelta(days=1)).date().isoformat()
        await self._store.async_save(self._data)
        _LOGGER.debug("Learned %s day(s) across %s entities", days, len(self.profile))


async def async_setup_learner(hass: HomeAssistant) -> Learner:
    """Load the profile, catch up on missed days, and schedule the nightly run."""
    learner = Learner(hass)
    await learner.async_load()
    await learner.async_update()

    async def _nightly(_now: dt.datetime) -> None:
        await learner.async_update()

    hass.data[DOMAIN]["unsub_learn"] = async_track_time_change(
        hass, _nightly, hour=LEARN_HOUR, minute=LEARN_MINUTE, second=0
    )
    return learner
