"""The Ghost Mode integration.

Learns how the home looks while occupied and replays that pattern while away,
so an empty house still looks lived-in. This module wires up the entry and the
nightly learner; the replay engine lands in a later version.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN
from .learner import async_setup_learner

PLATFORMS = ["switch"]

SERVICE_LEARN_NOW = "learn_now"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ghost Mode from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    learner = await async_setup_learner(hass)
    hass.data[DOMAIN]["learner"] = learner

    async def _learn_now(_call: ServiceCall) -> None:
        """Fold history in right now instead of waiting for tonight."""
        await learner.async_update()

    hass.services.async_register(DOMAIN, SERVICE_LEARN_NOW, _learn_now)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.services.async_remove(DOMAIN, SERVICE_LEARN_NOW)
        if (unsub := hass.data[DOMAIN].pop("unsub_learn", None)) is not None:
            unsub()
        hass.data[DOMAIN].pop("learner", None)
    return unloaded
