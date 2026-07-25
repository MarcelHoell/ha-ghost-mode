"""Ghost Mode master switch.

For now this only holds on/off state and survives restarts. When it is on and
the house is away, the (future) engine will replay learned patterns. Keeping it
as a real switch entity means automations and the alarm can flip it today.
"""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, SIGNAL_ENABLED


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ghost Mode switch."""
    async_add_entities([GhostModeSwitch(entry)])


class GhostModeSwitch(SwitchEntity, RestoreEntity):
    """The master on/off for Ghost Mode."""

    _attr_has_entity_name = True
    _attr_name = None  # the entity carries the device name
    _attr_icon = "mdi:ghost"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the switch."""
        self._attr_unique_id = f"{entry.entry_id}_enabled"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Ghost Mode",
            manufacturer="Marcel Höll",
        )
        self._is_on = False

    async def async_added_to_hass(self) -> None:
        """Restore the last known state after a restart."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._is_on = last_state.state == "on"
        self._publish()

    @property
    def is_on(self) -> bool:
        """Return whether Ghost Mode is enabled."""
        return self._is_on

    def _publish(self) -> None:
        """Tell replay at once, rather than let it find out on its next tick."""
        self.hass.data[DOMAIN]["enabled"] = self._is_on
        async_dispatcher_send(self.hass, SIGNAL_ENABLED)

    async def async_turn_on(self, **kwargs) -> None:
        """Enable Ghost Mode."""
        self._is_on = True
        self.async_write_ha_state()
        self._publish()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable Ghost Mode."""
        self._is_on = False
        self.async_write_ha_state()
        self._publish()
