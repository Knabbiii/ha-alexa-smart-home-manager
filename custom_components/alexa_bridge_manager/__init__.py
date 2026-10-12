"""The Alexa Smart Home Manager integration.

Sets up a config-entry-backed replacement for the manual
`alexa: smart_home:` YAML configuration (see entity_manager.py for why and
how). Options flow changes take effect immediately - no HA restart, and no
reload of this config entry is required for entity exposure to update.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.start import async_at_started

from . import entity_manager
from .const import DOMAIN, ISSUE_SMART_HOME_CONFLICT

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Alexa Smart Home Manager from a config entry."""
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
            "Cannot set up Alexa Smart Home Manager: /api/alexa/smart_home is "
            "already registered, likely by an `alexa: smart_home:` block in "
            "configuration.yaml. Remove it, then restart Home Assistant"
        )
        return False

    ir.async_delete_issue(hass, DOMAIN, ISSUE_SMART_HOME_CONFLICT)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    entry.async_on_unload(
        hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            callback(lambda event: _async_registry_updated(hass, entry, event)),
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await entity_manager.async_sync_discovery(hass, entry)

    # Entity states are not loaded yet while Home Assistant is still starting,
    # so only look for vanished entities once everything is up.
    entry.async_on_unload(
        async_at_started(
            hass,
            callback(
                lambda hass: entity_manager.async_update_missing_entities_issue(
                    hass, entry
                )
            ),
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    This intentionally does *not* tear down the registered Alexa HTTP view
    or runtime config - aiohttp cannot unregister a view, so see
    entity_manager.async_teardown_runtime for why that only happens on
    actual removal.
    """
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of a config entry."""
    await entity_manager.async_teardown_runtime(hass, entry)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Push an Alexa discovery update after the options flow saves changes."""
    entity_manager.async_update_missing_entities_issue(hass, entry)
    await entity_manager.async_sync_discovery(hass, entry)


@callback
def _async_registry_updated(
    hass: HomeAssistant, entry: ConfigEntry, event: Event
) -> None:
    """React to entities being renamed or removed in Home Assistant."""
    data = event.data
    action = data["action"]
    if action == "update" and (old_entity_id := data.get("old_entity_id")):
        entity_manager.async_handle_entity_renamed(
            hass, entry, old_entity_id, data["entity_id"]
        )
    elif action == "remove":
        entity_manager.async_update_missing_entities_issue(hass, entry)
