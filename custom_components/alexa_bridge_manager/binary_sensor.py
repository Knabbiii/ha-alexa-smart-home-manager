"""Binary sensor: is the Alexa skill account-linked?"""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_RUNTIME_CONFIG, DOMAIN
from .entity import AlexaBridgeManagerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the linked sensor."""
    async_add_entities([AlexaLinkedSensor(hass, entry)])


class AlexaLinkedSensor(AlexaBridgeManagerEntity, BinarySensorEntity):
    """On once Alexa has completed account linking (AcceptGrant received)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(entry, "linked")
        self._config = hass.data[DOMAIN][DATA_RUNTIME_CONFIG]

    @property
    def is_on(self) -> bool:
        """Return True if the skill is linked."""
        return bool(self._config.authorized)
