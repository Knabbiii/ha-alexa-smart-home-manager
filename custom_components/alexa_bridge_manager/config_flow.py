"""Config flow for the Alexa Bridge Manager integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import entity_manager
from .const import (
    CLIENT_ID_PREFIX,
    CLIENT_SECRET_PREFIX,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENDPOINT,
    CONF_ENTITY_NAMES,
    CONF_EXPOSED_ENTITIES,
    DOMAIN,
    ENDPOINT_CUSTOM,
    ENTITIES_PER_PAGE,
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

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AlexaBridgeManagerOptionsFlow:
        """Return the options flow for managing exposed entities."""
        return AlexaBridgeManagerOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the base Alexa event gateway credentials."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

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


class AlexaBridgeManagerOptionsFlow(OptionsFlow):
    """Manage which entities are exposed to Alexa, and their Alexa names.

    Two steps only, regardless of how many entities exist:

    `async_step_init` shows a single native `EntitySelector` in multi-select
    mode - a searchable, filterable picker (not a scrolling checkbox list)
    that already knows every entity's domain and friendly name. Whatever the
    user picks there becomes the exposed set.

    `async_step_names` then walks *only* that (typically much smaller)
    selection, `ENTITIES_PER_PAGE` at a time, asking for an optional Alexa
    name per entity. Submitting the last page is the save - there is no
    separate "finish" menu to find. If two entities end up sharing a name,
    the flow loops back to the first naming page with an error instead of
    creating the entry, so the fix-up happens in the same place the name
    was set.
    """

    def __init__(self) -> None:
        """Initialize with no state - populated on first step_init call."""
        self._selected: list[str] = []
        self._names: dict[str, str] = {}
        self._current_page: int = 0

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick which entities are exposed to Alexa."""
        if user_input is not None:
            self._selected = user_input[CONF_EXPOSED_ENTITIES]
            self._names = {
                entity_id: name
                for entity_id, name in self.config_entry.options.get(
                    CONF_ENTITY_NAMES, {}
                ).items()
                if entity_id in self._selected
            }
            self._current_page = 0

            if not self._selected:
                return self.async_create_entry(
                    title="",
                    data={CONF_EXPOSED_ENTITIES: [], CONF_ENTITY_NAMES: {}},
                )

            return await self.async_step_names()

        current_exposed = self.config_entry.options.get(CONF_EXPOSED_ENTITIES, [])
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EXPOSED_ENTITIES, default=current_exposed
                    ): EntitySelector(EntitySelectorConfig(multiple=True)),
                }
            ),
        )

    async def async_step_names(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for an optional Alexa name, one page of entities at a time."""
        start = self._current_page * ENTITIES_PER_PAGE
        page_ids = self._selected[start : start + ENTITIES_PER_PAGE]
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            for entity_id in page_ids:
                name = str(user_input.get(entity_id, "")).strip()
                if name:
                    self._names[entity_id] = name
                else:
                    self._names.pop(entity_id, None)

            if start + ENTITIES_PER_PAGE < len(self._selected):
                self._current_page += 1
                return await self.async_step_names()

            duplicates = entity_manager.find_duplicate_names(self._names)
            overlaps = entity_manager.find_overlapping_names(self._names)
            if not duplicates and not overlaps:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_EXPOSED_ENTITIES: self._selected,
                        CONF_ENTITY_NAMES: self._names,
                    },
                )

            # Loop back to the first page so the fix-up happens where the
            # names were entered, instead of a separate summary/error page.
            self._current_page = 0
            start = 0
            page_ids = self._selected[0:ENTITIES_PER_PAGE]
            if duplicates:
                errors["base"] = "duplicate_names"
                description_placeholders["duplicates"] = "; ".join(
                    f"'{name}': {', '.join(ids)}" for name, ids in duplicates.items()
                )
            else:
                errors["base"] = "overlapping_names"
                description_placeholders["overlaps"] = "; ".join(
                    f"'{shorter}' in '{longer}'"
                    for _shorter_id, shorter, _longer_id, longer in overlaps
                )

        schema_dict: dict[Any, Any] = {
            vol.Optional(
                entity_id, default=self._names.get(entity_id, "")
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
            for entity_id in page_ids
        }

        total_pages = max(1, -(-len(self._selected) // ENTITIES_PER_PAGE))

        return self.async_show_form(
            step_id="names",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={
                "page": str(self._current_page + 1),
                "total_pages": str(total_pages),
                **description_placeholders,
            },
        )
