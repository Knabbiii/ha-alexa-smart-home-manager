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
