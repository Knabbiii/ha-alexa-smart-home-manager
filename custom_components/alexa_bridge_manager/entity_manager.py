"""Runtime logic that wires this integration into HA Core's `alexa` component.

Why this file looks the way it does
------------------------------------
Home Assistant's built-in `alexa` integration (homeassistant/components/alexa)
has *no* config entry / config flow support at all. It is configured purely
from `configuration.yaml`'s `alexa: smart_home:` block, parsed once at HA
startup by `alexa/__init__.py::async_setup()`, which builds a single
`AlexaConfig` object (alexa/smart_home.py) and registers it as an aiohttp view
at the fixed URL `/api/alexa/smart_home`. That object's filter/entity_config
is frozen for the lifetime of the HA process - there is no reload hook.

To let users manage exposed entities from the UI without restarting HA, this
module does *not* try to patch or reach into that private `AlexaConfig`
instance. Instead it plays the same role the manual YAML setup does, but
config-entry-backed:

- `AlexaBridgeManagerConfig` subclasses the same public
  `homeassistant.components.alexa.config.AbstractConfig` base class the core
  component uses, reading `should_expose`/`entity_config`/`endpoint` live from
  the config entry on every call (never cached), so changes made through the
  options flow take effect immediately.
- It is registered exactly once per HA run at the same
  `homeassistant.components.alexa.smart_home.SMART_HOME_HTTP_ENDPOINT` URL,
  using the same `SmartHomeView` class Core uses, so Amazon's Lambda can call
  it exactly as it would the manual setup.
- Because aiohttp has no API to unregister a view, we never re-register: the
  view/config object is created once and then *rebound* to whichever config
  entry is currently active (see `bind`/`unbind`). This correctly survives
  config entry reloads (options changes) and remove+re-add cycles without
  ever leaving a stale, unreachable second registration behind.
- If the user still has `alexa: smart_home:` in YAML, that YAML setup will
  already have claimed the same URL first. aiohttp resolves duplicate routes
  to whichever was registered first, so silently registering a second one
  would look like it worked while never actually receiving requests. We
  detect that case up front and refuse to set up with a Repair issue
  instead, telling the user to remove the YAML block.
"""
from __future__ import annotations

import logging
from typing import Any

from yarl import URL

