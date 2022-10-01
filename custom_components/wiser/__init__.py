"""
Drayton Wiser Compoment for Wiser System.

https://github.com/asantaga/wiserHomeAssistantPlatform
msparker@sky.com
"""
import asyncio
from datetime import timedelta, datetime
import logging
import json
import voluptuous as vol

from wiserHeatAPIv2.wiserhub import (
    TEMP_MINIMUM,
    TEMP_MAXIMUM,
    WiserAPI,
    WiserHubConnectionError,
    WiserHubAuthenticationError,
    WiserHubRESTError,
)

from homeassistant.const import (
    CONF_HOST,
    CONF_MINIMUM,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import Throttle

from .frontend import WiserCardRegistration
from .helpers import get_device_name, get_identifier
from .services import async_setup_services
from .websockets import async_register_websockets

from .const import (
    CONF_MOMENTS,
    CONF_RESTORE_MANUAL_TEMP_OPTION,
    CONF_SETPOINT_MODE,
    DEFAULT_SETPOINT_MODE,
    CONF_HEATING_BOOST_TEMP,
    CONF_HEATING_BOOST_TIME,
    CONF_HW_BOOST_TIME,
    CONF_LTS_SENSORS,
    DATA,
    DEFAULT_BOOST_TEMP,
    DEFAULT_BOOST_TEMP_TIME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MANUFACTURER,
    WISER_CARD_FILENAMES,
    UPDATE_LISTENER,
    UPDATE_TRACK,
    URL_BASE,
    WISER_PLATFORMS,
    WISER_SERVICES
)

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): vol.All(vol.Coerce(int)),
                    vol.Optional(CONF_MINIMUM, default=TEMP_MINIMUM): vol.All(
                        vol.Coerce(int)
                    ),
                    vol.Optional(CONF_HEATING_BOOST_TEMP, default=DEFAULT_BOOST_TEMP): vol.All(
                        vol.Coerce(int)
                    ),
                    vol.Optional(
                        CONF_HEATING_BOOST_TIME, default=DEFAULT_BOOST_TEMP_TIME
                    ): vol.All(vol.Coerce(int)),
                }
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass, config):
    """Set up of the Wiser Hub component."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up Wiser from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    data = WiserHubHandle(
        hass,
        config_entry,
    )

    try:
        await hass.async_add_executor_job(data.connect)
    except (WiserHubConnectionError, WiserHubRESTError) as ex:
        _LOGGER.error(ex)
        raise ConfigEntryNotReady("Unable to connect to the Wiser Hub")
    except WiserHubAuthenticationError as ex:
        _LOGGER.error(ex)
        return False
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.error(f"An unknown error occurred trying to update from Wiser hub {config_entry.data[CONF_HOST]}")
        _LOGGER.debug(f"Error is {str(ex)}")
        raise ConfigEntryNotReady("Unknown error connecting to the Wiser Hub")

    await hass.async_add_executor_job(data.update)


    # Poll for updates in the background
    update_track = async_track_time_interval(
        hass,
        lambda now: data.update(),
        timedelta(
            seconds=config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        ),
    )

    update_listener = config_entry.add_update_listener(_async_update_listener)

    hass.data[DOMAIN][config_entry.entry_id] = {
        DATA: data,
        UPDATE_TRACK: update_track,
        UPDATE_LISTENER: update_listener,
    }


    # Setup platforms
    for platform in WISER_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    # Setup websocket services for frontend cards
    await async_register_websockets(hass, data)

    # Setup services
    await async_setup_services(hass, data)

    # Add hub as device
    await data.async_update_device_registry()

    # Register custom cards
    cards = WiserCardRegistration(hass)
    cards.register()

    # Remove old gzip files
    await cards.async_remove_gzip_files()

    _LOGGER.info("Wiser Component Setup Completed")

    return True


async def _async_update_listener(hass, config_entry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)

async def async_remove_config_entry_device(hass, config_entry, device_entry) -> bool:
    """Delete device if not entities"""
    if device_entry.model == "Controller":
        _LOGGER.error("You cannot delete the Wiser Controller device via the device delete method.  Please remove the integration instead.")
        return False
    return True

async def async_unload_entry(hass, config_entry):
    """
    Unload a config entry.

    :param hass:
    :param config_entry:
    :return:
    """
    # Unload lovelace module resource
    if hass.data['lovelace']['mode'] == "storage":
        for card_filename in WISER_CARD_FILENAMES:
            url = f"{URL_BASE}/{card_filename}"
            wiser_resources = [resource for resource in hass.data['lovelace']["resources"].async_items() if resource["url"] == url]
            for resource in wiser_resources:
                await hass.data['lovelace']["resources"].async_delete_item(resource.get("id"))

    # Deregister services
    _LOGGER.debug("Unregister Wiser Services")
    hass.services.async_remove(DOMAIN, WISER_SERVICES["SERVICE_GET_SCHEDULE"])
    hass.services.async_remove(DOMAIN, WISER_SERVICES["SERVICE_SET_SCHEDULE"])
    hass.services.async_remove(DOMAIN, WISER_SERVICES["SERVICE_COPY_SCHEDULE"])
    hass.services.async_remove(DOMAIN, WISER_SERVICES["SERVICE_SET_DEVICE_MODE"])

    _LOGGER.debug("Unloading Wiser Component")
    # Unload a config entry
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in WISER_PLATFORMS
            ]
        )
    )

    hass.data[DOMAIN][config_entry.entry_id][UPDATE_TRACK]()
    hass.data[DOMAIN][config_entry.entry_id][UPDATE_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class WiserHubHandle:
    """Main Wiser class handling all data."""

    def __init__(self, hass, config_entry):
        """Initialise the base class."""
        self._hass = hass
        self._config_entry = config_entry
        self._name = config_entry.data[CONF_NAME]
        self.host = config_entry.data[CONF_HOST]
        self.secret = config_entry.data[CONF_PASSWORD]
        self.wiserhub = None
        self.last_update_time = datetime.now()
        self.last_update_status = ""
        self.minimum_temp = TEMP_MINIMUM
        self.maximum_temp = TEMP_MAXIMUM
        self.boost_temp = config_entry.options.get(CONF_HEATING_BOOST_TEMP, DEFAULT_BOOST_TEMP)
        self.boost_time = config_entry.options.get(
            CONF_HEATING_BOOST_TIME, DEFAULT_BOOST_TEMP_TIME
        )
        self.hw_boost_time = config_entry.options.get(
            CONF_HW_BOOST_TIME, DEFAULT_BOOST_TEMP_TIME
        )
        self.setpoint_mode = config_entry.options.get(CONF_SETPOINT_MODE, DEFAULT_SETPOINT_MODE)
        self.enable_moments = config_entry.options.get(CONF_MOMENTS, False)
        self.enable_lts_sensors = config_entry.options.get(CONF_LTS_SENSORS, False)
        self.previous_target_temp_option = config_entry.options.get(CONF_RESTORE_MANUAL_TEMP_OPTION, "Schedule")

    def connect(self):
        """Connect to Wiser Hub."""
        self.wiserhub = WiserAPI(self.host, self.secret)
        return True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Call Wiser Hub async update."""
        self._hass.async_create_task(self.async_update())

    async def async_update(self, no_throttle: bool = False):
        """Update from Wiser Hub."""
        try:
            result = await self._hass.async_add_executor_job(self.wiserhub.read_hub_data)
            if result:
                _LOGGER.info(f"Wiser Hub data updated - {self.wiserhub.system.name}")
                # Send update notice to all components to update
                self.last_update_time = datetime.now()
                self.last_update_status = "Success"
                dispatcher_send(self._hass, f"{self.wiserhub.system.name}-HubUpdateMessage")
                # Fire event on successfull update
                dispatcher_send(self._hass,"wiser_update_received")
                return True

            _LOGGER.error(f"Unable to update from Wiser hub - {self.wiserhub.system.name}")

        except (WiserHubConnectionError, WiserHubAuthenticationError, WiserHubRESTError) as ex:
            _LOGGER.error(ex)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error(f"An unknown error occurred trying to update from Wiser hub {self.wiserhub.system.name}")
            _LOGGER.debug(f"Error is {str(ex)}")
        
        self.last_update_status = "Failed"
        dispatcher_send(self._hass, f"{self.wiserhub.system.name}-HubUpdateFailedMessage")
        return False

    @property
    def unique_id(self):
        """Return a unique name, otherwise config flow does not work right."""
        return self.wiserhub.system.name

    async def async_update_device_registry(self):
        """Update device registry."""
        device_registry = dr.async_get(self._hass)
        device_registry.async_get_or_create(
            config_entry_id=self._config_entry.entry_id,
            connections={(CONNECTION_NETWORK_MAC, self.wiserhub.system.network.mac_address)},
            identifiers={(DOMAIN, get_identifier(self, 0))},
            manufacturer=MANUFACTURER,
            name=get_device_name(self, 0),
            model=self.wiserhub.system.model,
            sw_version=self.wiserhub.system.firmware_version,
        )
