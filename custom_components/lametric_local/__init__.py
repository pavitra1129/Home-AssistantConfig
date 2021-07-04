"""Support for LaMetric time."""
import logging

import voluptuous as vol
from homeassistant.helpers import config_validation as cv, discovery

_LOGGER = logging.getLogger(__name__)

from homeassistant.const import CONF_NAME

DOMAIN = "lametric_local"

LAMETRIC_DEVICES = "LAMETRIC_LOCAL_DEVICES"

CONF_IP_ADDRESS = "ip_address"
CONF_PORT = "port"
CONF_API_KEY = "api_key"
CONF_CUSTOMIZE = "data"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_NAME): cv.string,
                        vol.Required(CONF_IP_ADDRESS): cv.string,
                        vol.Required(CONF_PORT): cv.string,
                        vol.Required(CONF_API_KEY): cv.string,
                        vol.Optional(CONF_CUSTOMIZE, default={}): dict
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass, config):
    """Set up the LaMetric."""
    _LOGGER.debug("Setting up LaMetric (local) platform")

    devices = config[DOMAIN]

    for device_conf in devices:
        hass.async_create_task(
            discovery.async_load_platform(hass, "notify", DOMAIN, device_conf, config)
        )

    return True
