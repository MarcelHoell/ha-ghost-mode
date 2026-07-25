"""Config flow for Ghost Mode."""
from __future__ import annotations

from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN


class GhostModeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-instance setup, no options: entities come from the registry."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Confirm and create the single Ghost Mode entry."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Ghost Mode", data={})

        return self.async_show_form(step_id="user")
