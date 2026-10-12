"""Tests for the full integration lifecycle: setup, entities, repairs, renames."""
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alexa_bridge_manager import entity_manager
from custom_components.alexa_bridge_manager.const import (
    CLIENT_ID_PREFIX,
    CLIENT_SECRET_PREFIX,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENDPOINT,
    CONF_ENTITY_NAMES,
    CONF_EXPOSED_ENTITIES,
    DATA_RUNTIME_CONFIG,
    DOMAIN,
    ENDPOINT_EU,
    ISSUE_MISSING_ENTITIES,
    ISSUE_SMART_HOME_CONFLICT,
    STATUS_NOT_LINKED,
    STATUS_SYNCED,
)
from custom_components.alexa_bridge_manager.repairs import async_create_fix_flow

VALID_CLIENT_ID = CLIENT_ID_PREFIX + "test-fixture-not-a-real-id"
VALID_CLIENT_SECRET = CLIENT_SECRET_PREFIX + "test-fixture-not-a-real-secret"

SEND_ADD = "custom_components.alexa_bridge_manager.entity_manager.async_send_add_or_update_message"
SEND_DELETE = "custom_components.alexa_bridge_manager.entity_manager.async_send_delete_message"


def _make_entry(hass: HomeAssistant, options: dict | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ENDPOINT: ENDPOINT_EU,
            CONF_CLIENT_ID: VALID_CLIENT_ID,
            CONF_CLIENT_SECRET: VALID_CLIENT_SECRET,
        },
        options=options or {},
    )
    entry.add_to_hass(hass)
    return entry


def _linked(linked: bool):
    return patch.object(
        entity_manager.AlexaBridgeManagerConfig,
        "authorized",
        new_callable=lambda: property(lambda self: linked),
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    with patch.object(
        entity_manager, "_smart_home_endpoint_registered", return_value=False
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_setup_creates_status_entities_and_unloads(hass: HomeAssistant) -> None:
    """Setup registers the three entities; unloading keeps the runtime alive."""
    entry = _make_entry(hass)
    with _linked(False):
        await _setup(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    registry = er.async_get(hass)
    linked = registry.async_get_entity_id("binary_sensor", DOMAIN, f"{entry.entry_id}_linked")
    status = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_sync_status")
    button = registry.async_get_entity_id("button", DOMAIN, f"{entry.entry_id}_resync")
    assert linked and status and button

    assert hass.states.get(linked).state == STATE_OFF
    assert hass.states.get(status).state == STATUS_NOT_LINKED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert DATA_RUNTIME_CONFIG in hass.data[DOMAIN]


async def test_setup_conflict_creates_repair(hass: HomeAssistant) -> None:
    """A YAML-owned endpoint fails setup and raises a Repair issue."""
    entry = _make_entry(hass)
    with patch.object(
        entity_manager, "_smart_home_endpoint_registered", return_value=True
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_SMART_HOME_CONFLICT)


async def test_resync_button_forces_full_report(hass: HomeAssistant) -> None:
    """Pressing the button resends everything even when nothing changed."""
    entry = _make_entry(hass, {CONF_EXPOSED_ENTITIES: ["light.a", "light.b"]})
    hass.states.async_set("light.a", STATE_ON)
    hass.states.async_set("light.b", STATE_ON)

    with _linked(True), patch(SEND_ADD, new=AsyncMock(return_value=Mock())) as mock_add, patch(
        SEND_DELETE, new=AsyncMock(return_value=Mock())
    ):
        await _setup(hass, entry)
        mock_add.reset_mock()

        button = er.async_get(hass).async_get_entity_id(
            "button", DOMAIN, f"{entry.entry_id}_resync"
        )
        await hass.services.async_call(
            "button", "press", {"entity_id": button}, blocking=True
        )

    mock_add.assert_awaited_once()
    assert mock_add.await_args.args[2] == ["light.a", "light.b"]
    status = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_sync_status"
    )
    assert hass.states.get(status).state == STATUS_SYNCED


async def test_rename_in_registry_moves_exposure_and_name(hass: HomeAssistant) -> None:
    """Renaming an exposed entity ID keeps it exposed under the new ID."""
    registry = er.async_get(hass)
    registry.async_get_or_create("light", "test", "1", suggested_object_id="old")
    entry = _make_entry(
        hass,
        {
            CONF_EXPOSED_ENTITIES: ["light.old", "light.other"],
            CONF_ENTITY_NAMES: {"light.old": "Reading Lamp"},
        },
    )
    with _linked(False):
        await _setup(hass, entry)

        registry.async_update_entity("light.old", new_entity_id="light.new")
        await hass.async_block_till_done()

    assert entry.options[CONF_EXPOSED_ENTITIES] == ["light.new", "light.other"]
    assert entry.options[CONF_ENTITY_NAMES] == {"light.new": "Reading Lamp"}


async def test_missing_entities_issue_and_fix(hass: HomeAssistant) -> None:
    """Exposed entities that vanished raise a fixable repair that prunes them."""
    hass.states.async_set("light.here", STATE_ON)
    entry = _make_entry(
        hass,
        {
            CONF_EXPOSED_ENTITIES: ["light.here", "light.gone"],
            CONF_ENTITY_NAMES: {"light.gone": "Ghost"},
        },
    )
    with _linked(False):
        await _setup(hass, entry)

        issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_MISSING_ENTITIES)
        assert issue is not None
        assert issue.is_fixable
        assert issue.data["entities"] == ["light.gone"]

        flow = await async_create_fix_flow(hass, ISSUE_MISSING_ENTITIES, issue.data)
        flow.hass = hass
        result = await flow.async_step_init()
        assert result["step_id"] == "confirm"
        result = await flow.async_step_confirm({})
        await hass.async_block_till_done()

    assert result["type"].value == "create_entry"
    assert entry.options[CONF_EXPOSED_ENTITIES] == ["light.here"]
    assert entry.options[CONF_ENTITY_NAMES] == {}
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_MISSING_ENTITIES) is None
