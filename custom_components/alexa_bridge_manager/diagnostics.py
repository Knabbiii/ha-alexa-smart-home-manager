"""Diagnostics support for Alexa Bridge Manager.

Doubles as the "how many entities are exposed" overview requested for this
integration: Settings -> Devices & services -> Alexa Bridge Manager -> the
entry's "..." menu -> Download diagnostics.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENTITY_NAMES,
    CONF_EXPOSED_ENTITIES,
)

TO_REDACT = {CONF_CLIENT_ID, CONF_CLIENT_SECRET}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    exposed: list[str] = entry.options.get(CONF_EXPOSED_ENTITIES, [])
    names: dict[str, str] = entry.options.get(CONF_ENTITY_NAMES, {})

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "exposed_entity_count": len(exposed),
        "custom_named_entity_count": len(names),
        "exposed_entities": sorted(exposed),
    }
