"""Config flow for Ghost Mode."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlowWithReload
from homeassistant.helpers import selector

from .const import CONF_EXCLUDE, CONF_PASTE, DOMAIN
from .discovery import GHOSTABLE_DOMAINS, parse_entity_ids


class GhostModeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-instance setup, no questions: entities come from the registry."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Confirm and create the single Ghost Mode entry."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Ghost Mode", data={})

        return self.async_show_form(step_id="user")

    @staticmethod
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlowWithReload:
        """Return the options flow."""
        return GhostModeOptionsFlow()


class GhostModeOptionsFlow(OptionsFlowWithReload):
    """Only one option, and only because discovery cannot read minds.

    Some integrations ship permanently-on config switches without marking them
    as such (a vacuum's UV lamp setting, say). Those are noise a passer-by
    never sees, so they need a way out.

    `OptionsFlowWithReload` reloads the entry for us when the options change —
    which is why there is no update listener anywhere in this integration.
    """

    async def async_step_init(self, user_input=None):
        """Let the user exclude entities from learning and replay."""
        if user_input is not None:
            # The paste box is a bulk-add, not a second list: whatever it
            # contains is merged into the picker and then forgotten, so
            # reopening the form shows one list rather than two.
            excluded = set(user_input.get(CONF_EXCLUDE, []))
            excluded |= parse_entity_ids(user_input.get(CONF_PASTE, ""))
            return self.async_create_entry(data={CONF_EXCLUDE: sorted(excluded)})

        current = self.config_entry.options.get(CONF_EXCLUDE, [])
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_EXCLUDE, default=current): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=sorted(GHOSTABLE_DOMAINS), multiple=True
                        )
                    ),
                    vol.Optional(CONF_PASTE, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    ),
                }
            ),
        )
