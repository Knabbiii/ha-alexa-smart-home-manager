"""Tests for entity_manager.py: the alexa.smart_home runtime wiring."""
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import HomeAssistant
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
    DATA_LAST_EXPOSED,
    DATA_RUNTIME_CONFIG,
    DOMAIN,
    ENDPOINT_EU,
)

# Built from the prefix constant at runtime (not a literal secret-shaped
# string in source) so GitHub's push protection does not flag it.
VALID_CLIENT_ID = CLIENT_ID_PREFIX + "test-fixture-not-a-real-id"
VALID_CLIENT_SECRET = CLIENT_SECRET_PREFIX + "test-fixture-not-a-real-secret"


def test_entities_by_domain_groups_and_sorts(hass: HomeAssistant) -> None:
    """Entities come back grouped by domain, each list sorted."""
    hass.states.async_set("light.b", "on")
    hass.states.async_set("light.a", "on")
    hass.states.async_set("switch.x", "off")

    grouped = entity_manager.entities_by_domain(hass)

    assert grouped["light"] == ["light.a", "light.b"]
    assert grouped["switch"] == ["switch.x"]


def test_find_duplicate_names_detects_collisions() -> None:
    """Two entities sharing a non-blank name are flagged."""
    duplicates = entity_manager.find_duplicate_names(
        {
            "light.a": "Lampe",
            "light.b": "Lampe",
            "light.c": "Andere Lampe",
            "light.d": "",
        }
    )
    assert duplicates == {"Lampe": ["light.a", "light.b"]}


def test_find_duplicate_names_ignores_blank() -> None:
    """Entities without a custom name never collide with each other."""
    duplicates = entity_manager.find_duplicate_names(
        {"light.a": "", "light.b": "   "}
    )
    assert duplicates == {}


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


async def test_config_reads_live_entry_state(hass: HomeAssistant) -> None:
    """should_expose/entity_config/endpoint reflect the bound entry live."""
    entry = _make_entry(
        hass,
        {
            CONF_EXPOSED_ENTITIES: ["light.donut_led"],
            CONF_ENTITY_NAMES: {"light.donut_led": "Donut"},
        },
    )

    config = entity_manager.AlexaBridgeManagerConfig(hass)
    config.bind(entry)

    assert config.endpoint == ENDPOINT_EU
    assert config.should_expose("light.donut_led") is True
    assert config.should_expose("light.other") is False
    assert config.entity_config == {"light.donut_led": {"name": "Donut"}}

    # Live update to the entry is picked up without rebinding.
    hass.config_entries.async_update_entry(
        entry, options={CONF_EXPOSED_ENTITIES: [], CONF_ENTITY_NAMES: {}}
    )
    assert config.should_expose("light.donut_led") is False
    assert config.entity_config == {}


async def test_config_unbind_clears_state(hass: HomeAssistant) -> None:
    """After unbind(), a removed integration exposes nothing."""
    entry = _make_entry(hass, {CONF_EXPOSED_ENTITIES: ["light.donut_led"]})
    config = entity_manager.AlexaBridgeManagerConfig(hass)
    config.bind(entry)
    assert config.should_expose("light.donut_led") is True

    config.unbind()
    assert config.should_expose("light.donut_led") is False
    assert config.endpoint is None
    assert config.supports_auth is False


async def test_setup_runtime_raises_on_conflict(hass: HomeAssistant) -> None:
    """A pre-existing /api/alexa/smart_home registration is detected."""
    entry = _make_entry(hass)

    with patch.object(
        entity_manager, "_smart_home_endpoint_registered", return_value=True
    ):
        with pytest.raises(entity_manager.SmartHomeEndpointConflict):
            await entity_manager.async_setup_runtime(hass, entry)


async def test_setup_runtime_registers_once(hass: HomeAssistant) -> None:
    """A second entry setup reuses the already-registered runtime config."""
    entry = _make_entry(hass)
    mock_register = Mock()
    hass.http = Mock(register_view=mock_register)
    hass.http.app.router.resources.return_value = []

    config1 = await entity_manager.async_setup_runtime(hass, entry)
    config2 = await entity_manager.async_setup_runtime(hass, entry)

    assert config1 is config2
    mock_register.assert_called_once()


async def test_sync_discovery_sends_add_and_delete(hass: HomeAssistant) -> None:
    """Newly exposed entities trigger AddOrUpdate, removed ones DeleteReport."""
    entry = _make_entry(hass, {CONF_EXPOSED_ENTITIES: ["light.a"]})
    domain_data = hass.data.setdefault(DOMAIN, {})
    config = entity_manager.AlexaBridgeManagerConfig(hass)
    config.bind(entry)
    domain_data[DATA_RUNTIME_CONFIG] = config
    domain_data[DATA_LAST_EXPOSED] = {entry.entry_id: ["light.old"]}

    with patch.object(
        entity_manager.AlexaBridgeManagerConfig,
        "authorized",
        new_callable=lambda: property(lambda self: True),
    ), patch(
        "custom_components.alexa_bridge_manager.entity_manager.async_send_add_or_update_message",
        new=AsyncMock(),
    ) as mock_add, patch(
        "custom_components.alexa_bridge_manager.entity_manager.async_send_delete_message",
        new=AsyncMock(),
    ) as mock_delete:
        await entity_manager.async_sync_discovery(hass, entry)

    mock_add.assert_awaited_once_with(hass, config, ["light.a"])
    mock_delete.assert_awaited_once_with(hass, config, ["light.old"])
    assert domain_data[DATA_LAST_EXPOSED][entry.entry_id] == ["light.a"]


async def test_sync_discovery_skips_when_not_authorized(hass: HomeAssistant) -> None:
    """Without a completed Alexa account link, no discovery push is sent."""
    entry = _make_entry(hass, {CONF_EXPOSED_ENTITIES: ["light.a"]})
    domain_data = hass.data.setdefault(DOMAIN, {})
    config = entity_manager.AlexaBridgeManagerConfig(hass)
    await config.async_initialize()
    config.bind(entry)
    domain_data[DATA_RUNTIME_CONFIG] = config

    with patch(
        "custom_components.alexa_bridge_manager.entity_manager.async_send_add_or_update_message",
        new=AsyncMock(),
    ) as mock_add:
        await entity_manager.async_sync_discovery(hass, entry)

    mock_add.assert_not_awaited()
