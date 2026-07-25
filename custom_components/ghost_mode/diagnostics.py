"""Diagnostics: what the learner has actually recorded.

Settings -> Devices & Services -> Ghost Mode -> ... -> Download diagnostics.
Beats hunting for a dotfile under `.storage`, and it is what to attach to a
bug report.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_EXCLUDE, DOMAIN
from .discovery import GHOSTABLE_DOMAINS
from .rhythm import SLOT_MINUTES, WEEKDAYS, sparkline

LEGEND = (
    "One character per 30 minutes, local midnight first, showing how much of "
    "that half hour the entity was on: '·' none, '▁' briefly, '▃'/'▅' partly, "
    "'█' all of it."
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return the learned rhythm, readable rather than raw.

    ponytail: sparklines only. The underlying floats are 336 numbers per
    entity — same information, fifty times the download, unreadable either
    way. Read `.storage/ghost_mode.profile` if you need the exact values.
    """
    learner = hass.data[DOMAIN]["learner"]
    profile = learner.profile
    discovered = learner.entity_ids

    return {
        "last_learned_day": learner.last_day,
        "legend": LEGEND,
        "slot_minutes": SLOT_MINUTES,
        "entities_discovered": len(discovered),
        "entities_learned": len(profile),
        # Discovered but never seen in history: usually recorder excludes them,
        # or they simply have not changed state yet.
        "discovered_but_unlearned": sorted(set(discovered) - set(profile)),
        "domains_watched": sorted(GHOSTABLE_DOMAINS),
        "excluded_by_user": sorted(entry.options.get(CONF_EXCLUDE, [])),
        "rhythm": {
            entity_id: {
                WEEKDAYS[weekday]: sparkline(day)
                for weekday, day in enumerate(week)
            }
            for entity_id, week in sorted(profile.items())
        },
    }