from homeassistant.components.alexa.auth import Auth
from homeassistant.components.alexa.config import AbstractConfig
from homeassistant.components.alexa.smart_home import (
    SMART_HOME_HTTP_ENDPOINT,
    SmartHomeView,
)
from homeassistant.components.alexa.state_report import (
    async_send_add_or_update_message,
    async_send_delete_message,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENDPOINT,
    CONF_ENTITY_NAMES,
    CONF_EXPOSED_ENTITIES,
    DATA_LAST_EXPOSED,
    DATA_LAST_NAMES,
    DATA_RUNTIME_CONFIG,
    DEFAULT_LOCALE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SmartHomeEndpointConflict(Exception):
    """Raised when `/api/alexa/smart_home` is already claimed elsewhere."""


class AlexaBridgeManagerConfig(AbstractConfig):
    """Live `AbstractConfig` implementation backed by our config entry.

    A single instance of this class is created for the lifetime of the HA
    process (see `async_setup_runtime`). `bind()`/`unbind()` point it at the
    config entry that currently owns it, and every property re-reads that
    entry's current data/options - there is no cached state to invalidate
    when the options flow saves changes.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize with no bound entry yet."""
        super().__init__(hass)
        self._entry_id: str | None = None
        self._auth: Auth | None = None

    @callback
    def bind(self, entry: ConfigEntry) -> None:
        """(Re)bind this runtime config to a config entry."""
        self._entry_id = entry.entry_id
        self._auth = Auth(
            self.hass, entry.data[CONF_CLIENT_ID], entry.data[CONF_CLIENT_SECRET]
        )

    @callback
    def unbind(self) -> None:
        """Detach from any config entry (integration removed)."""
        self._entry_id = None
        self._auth = None

    def _entry(self) -> ConfigEntry | None:
        """Return the currently bound config entry, if any."""
        if self._entry_id is None:
            return None
        return self.hass.config_entries.async_get_entry(self._entry_id)

    @property
    def supports_auth(self) -> bool:
        """Return if config supports auth."""
        return self._auth is not None

    @property
    def should_report_state(self) -> bool:
        """Return if we should proactively report states."""
        return self._auth is not None and self.authorized

    @property
    def endpoint(self) -> str | URL | None:
        """Endpoint for report state."""
        entry = self._entry()
        return entry.data[CONF_ENDPOINT] if entry else None

    @property
    def entity_config(self) -> dict[str, Any]:
        """Return the Alexa display names configured for exposed entities."""
        entry = self._entry()
        if entry is None:
            return {}
        names: dict[str, str] = entry.options.get(CONF_ENTITY_NAMES, {})
        return {
            entity_id: {"name": name} for entity_id, name in names.items() if name
        }

    @property
    def locale(self) -> str | None:
        """Return config locale."""
        return DEFAULT_LOCALE

    @callback
    def user_identifier(self) -> str:
        """Return an identifier for the user that represents this config."""
        return ""

    @callback
    def should_expose(self, entity_id: str) -> bool:
        """If an entity should be exposed, per the options flow selection."""
        entry = self._entry()
        if entry is None:
            return False
        return entity_id in entry.options.get(CONF_EXPOSED_ENTITIES, [])

    @callback
    def async_invalidate_access_token(self) -> None:
        """Invalidate access token."""
        assert self._auth is not None
        self._auth.async_invalidate_access_token()

    async def async_get_access_token(self) -> str | None:
        """Get an access token."""
        assert self._auth is not None
        return await self._auth.async_get_access_token()

    async def async_accept_grant(self, code: str) -> str | None:
        """Accept a grant."""
        assert self._auth is not None
        return await self._auth.async_do_auth(code)


@callback
def _smart_home_endpoint_registered(hass: HomeAssistant) -> bool:
    """Return True if something already serves SMART_HOME_HTTP_ENDPOINT.

    There is no public "is this URL taken" API, but aiohttp's router can be
    introspected: every registered route shows up as a resource with a
    canonical path. This lets us detect a YAML-configured `alexa:
    smart_home:` (or a leftover registration from this integration in a
    prior run) before silently registering a second, unreachable one.
    """
    for resource in hass.http.app.router.resources():
        if resource.canonical == SMART_HOME_HTTP_ENDPOINT:
            return True
    return False


async def async_setup_runtime(
    hass: HomeAssistant, entry: ConfigEntry
) -> AlexaBridgeManagerConfig:
    """Create (once) and bind the runtime Alexa config for this entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    config: AlexaBridgeManagerConfig | None = domain_data.get(DATA_RUNTIME_CONFIG)

    if config is None:
        if _smart_home_endpoint_registered(hass):
            raise SmartHomeEndpointConflict(
                f"{SMART_HOME_HTTP_ENDPOINT} is already registered, likely by "
                "a YAML `alexa: smart_home:` block"
            )

        config = AlexaBridgeManagerConfig(hass)
        await config.async_initialize()
        hass.http.register_view(SmartHomeView(config))
        domain_data[DATA_RUNTIME_CONFIG] = config
        _LOGGER.debug("Registered Alexa Smart Home endpoint for %s", DOMAIN)

    config.bind(entry)

    if config.should_report_state:
        await config.async_enable_proactive_mode()

    return config


async def async_teardown_runtime(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Fully detach the runtime config when the config entry is removed.

    Called from `async_remove_entry`, *not* on every reload - reloads (e.g.
    from the options flow) must keep the same registered view alive, since
    aiohttp has no API to unregister it. Only a genuine removal clears the
    binding, so a later re-add starts from a clean, correctly-bound state
    instead of silently keeping stale credentials.
    """
    domain_data = hass.data.get(DOMAIN, {})
    config: AlexaBridgeManagerConfig | None = domain_data.get(DATA_RUNTIME_CONFIG)
    if config is None:
        return

    exposed = entry.options.get(CONF_EXPOSED_ENTITIES, [])
    if exposed and config.authorized:
        try:
            await async_send_delete_message(hass, config, exposed)
        except Exception:  # noqa: BLE001 - best effort, must not block removal
            _LOGGER.warning(
                "Could not notify Alexa about removed entities", exc_info=True
            )

    await config.async_disable_proactive_mode()
    config.unbind()
    domain_data.pop(DATA_LAST_EXPOSED, None)
    domain_data.pop(DATA_LAST_NAMES, None)


async def async_sync_discovery(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Push an Alexa discovery update after exposure or naming changed.

    Alexa (unlike Google Assistant) does not pick up newly exposed entities
    - or renamed ones - on its own; a proactive `AddOrUpdateReport`/
    `DeleteReport` discovery event needs to be sent to Amazon's event
    gateway. This diffs both the newly saved `exposed_entities` *and*
    `entity_names` options against what was last synced: newly exposed
    entities and entities whose Alexa name changed both need an
    `AddOrUpdateReport` (Amazon treats it as an upsert keyed by endpoint ID,
    so resending an already-known entity just updates its name), while
    entities that dropped out of the exposed set need a `DeleteReport`.
    Only comparing entity-ID set membership - as an earlier version of this
    function did - misses pure renames: the exposed set does not change
    when you just edit a name, so no update would ever reach Amazon and the
    old name would keep being the only one Alexa recognizes.

    Best-effort: if the skill has not completed Alexa account linking yet
    (`config.authorized` is False), or the request to Amazon fails, this
    logs a warning instead of raising, so a save in the options flow never
    fails just because the discovery push could not be delivered.
    """
    domain_data = hass.data.get(DOMAIN, {})
    config: AlexaBridgeManagerConfig | None = domain_data.get(DATA_RUNTIME_CONFIG)
    if config is None:
        _LOGGER.warning(
            "Skipping Alexa discovery sync: runtime config not set up yet"
        )
        return
    if not config.authorized:
        _LOGGER.warning(
            "Skipping Alexa discovery sync: this skill has not completed Alexa "
            "account linking yet (no AcceptGrant/directive received from Alexa "
            "so far), so there is no access token to call the event gateway with"
        )
        return

    last_exposed: dict[str, list[str]] = domain_data.setdefault(DATA_LAST_EXPOSED, {})
    last_names: dict[str, dict[str, str]] = domain_data.setdefault(DATA_LAST_NAMES, {})

    previous_exposed = set(last_exposed.get(entry.entry_id, []))
    current_exposed = set(entry.options.get(CONF_EXPOSED_ENTITIES, []))
    previous_names = last_names.get(entry.entry_id, {})
    current_names: dict[str, str] = entry.options.get(CONF_ENTITY_NAMES, {})

    newly_exposed = current_exposed - previous_exposed
    removed = previous_exposed - current_exposed
    renamed = {
        entity_id
        for entity_id in current_exposed & previous_exposed
        if current_names.get(entity_id, "") != previous_names.get(entity_id, "")
    }
    to_upsert = newly_exposed | renamed

    if not to_upsert and not removed:
        _LOGGER.debug("Alexa discovery sync: nothing changed, nothing to send")
        return

    _LOGGER.info(
        "Alexa discovery sync: sending AddOrUpdateReport for %s, "
        "DeleteReport for %s",
        sorted(to_upsert) or "-",
        sorted(removed) or "-",
    )

    try:
        if to_upsert:
            response = await async_send_add_or_update_message(
                hass, config, list(to_upsert)
            )
            response.raise_for_status()
        if removed:
            response = await async_send_delete_message(hass, config, list(removed))
            response.raise_for_status()
    except Exception:  # noqa: BLE001 - network call to Amazon, must not crash
        _LOGGER.warning(
            "Alexa rejected or could not be reached for the discovery sync - "
            "the exposed/named entities in Home Assistant and what Alexa "
            "actually knows are now out of sync until the next successful save",
            exc_info=True,
        )
        return

    _LOGGER.info("Alexa discovery sync: gateway accepted the update")
    last_exposed[entry.entry_id] = list(current_exposed)
    last_names[entry.entry_id] = dict(current_names)


def find_duplicate_names(entity_names: dict[str, str]) -> dict[str, list[str]]:
    """Return {alexa_name: [entity_ids]} for names used by more than one entity.

    Blank/unset names are ignored - they fall back to the HA friendly_name
    and are not compared against each other here.
    """
    by_name: dict[str, list[str]] = {}
    for entity_id, name in entity_names.items():
        normalized = name.strip()
        if not normalized:
            continue
        by_name.setdefault(normalized, []).append(entity_id)
    return {name: ids for name, ids in by_name.items() if len(ids) > 1}
