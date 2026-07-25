"""Says whether Ghost Mode is performing right now.

Without this a dashboard can only show the *conditions* for replay — switch
on, alarm armed — and leave you to infer the rest. That is a guess, not a
report, and it looks identical whether replay is lighting the house or has
nothing to do today.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_REPLAY


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the replaying indicator."""
    async_add_entities([GhostModeReplayingSensor(hass, entry)])


class GhostModeReplayingSensor(BinarySensorEntity):
    """On while replay is actually driving the house."""

    _attr_has_entity_name = True
    _attr_translation_key = "replaying"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_should_poll = False

    # The list changes as replay works and is only useful right now; keeping a
    # history of it would bloat the recorder for nothing.
    _unrecorded_attributes = frozenset({"restores_on_return"})

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._attr_unique_id = f"{entry.entry_id}_replaying"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Ghost Mode",
            manufacturer="Marcel Höll",
        )

    async def async_added_to_hass(self) -> None:
        """Redraw whenever replay starts, stops or changes what it holds."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_REPLAY, self._handle_update)
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def _replay(self):
        return self.hass.data[DOMAIN].get("replay")

    @property
    def is_on(self) -> bool:
        """Return whether replay is driving the house."""
        return bool(replay.is_running) if (replay := self._replay) else False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return what replay is holding, and why it is idle if it is."""
        if (replay := self._replay) is None:
            return {}
        held = replay.held
        return {
            "entities_held": len(held),
            "restores_on_return": held,
            # None while running, so an automation can key off "is it blocked".
            "waiting_for": replay.blocked_by(),
        }
