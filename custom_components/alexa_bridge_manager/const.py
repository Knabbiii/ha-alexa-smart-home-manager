"""Constants for the Alexa Bridge Manager integration."""
from __future__ import annotations

DOMAIN = "alexa_bridge_manager"

# Config entry / options keys
CONF_ENDPOINT = "endpoint"
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_CUSTOM_ENDPOINT = "custom_endpoint"

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
    ENDPOINT_CUSTOM: "Custom / other",
}

# amzn1.application-oa2-client.<hex> / amzn1.oa2-cs.v1.<hex>
CLIENT_ID_PREFIX = "amzn1.application-oa2-client."
CLIENT_SECRET_PREFIX = "amzn1.oa2-cs.v1."

# Locale reported to Alexa for exposed entities. Not user-configurable (yet);
# the manual alexa.smart_home YAML setup defaults to en-US, we default to
# de-DE since that matches this project's primary audience.
DEFAULT_LOCALE = "de-DE"

# Keys used inside hass.data[DOMAIN]
DATA_RUNTIME_CONFIG = "runtime_config"
DATA_LAST_EXPOSED = "last_exposed"
DATA_LAST_NAMES = "last_names"

# Repair issue raised when the manual `alexa: smart_home:` YAML block already
# owns the /api/alexa/smart_home endpoint (see entity_manager.py).
ISSUE_SMART_HOME_CONFLICT = "smart_home_conflict"

# How many entities are shown per page in the options flow entity-selection
# step, grouped by domain, so the form stays usable with hundreds of entities.
ENTITIES_PER_PAGE = 10
