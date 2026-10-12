"""Sensor: result of the last discovery sync with Alexa."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import entity_manager
from .const import STATUS_ERROR, STATUS_NOT_LINKED, STATUS_PENDING, STATUS_SYNCED
from .entity import AlexaBridgeManagerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sync status sensor."""
    async_add_entities([AlexaSyncStatusSensor(hass, entry)])


class AlexaSyncStatusSensor(AlexaBridgeManagerEntity, SensorEntity):
    """Whether Alexa knows the entities Home Assistant currently exposes."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [STATUS_NOT_LINKED, STATUS_PENDING, STATUS_SYNCED, STATUS_ERROR]

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(entry, "sync_status")
        self._hass = hass

    @property
    def native_value(self) -> str:
        """Return the sync state."""
        return entity_manager.get_status(self._hass).state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return when the last sync worked and what went wrong otherwise."""
        status = entity_manager.get_status(self._hass)
        return {"last_success": status.last_success, "last_error": status.error}
