"""Which entities Ghost Mode learns from and replays.

No picker, no config: the entity registry already knows what exists and which
of it is user-facing. Anything switchable that a person would notice is fair
game; config and diagnostic entities are not.
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

# ponytail: a domain allowlist, not a supported-features probe. These are the
# domains whose on/off state reads as "someone is home" from the street.
GHOSTABLE_DOMAINS = {
    "light",
    "switch",
    "fan",
    "media_player",
    "cover",
    "input_boolean",
}


@callback
def ghostable_entities(hass: HomeAssistant) -> list[str]:
    """Return every entity worth learning from, newest registry state."""
    return sorted(
        entry.entity_id
        for entry in er.async_get(hass).entities.values()
        if entry.domain in GHOSTABLE_DOMAINS
        and not entry.disabled_by
        and not entry.hidden_by
        # entity_category is set on config/diagnostic entities: the "LED
        # indicator" and "child lock" switches every Zigbee device ships.
        and entry.entity_category is None
    )
