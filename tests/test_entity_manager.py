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
    DATA_LAST_NAMES,
    DATA_RUNTIME_CONFIG,
    DOMAIN,
    ENDPOINT_EU,
)

# Built from the prefix constant at runtime (not a literal secret-shaped
# string in source) so GitHub's push protection does not flag it.
VALID_CLIENT_ID = CLIENT_ID_PREFIX + "test-fixture-not-a-real-id"
VALID_CLIENT_SECRET = CLIENT_SECRET_PREFIX + "test-fixture-not-a-real-secret"


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


def test_find_overlapping_names_detects_substring() -> None:
    """A name fully contained in another (as a whole word) is flagged.

    Reproduces a real report: naming a switch "TV" and a light "TV Licht"
    made Alexa unable to voice-recognize the light at all - a genuine Alexa
    limitation, not something Home Assistant controls, but something this
    validation can catch before it ever reaches Alexa.
    """
    overlaps = entity_manager.find_overlapping_names(
        {"switch.tv": "TV", "light.tv_led": "TV Licht"}
    )
    assert overlaps == [("switch.tv", "TV", "light.tv_led", "TV Licht")]


def test_find_overlapping_names_ignores_exact_duplicates() -> None:
    """Exact duplicates are left to find_duplicate_names, not reported twice."""
    overlaps = entity_manager.find_overlapping_names(
        {"light.a": "Lampe", "light.b": "Lampe"}
    )
    assert overlaps == []


def test_find_overlapping_names_ignores_partial_word_matches() -> None:
    """A name that is only a substring within a single word (not a whole
    word on its own) is not flagged - "TV" inside "TVzimmer" has no word
    boundary after it, unlike "TV" inside "TV Zimmer"."""
    overlaps = entity_manager.find_overlapping_names(
        {"switch.tv": "TV", "light.other": "TVzimmer"}
    )
    assert overlaps == []


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
        new=AsyncMock(return_value=Mock()),
    ) as mock_add, patch(
        "custom_components.alexa_bridge_manager.entity_manager.async_send_delete_message",
        new=AsyncMock(return_value=Mock()),
    ) as mock_delete:
        await entity_manager.async_sync_discovery(hass, entry)

    mock_add.assert_awaited_once_with(hass, config, ["light.a"])
    mock_delete.assert_awaited_once_with(hass, config, ["light.old"])
    assert domain_data[DATA_LAST_EXPOSED][entry.entry_id] == ["light.a"]


async def test_sync_discovery_sends_update_on_rename_alone(
    hass: HomeAssistant,
) -> None:
    """Renaming an already-exposed entity re-sends AddOrUpdate even though
    the exposed set itself did not change.

    Regression test: an earlier version of async_sync_discovery only diffed
    entity-ID set membership, so editing just the Alexa name of an entity
    that was already exposed never triggered a new discovery push - Alexa
    kept the old name forever until the entity was toggled off and on again.
    """
    entry = _make_entry(
        hass,
        {
            CONF_EXPOSED_ENTITIES: ["light.tv_led"],
            CONF_ENTITY_NAMES: {"light.tv_led": "TV Licht"},
        },
    )
    domain_data = hass.data.setdefault(DOMAIN, {})
    config = entity_manager.AlexaBridgeManagerConfig(hass)
    config.bind(entry)
    domain_data[DATA_RUNTIME_CONFIG] = config
    # Already synced once before, under the entity's old name.
    domain_data[DATA_LAST_EXPOSED] = {entry.entry_id: ["light.tv_led"]}
    domain_data[DATA_LAST_NAMES] = {
        entry.entry_id: {"light.tv_led": "TV LED Beleuchtung"}
    }

    with patch.object(
        entity_manager.AlexaBridgeManagerConfig,
        "authorized",
        new_callable=lambda: property(lambda self: True),
    ), patch(
        "custom_components.alexa_bridge_manager.entity_manager.async_send_add_or_update_message",
        new=AsyncMock(return_value=Mock()),
    ) as mock_add, patch(
        "custom_components.alexa_bridge_manager.entity_manager.async_send_delete_message",
        new=AsyncMock(return_value=Mock()),
    ) as mock_delete:
        await entity_manager.async_sync_discovery(hass, entry)

    mock_add.assert_awaited_once_with(hass, config, ["light.tv_led"])
    mock_delete.assert_not_awaited()
    assert domain_data[DATA_LAST_NAMES][entry.entry_id] == {
        "light.tv_led": "TV Licht"
    }


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
        new=AsyncMock(return_value=Mock()),
    ) as mock_add:
        await entity_manager.async_sync_discovery(hass, entry)

    mock_add.assert_not_awaited()


async def test_sync_discovery_does_not_advance_state_on_gateway_error(
    hass: HomeAssistant,
) -> None:
    """If Amazon rejects the push, the entity is retried on the next save.

    Regression guard for a real-world symptom: async_send_add_or_update_message
    only raises for connection-level failures, not for a 4xx/5xx response
    from Amazon (e.g. an expired token) - `raise_for_status()` must be called
    explicitly. If a rejection were treated as success, last_exposed/
    last_names would advance to the new state even though Alexa never
    actually learned about it, permanently hiding the failure.
    """
    entry = _make_entry(
        hass,
        {
            CONF_EXPOSED_ENTITIES: ["light.tv_led"],
            CONF_ENTITY_NAMES: {"light.tv_led": "TV Licht"},
        },
    )
    domain_data = hass.data.setdefault(DOMAIN, {})
    config = entity_manager.AlexaBridgeManagerConfig(hass)
    config.bind(entry)
    domain_data[DATA_RUNTIME_CONFIG] = config
    domain_data[DATA_LAST_EXPOSED] = {entry.entry_id: ["light.tv_led"]}
    domain_data[DATA_LAST_NAMES] = {
        entry.entry_id: {"light.tv_led": "TV LED Beleuchtung"}
    }

    rejected_response = Mock()
    rejected_response.raise_for_status.side_effect = Exception("401 Unauthorized")

    with patch.object(
        entity_manager.AlexaBridgeManagerConfig,
        "authorized",
        new_callable=lambda: property(lambda self: True),
    ), patch(
        "custom_components.alexa_bridge_manager.entity_manager.async_send_add_or_update_message",
        new=AsyncMock(return_value=rejected_response),
    ):
        await entity_manager.async_sync_discovery(hass, entry)

    # State must stay at the old (unsynced) name so the next save retries it.
    assert domain_data[DATA_LAST_NAMES][entry.entry_id] == {
        "light.tv_led": "TV LED Beleuchtung"
    }
