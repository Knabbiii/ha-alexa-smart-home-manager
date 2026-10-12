"""Diagnostics support for Alexa Bridge Manager.

Settings -> Devices & services -> Alexa Bridge Manager -> the entry's "..."
menu -> Download diagnostics.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import entity_manager
from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENTITY_NAMES,
    CONF_EXPOSED_ENTITIES,
    DATA_RUNTIME_CONFIG,
    DOMAIN,
)

TO_REDACT = {CONF_CLIENT_ID, CONF_CLIENT_SECRET}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    exposed: list[str] = entry.options.get(CONF_EXPOSED_ENTITIES, [])
    names: dict[str, str] = entry.options.get(CONF_ENTITY_NAMES, {})
    config = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME_CONFIG)
    status = entity_manager.get_status(hass)

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "exposed_entity_count": len(exposed),
        "custom_named_entity_count": len(names),
        "exposed_entities": sorted(exposed),
        "alexa_linked": bool(config and config.authorized),
        "sync_status": status.state,
        "last_successful_sync": (
            status.last_success.isoformat() if status.last_success else None
        ),
        "last_sync_error": status.error,
    }
