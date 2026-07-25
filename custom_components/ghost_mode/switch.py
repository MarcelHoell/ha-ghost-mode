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
    """Set up the Ghost Mode switches."""
    async_add_entities([GhostModeSwitch(entry), GhostModeForceSwitch(entry)])


class _GhostModeSwitchBase(SwitchEntity, RestoreEntity):
    """Shared plumbing: remember the state, and tell replay at once."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    #: Key in `hass.data[DOMAIN]` this switch publishes to.
    _key: str

    def __init__(self, entry: ConfigEntry, unique_suffix: str) -> None:
        """Initialize the switch."""
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
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
        self.hass.data[DOMAIN][self._key] = self._is_on
        async_dispatcher_send(self.hass, SIGNAL_ENABLED)

    async def async_turn_on(self, **kwargs) -> None:
        """Switch on."""
        self._is_on = True
        self.async_write_ha_state()
        self._publish()

    async def async_turn_off(self, **kwargs) -> None:
        """Switch off."""
        self._is_on = False
        self.async_write_ha_state()
        self._publish()


class GhostModeSwitch(_GhostModeSwitchBase):
    """The master on/off: replay may act, if the alarm also agrees."""

    _attr_name = None  # the entity carries the device name
    _attr_icon = "mdi:ghost"
    _key = "enabled"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the master switch."""
        super().__init__(entry, "enabled")


class GhostModeForceSwitch(_GhostModeSwitchBase):
    """Replay now, whatever the alarm says.

    The alarm is the right signal almost always, and exactly wrong when you
    want to see what replay does, or when you are away without arming it.
    """

    _attr_translation_key = "force"
    _attr_icon = "mdi:play-circle"
    _key = "forced"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the force switch."""
        super().__init__(entry, "forced")
