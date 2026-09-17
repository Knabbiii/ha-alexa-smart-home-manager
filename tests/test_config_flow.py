"""Tests for the Alexa Bridge Manager config and options flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alexa_bridge_manager.const import (
    CLIENT_ID_PREFIX,
    CLIENT_SECRET_PREFIX,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENDPOINT,
    CONF_ENTITY_NAMES,
    CONF_EXPOSED_ENTITIES,
    DOMAIN,
    ENDPOINT_CUSTOM,
    ENDPOINT_EU,
)

# Built from the prefix constant at runtime (not a literal secret-shaped
# string in source) so GitHub's push protection does not flag it.
VALID_CLIENT_ID = CLIENT_ID_PREFIX + "test-fixture-not-a-real-id"
VALID_CLIENT_SECRET = CLIENT_SECRET_PREFIX + "test-fixture-not-a-real-secret"


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """A valid endpoint/client_id/client_secret creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.alexa_bridge_manager.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ENDPOINT: ENDPOINT_EU,
                CONF_CLIENT_ID: VALID_CLIENT_ID,
                CONF_CLIENT_SECRET: VALID_CLIENT_SECRET,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ENDPOINT] == ENDPOINT_EU
    assert result["data"][CONF_CLIENT_ID] == VALID_CLIENT_ID
    assert result["data"][CONF_CLIENT_SECRET] == VALID_CLIENT_SECRET


async def test_user_flow_invalid_client_id(hass: HomeAssistant) -> None:
    """A client_id without the expected prefix is rejected with an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ENDPOINT: ENDPOINT_EU,
            CONF_CLIENT_ID: "not-a-valid-client-id",
            CONF_CLIENT_SECRET: VALID_CLIENT_SECRET,
        },
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"][CONF_CLIENT_ID] == "invalid_client_id"


async def test_user_flow_invalid_client_secret(hass: HomeAssistant) -> None:
    """A client_secret without the expected prefix is rejected with an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ENDPOINT: ENDPOINT_EU,
            CONF_CLIENT_ID: VALID_CLIENT_ID,
            CONF_CLIENT_SECRET: "not-a-valid-secret",
        },
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"][CONF_CLIENT_SECRET] == "invalid_client_secret"


async def test_user_flow_custom_endpoint(hass: HomeAssistant) -> None:
    """Selecting 'custom' asks for a URL and validates it starts with https://."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ENDPOINT: ENDPOINT_CUSTOM,
            CONF_CLIENT_ID: VALID_CLIENT_ID,
            CONF_CLIENT_SECRET: VALID_CLIENT_SECRET,
        },
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "custom_endpoint"

    # A non-https URL is rejected.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ENDPOINT: "http://insecure.example.com"}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"][CONF_ENDPOINT] == "invalid_endpoint"

    with patch(
        "custom_components.alexa_bridge_manager.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ENDPOINT: "https://custom.example.com/v3/events"}
        )
        await hass.async_block_till_done()

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ENDPOINT] == "https://custom.example.com/v3/events"


async def test_single_instance_allowed(hass: HomeAssistant) -> None:
    """A second config entry is refused - the skill only has one endpoint."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ENDPOINT: ENDPOINT_EU,
            CONF_CLIENT_ID: VALID_CLIENT_ID,
            CONF_CLIENT_SECRET: VALID_CLIENT_SECRET,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ENDPOINT: ENDPOINT_EU,
            CONF_CLIENT_ID: VALID_CLIENT_ID,
            CONF_CLIENT_SECRET: VALID_CLIENT_SECRET,
        },
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.alexa_bridge_manager.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_options_flow_expose_and_name_entity(hass: HomeAssistant) -> None:
    """Picking an entity in the selector and naming it saves into the options."""
    entry = await _setup_entry(hass)
    hass.states.async_set("light.donut_led", "on", {"friendly_name": "Donut LED"})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_EXPOSED_ENTITIES: ["light.donut_led"]}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "names"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"light.donut_led": "Donut"}
    )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_EXPOSED_ENTITIES] == ["light.donut_led"]
    assert result["data"][CONF_ENTITY_NAMES] == {"light.donut_led": "Donut"}


async def test_options_flow_no_entities_selected_saves_empty(
    hass: HomeAssistant,
) -> None:
    """Submitting the selector with nothing picked skips straight to saving."""
    entry = await _setup_entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_EXPOSED_ENTITIES: []}
    )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_EXPOSED_ENTITIES] == []
    assert result["data"][CONF_ENTITY_NAMES] == {}


async def test_options_flow_rejects_duplicate_names(hass: HomeAssistant) -> None:
    """Finishing with two entities sharing an Alexa name shows an error."""
    entry = await _setup_entry(hass)
    hass.states.async_set("light.a", "on", {"friendly_name": "A"})
    hass.states.async_set("light.b", "on", {"friendly_name": "B"})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_EXPOSED_ENTITIES: ["light.a", "light.b"]}
    )
    assert result["step_id"] == "names"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"light.a": "Lampe", "light.b": "Lampe"}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "names"
    assert result["errors"]["base"] == "duplicate_names"

    # Fixing the collision on the same (looped-back) page now saves fine.
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"light.a": "Lampe", "light.b": "Andere Lampe"}
    )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ENTITY_NAMES] == {
        "light.a": "Lampe",
        "light.b": "Andere Lampe",
    }


async def test_options_flow_paginates_names_across_many_entities(
    hass: HomeAssistant,
) -> None:
    """More than one page of selected entities are asked for one page at a time."""
    entry = await _setup_entry(hass)
    entity_ids = [f"light.l{i}" for i in range(12)]
    for entity_id in entity_ids:
        hass.states.async_set(entity_id, "on")

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_EXPOSED_ENTITIES: entity_ids}
    )
    assert result["step_id"] == "names"
    assert result["description_placeholders"]["page"] == "1"
    assert result["description_placeholders"]["total_pages"] == "2"

    # First page (10 entities) - leave all names blank.
    first_page_fields = {
        str(key) for key in result["data_schema"].schema.keys()
    }
    assert len(first_page_fields) == 10

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "names"
    assert result["description_placeholders"]["page"] == "2"

    # Second (final) page - remaining 2 entities.
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {}
    )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_EXPOSED_ENTITIES] == entity_ids
