"""Config flow for the Alexa Bridge Manager integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CLIENT_ID_PREFIX,
    CLIENT_SECRET_PREFIX,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENDPOINT,
    DOMAIN,
    ENDPOINT_CUSTOM,
    KNOWN_ENDPOINTS,
)

_LOGGER = logging.getLogger(__name__)


def _base_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the schema for the base (endpoint/client_id/client_secret) step."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_ENDPOINT, default=defaults.get(CONF_ENDPOINT)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=list(KNOWN_ENDPOINTS.keys()),
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="endpoint",
                )
            ),
            vol.Required(
                CONF_CLIENT_ID, default=defaults.get(CONF_CLIENT_ID, "")
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(
                CONF_CLIENT_SECRET, default=defaults.get(CONF_CLIENT_SECRET, "")
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        }
    )


def _custom_endpoint_schema(default: str = "") -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_ENDPOINT, default=default): TextSelector(
                TextSelectorConfig(type=TextSelectorType.URL)
            ),
        }
    )


def _validate_credentials(data: dict[str, Any]) -> dict[str, str]:
    """Validate client_id/client_secret format. Returns a dict of field -> error key."""
    errors: dict[str, str] = {}

    client_id = data.get(CONF_CLIENT_ID, "").strip()
    client_secret = data.get(CONF_CLIENT_SECRET, "").strip()

    if not client_id.startswith(CLIENT_ID_PREFIX):
        errors[CONF_CLIENT_ID] = "invalid_client_id"

    if not client_secret.startswith(CLIENT_SECRET_PREFIX):
        errors[CONF_CLIENT_SECRET] = "invalid_client_secret"

    return errors


class AlexaBridgeManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup of the Alexa Bridge Manager integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the base Alexa event gateway credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)

            if user_input[CONF_ENDPOINT] == ENDPOINT_CUSTOM:
                return await self.async_step_custom_endpoint()

            errors = _validate_credentials(self._data)
            if not errors:
                return await self._async_create_entry()

        return self.async_show_form(
            step_id="user",
            data_schema=_base_schema(self._data),
            errors=errors,
        )

    async def async_step_custom_endpoint(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the custom endpoint URL when 'custom' was selected."""
        errors: dict[str, str] = {}

        if user_input is not None:
            endpoint = user_input[CONF_ENDPOINT].strip()
            if not endpoint.startswith("https://"):
                errors[CONF_ENDPOINT] = "invalid_endpoint"
            else:
                self._data[CONF_ENDPOINT] = endpoint
                errors = _validate_credentials(self._data)
                if not errors:
                    return await self._async_create_entry()

        return self.async_show_form(
            step_id="custom_endpoint",
            data_schema=_custom_endpoint_schema(),
            errors=errors,
        )

    async def _async_create_entry(self) -> ConfigFlowResult:
        """Create the config entry, guarding against duplicate client_ids."""
        await self.async_set_unique_id(self._data[CONF_CLIENT_ID])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="Alexa Bridge Manager",
            data=self._data,
        )
