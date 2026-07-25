"""Diagnostics: what the learner has actually recorded.

Settings -> Devices & Services -> Ghost Mode -> ... -> Download diagnostics.
Beats hunting for a dotfile under `.storage`, and it is what to attach to a
bug report.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .discovery import GHOSTABLE_DOMAINS, ghostable_entities
from .rhythm import SLOT_MINUTES, WEEKDAYS, sparkline

LEGEND = (
    "One character per 30 minutes, local midnight first. "
    "'·' off, '▪' sometimes on, '█' reliably on."
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return the learned rhythm, readable first and raw underneath."""
    learner = hass.data[DOMAIN]["learner"]
    profile = learner.profile
    discovered = ghostable_entities(hass)

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
        "rhythm": {
            entity_id: {
                WEEKDAYS[weekday]: sparkline(day)
                for weekday, day in enumerate(week)
            }
            for entity_id, week in sorted(profile.items())
        },
        "raw": profile,
    }
