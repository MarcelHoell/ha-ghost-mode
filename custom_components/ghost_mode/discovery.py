"""Which entities Ghost Mode learns from and replays.

No picker by default: the entity registry already knows what exists and which
of it is user-facing. Anything switchable that a person would notice is fair
game; config and diagnostic entities are not, groups stand in for their
members, and the options flow can exclude whatever is left over.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .rhythm import collapse_groups

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


# Deliberately forgiving: anything shaped like an entity id counts, so a list
# pasted with commas, bullets, quotes or line breaks all work the same.
_ENTITY_ID = re.compile(r"[a-z_]+\.[a-z0-9_]+")


def parse_entity_ids(text: str) -> set[str]:
    """Pull entity ids out of whatever the user pasted.

    The picker takes one click per entity, which is unusable for the case that
    actually matters — dropping the eight entities a single television owns.
    """
    return set(_ENTITY_ID.findall(text.lower()))


@callback
def ghostable_entities(
    hass: HomeAssistant, exclude: Iterable[str] = ()
) -> list[str]:
    """Return every entity worth learning from, newest registry state."""
    candidates = {
        entry.entity_id
        for entry in er.async_get(hass).entities.values()
        if entry.domain in GHOSTABLE_DOMAINS
        and not entry.disabled_by
        and not entry.hidden_by
        # entity_category is set on config/diagnostic entities: the "LED
        # indicator" and "child lock" switches every Zigbee device ships.
        and entry.entity_category is None
        # Never learn from, or replay, our own switch.
        and entry.platform != DOMAIN
    }
    candidates -= set(exclude)

    # A group entity lists its members in the `entity_id` attribute.
    members_by_group = {
        state.entity_id: list(members)
        for state in hass.states.async_all(GHOSTABLE_DOMAINS)
        if isinstance(members := state.attributes.get("entity_id"), (list, tuple))
    }
    return sorted(collapse_groups(candidates, members_by_group))
