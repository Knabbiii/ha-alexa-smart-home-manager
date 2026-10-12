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
    STATUS_ERROR,
    STORAGE_KEY,
    STORAGE_VERSION,
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


def test_find_duplicate_names_ignores_case_and_spacing() -> None:
    """Alexa does not tell 'Lamp' and ' lamp ' apart, so neither do we."""
    duplicates = entity_manager.find_duplicate_names(
        {"light.a": "Lamp", "light.b": " lamp ", "light.c": "Reading  Lamp"}
    )
    assert duplicates == {"Lamp": ["light.a", "light.b"]}


def test_find_duplicate_names_allows_similar_names() -> None:
    """Names that merely contain or resemble each other are allowed."""
    duplicates = entity_manager.find_duplicate_names(
        {
            "light.a": "Lamp",
            "light.b": "Floor Lamp",
            "light.c": "Lamps",
            "light.d": "Lamp 2",
        }
    )
    assert duplicates == {}


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


def _authorized():
    return patch.object(
        entity_manager.AlexaBridgeManagerConfig,
        "authorized",
        new_callable=lambda: property(lambda self: True),
    )


async def test_sync_state_is_persisted_after_success(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    """What Amazon was told is written to storage, surviving a restart."""
    entry = _make_entry(
        hass,
        {
            CONF_EXPOSED_ENTITIES: ["light.a"],
            CONF_ENTITY_NAMES: {"light.a": "Lamp"},
        },
    )
    domain_data = hass.data.setdefault(DOMAIN, {})
    config = entity_manager.AlexaBridgeManagerConfig(hass)
    config.bind(entry)
    domain_data[DATA_RUNTIME_CONFIG] = config

    with _authorized(), patch(
        "custom_components.alexa_bridge_manager.entity_manager.async_send_add_or_update_message",
        new=AsyncMock(return_value=Mock()),
    ):
        await entity_manager.async_sync_discovery(hass, entry)

    saved = hass_storage[STORAGE_KEY]["data"]
    assert saved["exposed"] == {entry.entry_id: ["light.a"]}
    assert saved["names"] == {entry.entry_id: {"light.a": "Lamp"}}


async def test_persisted_state_prevents_resend_after_restart(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    """A fresh process loads the baseline instead of resending everything."""
    entry = _make_entry(hass, {CONF_EXPOSED_ENTITIES: ["light.a"]})
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "key": STORAGE_KEY,
        "data": {"exposed": {entry.entry_id: ["light.a"]}, "names": {}},
    }
    domain_data = hass.data.setdefault(DOMAIN, {})
    config = entity_manager.AlexaBridgeManagerConfig(hass)
    config.bind(entry)
    domain_data[DATA_RUNTIME_CONFIG] = config

    with _authorized(), patch(
        "custom_components.alexa_bridge_manager.entity_manager.async_send_add_or_update_message",
        new=AsyncMock(return_value=Mock()),
    ) as mock_add:
        await entity_manager.async_sync_discovery(hass, entry)

    mock_add.assert_not_awaited()


async def test_removal_while_unlinked_is_still_deleted_later(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    """A removal made before linking is sent once the skill is linked."""
    entry = _make_entry(hass, {CONF_EXPOSED_ENTITIES: []})
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "key": STORAGE_KEY,
        "data": {"exposed": {entry.entry_id: ["light.old"]}, "names": {}},
    }
    domain_data = hass.data.setdefault(DOMAIN, {})
    config = entity_manager.AlexaBridgeManagerConfig(hass)
    config.bind(entry)
    domain_data[DATA_RUNTIME_CONFIG] = config

    with _authorized(), patch(
        "custom_components.alexa_bridge_manager.entity_manager.async_send_delete_message",
        new=AsyncMock(return_value=Mock()),
    ) as mock_delete:
        await entity_manager.async_sync_discovery(hass, entry)

    mock_delete.assert_awaited_once_with(hass, config, ["light.old"])


async def test_sync_error_sets_status(hass: HomeAssistant) -> None:
    """A rejected push is visible in the sync status, with the reason."""
    entry = _make_entry(hass, {CONF_EXPOSED_ENTITIES: ["light.a"]})
    domain_data = hass.data.setdefault(DOMAIN, {})
    config = entity_manager.AlexaBridgeManagerConfig(hass)
    config.bind(entry)
    domain_data[DATA_RUNTIME_CONFIG] = config

    rejected = Mock()
    rejected.raise_for_status.side_effect = Exception("401 Unauthorized")
    with _authorized(), patch(
        "custom_components.alexa_bridge_manager.entity_manager.async_send_add_or_update_message",
        new=AsyncMock(return_value=rejected),
    ):
        await entity_manager.async_sync_discovery(hass, entry)

    status = entity_manager.get_status(hass)
    assert status.state == STATUS_ERROR
    assert status.error == "401 Unauthorized"


async def test_accept_grant_triggers_sync(hass: HomeAssistant) -> None:
    """Completing account linking pushes the already-exposed entities."""
    entry = _make_entry(hass, {CONF_EXPOSED_ENTITIES: ["light.a"]})
    config = entity_manager.AlexaBridgeManagerConfig(hass)
    config.bind(entry)

    with _authorized(), patch.object(
        config._auth, "async_do_auth", new=AsyncMock(return_value=None)
    ), patch.object(
        entity_manager, "async_sync_discovery", new=AsyncMock()
    ) as mock_sync:
        assert await config.async_accept_grant("code") is None
        await hass.async_block_till_done()

    mock_sync.assert_awaited_once_with(hass, entry)


async def test_bind_keeps_auth_when_credentials_unchanged(
    hass: HomeAssistant,
) -> None:
    """Rebinding after an options reload keeps the cached access token."""
    entry = _make_entry(hass)
    config = entity_manager.AlexaBridgeManagerConfig(hass)
    config.bind(entry)
    auth = config._auth

    config.bind(entry)
    assert config._auth is auth

    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_CLIENT_SECRET: CLIENT_SECRET_PREFIX + "new"}
    )
    config.bind(entry)
    assert config._auth is not auth
