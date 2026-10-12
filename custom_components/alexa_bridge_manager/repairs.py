"""Repair flows for Alexa Smart Home Manager."""
from __future__ import annotations

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant

from .const import CONF_ENTITY_NAMES, CONF_EXPOSED_ENTITIES


class MissingEntitiesRepairFlow(RepairsFlow):
    """Offer to stop exposing entities that no longer exist."""

    def __init__(self, entry_id: str, entities: list[str]) -> None:
        """Remember which entry and entities the issue is about."""
        self._entry_id = entry_id
        self._entities = entities

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Show the confirmation."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Remove the vanished entities from the exposed set."""
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                description_placeholders={"entities": ", ".join(self._entities)},
            )

        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is not None:
            gone = set(self._entities)
            self.hass.config_entries.async_update_entry(
                entry,
                options={
                    **entry.options,
                    CONF_EXPOSED_ENTITIES: [
                        eid
                        for eid in entry.options.get(CONF_EXPOSED_ENTITIES, [])
                        if eid not in gone
                    ],
                    CONF_ENTITY_NAMES: {
                        eid: name
                        for eid, name in entry.options.get(
                            CONF_ENTITY_NAMES, {}
                        ).items()
                        if eid not in gone
                    },
                },
            )
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the fix flow for a repair issue."""
    assert data is not None
    return MissingEntitiesRepairFlow(str(data["entry_id"]), list(data["entities"]))
