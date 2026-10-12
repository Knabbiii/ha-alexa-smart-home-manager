"""Constants for the Alexa Smart Home Manager integration."""
from __future__ import annotations

DOMAIN = "alexa_bridge_manager"

# Config entry / options keys
CONF_ENDPOINT = "endpoint"
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"

CONF_EXPOSED_ENTITIES = "exposed_entities"
CONF_ENTITY_NAMES = "entity_names"

# Well-known Alexa Smart Home event gateway endpoints.
# Source: Amazon Alexa Smart Home Skill API docs / HA alexa/smart_home.py.
ENDPOINT_EU = "https://api.eu.amazonalexa.com/v3/events"
ENDPOINT_NA = "https://api.amazonalexa.com/v3/events"
ENDPOINT_FE = "https://api.fe.amazonalexa.com/v3/events"
ENDPOINT_CUSTOM = "custom"

KNOWN_ENDPOINTS = {
    ENDPOINT_EU: "Europe (EU)",
    ENDPOINT_NA: "North America (NA)",
    ENDPOINT_FE: "Far East (FE)",
    ENDPOINT_CUSTOM: "Custom URL",
}

# amzn1.application-oa2-client.<hex> / amzn1.oa2-cs.v1.<hex>
CLIENT_ID_PREFIX = "amzn1.application-oa2-client."
CLIENT_SECRET_PREFIX = "amzn1.oa2-cs.v1."

# Locale reported to Alexa for exposed entities. Matches the default of the
# manual alexa.smart_home YAML setup.
DEFAULT_LOCALE = "en-US"

# Keys used inside hass.data[DOMAIN]
DATA_RUNTIME_CONFIG = "runtime_config"
DATA_LAST_EXPOSED = "last_exposed"
DATA_LAST_NAMES = "last_names"
DATA_STATUS = "status"

# Persistent store holding what Amazon was last told, so a restart does not
# resend everything and removals made while unlinked are not forgotten.
STORAGE_KEY = f"{DOMAIN}.sync_state"
STORAGE_VERSION = 1

# Dispatcher signal fired whenever the link/sync status changes.
SIGNAL_STATUS_UPDATED = f"{DOMAIN}_status_updated"

# Sync status values (state of the "Sync status" sensor).
STATUS_NOT_LINKED = "not_linked"
STATUS_PENDING = "pending"
STATUS_SYNCED = "synced"
STATUS_ERROR = "error"

# Repair issues.
# smart_home_conflict: the manual `alexa: smart_home:` YAML block already owns
#   the /api/alexa/smart_home endpoint (see entity_manager.py).
# missing_entities: exposed entities no longer exist in Home Assistant.
ISSUE_SMART_HOME_CONFLICT = "smart_home_conflict"
ISSUE_MISSING_ENTITIES = "missing_entities"

# How many entities are asked for an Alexa name per page in the options flow,
# so the form stays usable with hundreds of entities.
ENTITIES_PER_PAGE = 10
