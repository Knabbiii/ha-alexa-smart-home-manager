"""Shared base entity for Alexa Bridge Manager."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_STATUS_UPDATED


class AlexaBridgeManagerEntity(Entity):
    """Base class: one service device, refreshed on every sync status change."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, key: str) -> None:
        """Initialize the entity for a config entry."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Alexa Bridge Manager",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Refresh whenever the link or sync status changes."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_STATUS_UPDATED, self._handle_status_update
            )
        )

    @callback
    def _handle_status_update(self) -> None:
        self.async_write_ha_state()
