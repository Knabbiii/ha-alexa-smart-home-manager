"""Button: resend every exposed entity to Alexa."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import entity_manager
from .entity import AlexaBridgeManagerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the resync button."""
    async_add_entities([AlexaResyncButton(entry)])


class AlexaResyncButton(AlexaBridgeManagerEntity, ButtonEntity):
    """Force a full AddOrUpdateReport, e.g. after Alexa lost its devices."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(entry, "resync")

    async def async_press(self) -> None:
        """Resend all exposed entities to Alexa."""
        await entity_manager.async_sync_discovery(self.hass, self._entry, force=True)
