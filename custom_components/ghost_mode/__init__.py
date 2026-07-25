"""The Ghost Mode integration.

Learns how the home looks while occupied and replays that pattern while away,
so an empty house still looks lived-in. This module wires up the entry and the
nightly learner; the replay engine lands in a later version.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .learner import STORAGE_KEY, STORAGE_VERSION, async_setup_learner
from .replay import async_setup_replay

PLATFORMS = ["binary_sensor", "sensor", "switch"]

SERVICE_LEARN_NOW = "learn_now"
SERVICE_FORGET = "forget"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ghost Mode from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    learner = await async_setup_learner(hass, entry)
    hass.data[DOMAIN]["learner"] = learner

    async def _learn_now(_call: ServiceCall) -> None:
        """Fold history in right now instead of waiting for tonight."""
        await learner.async_update()

    async def _forget(_call: ServiceCall) -> None:
        """Throw the profile away and rebuild it from recorder history."""
        await learner.async_forget()

    hass.services.async_register(DOMAIN, SERVICE_LEARN_NOW, _learn_now)
    hass.services.async_register(DOMAIN, SERVICE_FORGET, _forget)

    hass.data[DOMAIN]["replay"] = await async_setup_replay(hass, entry, learner)

    # Changing the exclusion list reloads the entry: OptionsFlowWithReload
    # handles that, so there is deliberately no update listener here.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.services.async_remove(DOMAIN, SERVICE_LEARN_NOW)
        hass.services.async_remove(DOMAIN, SERVICE_FORGET)
        if (unsub := hass.data[DOMAIN].pop("unsub_learn", None)) is not None:
            unsub()
        for unsub in hass.data[DOMAIN].pop("unsub_replay", []):
            unsub()
        # Never leave the house mid-performance because of a reload.
        if (replay := hass.data[DOMAIN].pop("replay", None)) is not None:
            await replay.async_stand_down()
        hass.data[DOMAIN].pop("learner", None)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete the learned profile when the integration is removed.

    Without this the file survives in `.storage`, so removing Ghost Mode and
    adding it again silently restores months of old history — surprising, and
    not how an integration is meant to behave.
    """
    await Store(hass, STORAGE_VERSION, STORAGE_KEY).async_remove()
