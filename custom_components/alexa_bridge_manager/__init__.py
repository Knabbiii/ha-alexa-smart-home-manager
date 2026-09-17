"""The Alexa Bridge Manager integration.

Sets up a config-entry-backed replacement for the manual
`alexa: smart_home:` YAML configuration (see entity_manager.py for why and
how). Options flow changes take effect immediately - no HA restart, and no
reload of this config entry is required for entity exposure to update.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import entity_manager
from .const import DOMAIN, ISSUE_SMART_HOME_CONFLICT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Alexa Bridge Manager from a config entry."""
    try:
        await entity_manager.async_setup_runtime(hass, entry)
    except entity_manager.SmartHomeEndpointConflict:
        ir.async_create_issue(
            hass,
            DOMAIN,
            ISSUE_SMART_HOME_CONFLICT,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_SMART_HOME_CONFLICT,
        )
        _LOGGER.error(
            "Cannot set up Alexa Bridge Manager: /api/alexa/smart_home is "
            "already registered, likely by an `alexa: smart_home:` block in "
            "configuration.yaml. Remove it, then reload this integration."
        )
        return False

    ir.async_delete_issue(hass, DOMAIN, ISSUE_SMART_HOME_CONFLICT)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await entity_manager.async_sync_discovery(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    This intentionally does *not* tear down the registered Alexa HTTP view
    or runtime config - see entity_manager.async_teardown_runtime for why
    that only happens on actual removal.
    """
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of a config entry."""
    await entity_manager.async_teardown_runtime(hass, entry)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Push an Alexa discovery update after the options flow saves changes."""
    await entity_manager.async_sync_discovery(hass, entry)
