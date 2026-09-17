"""Tests for the diagnostics platform - mainly that secrets are redacted."""
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
    ENDPOINT_EU,
)
from custom_components.alexa_bridge_manager.diagnostics import (
    async_get_config_entry_diagnostics,
)

# Built from the prefix constant at runtime (not a literal secret-shaped
# string in source) so GitHub's push protection does not flag it.
VALID_CLIENT_ID = CLIENT_ID_PREFIX + "test-fixture-not-a-real-id"
VALID_CLIENT_SECRET = CLIENT_SECRET_PREFIX + "test-fixture-not-a-real-secret"


async def test_diagnostics_redacts_secrets_and_counts_entities(
    hass: HomeAssistant,
) -> None:
    """client_id/client_secret are redacted, exposure counts are reported."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ENDPOINT: ENDPOINT_EU,
            CONF_CLIENT_ID: VALID_CLIENT_ID,
            CONF_CLIENT_SECRET: VALID_CLIENT_SECRET,
        },
        options={
            CONF_EXPOSED_ENTITIES: ["light.a", "light.b"],
            CONF_ENTITY_NAMES: {"light.a": "Lampe"},
        },
    )
    entry.add_to_hass(hass)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry_data"][CONF_CLIENT_ID] == "**REDACTED**"
    assert result["entry_data"][CONF_CLIENT_SECRET] == "**REDACTED**"
    assert result["exposed_entity_count"] == 2
    assert result["custom_named_entity_count"] == 1
    assert result["exposed_entities"] == ["light.a", "light.b"]
