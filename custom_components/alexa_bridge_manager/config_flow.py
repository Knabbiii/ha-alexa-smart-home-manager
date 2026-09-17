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
    BooleanSelector,
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

FINISH_SENTINEL = "__finish__"


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

    Navigation is a small state machine kept on `self` across steps:
    `async_step_init` shows a menu of domains (plus a "finish" choice);
    picking a domain drops into `async_step_entities_page`, which shows that
    domain's entities `ENTITIES_PER_PAGE` at a time (so this stays usable
    with hundreds of entities) and loops itself until the domain is
    exhausted, then returns to the domain menu. Nothing is written back to
    the config entry until "finish" is chosen, at which point duplicate
    Alexa names are rejected.
    """

    def __init__(self) -> None:
        """Initialize with no state - populated on first step_init call."""
        self._domains: dict[str, list[str]] = {}
        self._exposed: dict[str, bool] = {}
        self._names: dict[str, str] = {}
        self._current_domain: str | None = None
        self._current_page: int = 0

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the domain picker, or finish and save."""
        if not self._domains:
            self._domains = entity_manager.entities_by_domain(self.hass)
            exposed_list: list[str] = self.config_entry.options.get(
                CONF_EXPOSED_ENTITIES, []
            )
            self._exposed = {
                entity_id: entity_id in exposed_list
                for entity_ids in self._domains.values()
                for entity_id in entity_ids
            }
            self._names = dict(
                self.config_entry.options.get(CONF_ENTITY_NAMES, {})
            )

        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            domain = user_input["domain"]

            if domain == FINISH_SENTINEL:
                duplicates = entity_manager.find_duplicate_names(self._names)
                if duplicates:
                    errors["base"] = "duplicate_names"
                    description_placeholders["duplicates"] = "; ".join(
                        f"'{name}': {', '.join(ids)}"
                        for name, ids in duplicates.items()
                    )
                else:
                    return self.async_create_entry(
                        title="",
                        data={
                            CONF_EXPOSED_ENTITIES: [
                                entity_id
                                for entity_id, exposed in self._exposed.items()
                                if exposed
                            ],
                            CONF_ENTITY_NAMES: self._names,
                        },
                    )
            else:
                self._current_domain = domain
                self._current_page = 0
                return await self.async_step_entities_page()

        options = [
            {
                "value": domain,
                "label": (
                    f"{domain} "
                    f"({sum(1 for e in entity_ids if self._exposed.get(e))}/"
                    f"{len(entity_ids)} für Alexa freigegeben)"
                ),
            }
            for domain, entity_ids in self._domains.items()
        ]
        options.append(
            {"value": FINISH_SENTINEL, "label": "✅ Fertig – Änderungen speichern"}
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("domain"): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.LIST
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_entities_page(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show one page of entities for the currently selected domain."""
        assert self._current_domain is not None
        entity_ids = self._domains[self._current_domain]
        start = self._current_page * ENTITIES_PER_PAGE
        page_ids = entity_ids[start : start + ENTITIES_PER_PAGE]

        if user_input is not None:
            for entity_id in page_ids:
                self._exposed[entity_id] = bool(user_input.get(entity_id, False))
                name = str(user_input.get(f"{entity_id}_name", "")).strip()
                if name:
                    self._names[entity_id] = name
                else:
                    self._names.pop(entity_id, None)

            if start + ENTITIES_PER_PAGE < len(entity_ids):
                self._current_page += 1
                return await self.async_step_entities_page()

            return await self.async_step_init()

        schema_dict: dict[Any, Any] = {}
        for entity_id in page_ids:
            schema_dict[
                vol.Optional(entity_id, default=self._exposed.get(entity_id, False))
            ] = BooleanSelector()
            schema_dict[
                vol.Optional(
                    f"{entity_id}_name", default=self._names.get(entity_id, "")
                )
            ] = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))

        total_pages = max(1, -(-len(entity_ids) // ENTITIES_PER_PAGE))

        return self.async_show_form(
            step_id="entities_page",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "domain": self._current_domain,
                "page": str(self._current_page + 1),
                "total_pages": str(total_pages),
            },
        )
