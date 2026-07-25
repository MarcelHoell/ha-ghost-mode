"""Exposes the learned rhythm so a Lovelace card can draw it.

The diagnostics download is for debugging; this is for looking at. One sensor
carries the whole profile as sparklines in an attribute, which a plain
markdown card can render — no custom card, no JavaScript, no frontend
resource to install.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_PROFILE_UPDATED
from .rhythm import WEEKDAYS, sparkline, varies


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the learned-rhythm sensor."""
    async_add_entities([GhostModeProfileSensor(hass, entry)])


class GhostModeProfileSensor(SensorEntity):
    """How many entities have a rhythm worth replaying, plus the rhythm."""

    _attr_has_entity_name = True
    _attr_translation_key = "profile"
    _attr_icon = "mdi:chart-timeline-variant"
    _attr_native_unit_of_measurement = "entities"
    _attr_should_poll = False

    # The rhythm is kilobytes of text that changes once a night. Storing it in
    # the recorder every time would bloat the database for nothing.
    _unrecorded_attributes = frozenset({"rhythm"})

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._attr_unique_id = f"{entry.entry_id}_profile"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Ghost Mode",
            manufacturer="Marcel Höll",
        )

    async def async_added_to_hass(self) -> None:
        """Redraw whenever the learner has folded a night in."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_PROFILE_UPDATED, self._handle_update
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def _interesting(self) -> dict[str, list[list[float] | None]]:
        """Return only entities whose week actually varies.

        An entity that is off all week — or a vacuum setting that is on all
        week — tells a viewer nothing and would trible the size of the
        attribute. They stay in the profile, they just do not get drawn.
        """
        learner = self.hass.data[DOMAIN].get("learner")
        if learner is None:
            return {}
        return {
            entity_id: week
            for entity_id, week in learner.profile.items()
            if varies(week)
        }

    @property
    def native_value(self) -> int:
        """Return how many entities have something worth showing."""
        return len(self._interesting)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the drawable rhythm, one string per weekday."""
        learner = self.hass.data[DOMAIN].get("learner")
        return {
            "last_learned_day": learner.last_day if learner else None,
            "legend": "· off   ▁ briefly   ▃ ▅ partly   █ on",
            "rhythm": {
                entity_id: {
                    WEEKDAYS[weekday]: sparkline(day)
                    for weekday, day in enumerate(week)
                }
                for entity_id, week in sorted(self._interesting.items())
            },
        }
