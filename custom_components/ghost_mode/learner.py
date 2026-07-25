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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import CONF_EXCLUDE, DOMAIN, SIGNAL_PROFILE_UPDATED
from .discovery import GHOSTABLE_DOMAINS, ghostable_entities
from .rhythm import day_grid, empty_week, fold

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}.profile"
STORAGE_VERSION = 1

# A ceiling on how far back to look, whatever recorder is keeping. Four weeks
# is already past the EMA's ~3-week half-life, so older days barely move the
# profile while the query grows without limit. Someone keeping a year of
# history does not want that year read on every fresh start.
MAX_BACKFILL_DAYS = 28

# Learn overnight, off the hour, so it does not pile onto recorder's own purge.
LEARN_HOUR, LEARN_MINUTE = 3, 17


class Learner:
    """Owns the stored profile and the nightly fold."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the learner."""
        self.hass = hass
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = {"last_day": None, "entities": {}}

    @property
    def profile(self) -> dict[str, list[list[float] | None]]:
        """Return the learned profile, keyed by entity id then weekday."""
        return self._data["entities"]

    @property
    def entity_ids(self) -> list[str]:
        """Return the entities to learn, honouring the user's exclusions."""
        return ghostable_entities(
            self.hass, self.entry.options.get(CONF_EXCLUDE, [])
        )

    @property
    def last_day(self) -> str | None:
        """Return the last day folded in, or None if nothing has been learned."""
        return self._data.get("last_day")

    async def async_load(self) -> None:
        """Load the profile from disk."""
        if (stored := await self._store.async_load()) is not None:
            self._data = stored

    def _backfill_days(self) -> int:
        """Return how far back it is worth querying, in days.

        Ask recorder rather than assuming: `purge_keep_days` is configurable,
        and hard-coding 10 threw away three weeks of usable history from
        anyone who had raised it. `0` means "never purge", so fall back to the
        ceiling rather than to nothing.
        """
        keep_days = getattr(get_instance(self.hass), "keep_days", 0) or 0
        if keep_days <= 0:
            return MAX_BACKFILL_DAYS
        return min(keep_days, MAX_BACKFILL_DAYS)

    async def async_update(self) -> None:
        """Fold every complete day we have not seen yet into the profile."""
        if not (entity_ids := self.entity_ids):
            _LOGGER.warning(
                "Nothing to learn from: no enabled, visible entities in %s",
                ", ".join(sorted(GHOSTABLE_DOMAINS)),
            )
            return

        # Prune before the date guard below, not after the fold. An upgrade or
        # a new exclusion must take effect now, not whenever a day next
        # happens to have new history in it.
        await self._async_prune(entity_ids)

        today = dt_util.start_of_local_day()
        query_start = dt_util.start_of_local_day(
            today - dt.timedelta(days=self._backfill_days())
        )
        # Never fold the oldest day we can query. It sits on the recorder's
        # purge horizon, where the row that last turned something off may
        # already be gone — which makes the whole day read as on-from-midnight
        # for every entity at once. It is only good enough to carry state in.
        window_start = dt_util.start_of_local_day(
            query_start + dt.timedelta(days=1, hours=1)
        )
        start = window_start

        if (last_day := self._data.get("last_day")) is not None:
            resume = dt_util.start_of_local_day(
                dt.datetime.fromisoformat(last_day)
            ) + dt.timedelta(days=1)
            start = max(start, resume)

        # Entities with nothing stored — just installed, or just un-excluded —
        # get the whole window instead of only the days since the last run.
        # Otherwise a light added today learns a single day while everything
        # around it has nine, and stays wrong for weeks.
        newcomers = set(entity_ids) - set(self.profile)

        if start >= today and not newcomers:
            _LOGGER.info(
                "Nothing to learn: everything up to %s is already folded in, and "
                "today is not over yet",
                self.last_day,
            )
            return

        states = await get_instance(self.hass).async_add_executor_job(
            lambda: history.get_significant_states(
                self.hass,
                dt_util.as_utc(query_start),
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
        seen: set[str] = set()
        day_start = window_start if newcomers else start
        while day_start < today:
            for entity_id, entity_changes in changes.items():
                # Days before the resume point exist only to backfill the
                # newcomers; folding them again for everyone else would count
                # the same evening twice.
                if day_start < start and entity_id not in newcomers:
                    continue
                if (grid := day_grid(entity_changes, day_start)) is None:
                    continue
                week = self.profile.setdefault(entity_id, empty_week())
                week[day_start.weekday()] = fold(week[day_start.weekday()], grid)
                seen.add(entity_id)
            # Not timedelta(days=1) on a naive clock: DST days are 23h or 25h,
            # and start_of_local_day keeps every day anchored to real midnight.
            day_start = dt_util.start_of_local_day(day_start + dt.timedelta(days=1, hours=1))
            days += 1

        self._data["last_day"] = (today - dt.timedelta(days=1)).date().isoformat()
        await self._store.async_save(self._data)
        async_dispatcher_send(self.hass, SIGNAL_PROFILE_UPDATED)

        if seen:
            _LOGGER.info(
                "Learned %s day(s) of history for %s of %s entities, up to %s%s",
                days,
                len(seen),
                len(entity_ids),
                self.last_day,
                f" (backfilled {len(newcomers)} new)" if newcomers else "",
            )
        else:
            _LOGGER.warning(
                "Learned nothing: the recorder returned no history for any of the "
                "%s entities between %s and %s. Is recorder excluding them?",
                len(entity_ids),
                start.date(),
                today.date(),
            )

    async def _async_prune(self, entity_ids: list[str]) -> None:
        """Forget entities that left the registry, a group, or the user's list."""
        if not (gone := set(self.profile) - set(entity_ids)):
            return

        for entity_id in gone:
            del self.profile[entity_id]
        await self._store.async_save(self._data)
        async_dispatcher_send(self.hass, SIGNAL_PROFILE_UPDATED)
        _LOGGER.info(
            "Forgot %s entit%s no longer worth replaying: %s",
            len(gone),
            "y" if len(gone) == 1 else "ies",
            ", ".join(sorted(gone)),
        )

    async def async_forget(self) -> None:
        """Throw the whole profile away and learn it again from scratch.

        Needed whenever a change to the maths invalidates what is stored: the
        moving average would otherwise blend old and new meanings together for
        weeks. Without this the only cure is deleting a hidden file by hand.
        """
        entities = len(self.profile)
        self._data = {"last_day": None, "entities": {}}
        await self._store.async_remove()
        async_dispatcher_send(self.hass, SIGNAL_PROFILE_UPDATED)
        _LOGGER.info("Forgot the profile (%s entities); relearning now", entities)
        await self.async_update()

    async def async_safe_update(self, _arg: Any = None) -> None:
        """Run a fold without ever taking the integration down with it."""
        try:
            await self.async_update()
        except Exception:  # noqa: BLE001 - a bad night must not kill the entry
            _LOGGER.exception("Learning run failed")


async def async_setup_learner(hass: HomeAssistant, entry: ConfigEntry) -> Learner:
    """Load the profile, schedule the catch-up and the nightly run.

    The catch-up waits for HA to have started rather than running inline: a
    history query is slow, and a failing one must not stop the entry loading.
    """
    learner = Learner(hass, entry)
    await learner.async_load()

    async_at_started(hass, learner.async_safe_update)
    hass.data[DOMAIN]["unsub_learn"] = async_track_time_change(
        hass, learner.async_safe_update, hour=LEARN_HOUR, minute=LEARN_MINUTE, second=0
    )
    return learner
