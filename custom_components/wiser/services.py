# Initialise global services
import voluptuous as vol
import logging
from .const import (
    ATTR_FILENAME,
    ATTR_HUB, 
    ATTR_SCHEDULE_ID,
    ATTR_TIME_PERIOD, 
    ATTR_TO_ENTITY_ID,
    DATA,
    DEFAULT_BOOST_TEMP_TIME,
    DOMAIN,
    WISER_SERVICES
)
from .helpers import get_config_entry_id_by_name, get_instance_count, is_wiser_config_id
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

async def async_setup_services(hass, data):

    GET_SCHEDULE_SCHEMA = vol.Schema(
        {
            vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Optional(ATTR_FILENAME, default=""): vol.Coerce(str),
        }
    )

    SET_SCHEDULE_SCHEMA = vol.Schema(
        {
            vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Required(ATTR_FILENAME): vol.Coerce(str),
        }
    )

    COPY_SCHEDULE_SCHEMA = vol.Schema(
        {
            vol.Required(ATTR_ENTITY_ID): cv.entity_id,
            vol.Required(ATTR_TO_ENTITY_ID): cv.entity_ids,
        }
    )

    ASSIGN_SCHEDULE_SCHEMA = vol.Schema(
        {
            vol.Optional(ATTR_ENTITY_ID): cv.entity_id,
            vol.Optional(ATTR_SCHEDULE_ID): vol.Coerce(int),
            vol.Required(ATTR_TO_ENTITY_ID): cv.entity_ids,
        }
    )

    SET_DEVICE_MODE_SCHEMA = vol.Schema(
        {
            vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Required(ATTR_MODE): vol.Coerce(str),
        }
    )

    BOOST_HOTWATER_SCHEMA = vol.Schema(
        {
            vol.Optional(ATTR_TIME_PERIOD, default=DEFAULT_BOOST_TEMP_TIME): vol.Coerce(int),
            vol.Optional(ATTR_HUB, default=""): vol.Coerce(str)
        }
        )

    def get_entity_from_entity_id(entity: str):
        """Get wiser entity from entity_id"""
        domain = entity.split(".", 1)[0]
        entity_comp = hass.data.get("entity_components", {}).get(domain)
        if entity_comp:
            return entity_comp.get_entity(entity)
        return None

    @callback
    def get_schedule(service_call):
        """Handle the service call."""
        entity_ids = service_call.data[ATTR_ENTITY_ID]
        for entity_id in entity_ids:
            filename = (
                service_call.data[ATTR_FILENAME]
                if service_call.data[ATTR_FILENAME] != ""
                else (hass.config.config_dir + "/schedules/schedule_" + entity_id.split(".", 1)[1] + ".yaml")
            )
            entity = get_entity_from_entity_id(entity_id)
            if entity:
                if hasattr(entity, "get_schedule"):
                    getattr(entity, "get_schedule")(filename)
                else:
                    _LOGGER.error(f"Cannot save schedule from entity {entity_id}.  Please see integration instructions for entities to choose")
            else:
                _LOGGER.error(f"Invalid entity. {entity_id} does not exist in this integration")

    @callback
    def set_schedule(service_call):
        """Handle the service call."""
        entity_ids = service_call.data[ATTR_ENTITY_ID]
        for entity_id in entity_ids:
            filename = service_call.data[ATTR_FILENAME]
            entity = get_entity_from_entity_id(entity_id)
            if entity:
                if hasattr(entity, "set_schedule"):
                    getattr(entity, "set_schedule")(filename)
                else:
                    _LOGGER.error(f"Cannot set schedule for entity {entity_id}.  Please see integration instructions for entities to choose")
            else:
                _LOGGER.error(f"Invalid entity. {entity_id} does not exist in this integration")

    @callback
    def copy_schedule(service_call):
        """Handle the service call"""
        entity_id = service_call.data[ATTR_ENTITY_ID]
        to_entity_ids = service_call.data[ATTR_TO_ENTITY_ID]
        for to_entity_id in to_entity_ids:
            from_entity = get_entity_from_entity_id(entity_id)
            to_entity = get_entity_from_entity_id(to_entity_id)

            if from_entity and to_entity:
                # Check from entity is a schedule entity
                if hasattr(from_entity, "copy_schedule"):
                    getattr(from_entity, "copy_schedule")(to_entity)
                else:
                    _LOGGER.error(f"Cannot copy schedule from entity {from_entity.name}.  Please see integration instructions for entities to choose")
            else:
                    _LOGGER.error(f"Invalid entity - {entity_id if not from_entity else ''}{' and ' if not from_entity and not to_entity else ''}{to_entity_id if not to_entity else ''} does not exist in this integration")
            return False

    @callback
    def assign_schedule(service_call):
        """Handle the service call"""
        entity_id = service_call.data.get(ATTR_ENTITY_ID)
        schedule_id = service_call.data.get(ATTR_SCHEDULE_ID)
        to_entity_ids = service_call.data[ATTR_TO_ENTITY_ID]

        if entity_id:
            # Assign schedule from this entity to another
            for to_entity_id in to_entity_ids:
                from_entity = get_entity_from_entity_id(entity_id)
                to_entity = get_entity_from_entity_id(to_entity_id)

                if from_entity and to_entity:
                    if hasattr(from_entity, "assign_schedule_to_another_entity"):
                        getattr(from_entity, "assign_schedule_to_another_entity")(to_entity)
                    else:
                        _LOGGER.error(f"Cannot assign schedule from entity {from_entity.name}.  Please see integration instructions for entities to choose")
                else:
                    _LOGGER.error(f"Invalid entity - {entity_id if not from_entity else ''}{' and ' if not from_entity and not to_entity else ''}{to_entity_id if not to_entity else ''} does not exist in this integration")
        elif schedule_id:
            # Assign scheduel with id to this entity
            for to_entity_id in to_entity_ids:
                to_entity = get_entity_from_entity_id(to_entity_id)
                if to_entity:
                    if hasattr(to_entity, "assign_schedule_by_id"):
                        getattr(to_entity, "assign_schedule_by_id")(schedule_id)
                    else:
                        _LOGGER.error(f"Cannot assign schedule to entity {to_entity.name}.  Please see integration instructions for entities to choose")
        else:
            # Create default schedule and assign to entity
            for to_entity_id in to_entity_ids:
                entity = get_entity_from_entity_id(to_entity_id)
                if hasattr(entity, "create_schedule"):
                    getattr(entity, "create_schedule")()
                else:
                    _LOGGER.error(f"Cannot assign schedule to entity {to_entity.name}.  Please see integration instructions for entities to choose")

    @callback
    def set_device_mode(service_call):
        """Handle the service call."""
        entity_ids = service_call.data[ATTR_ENTITY_ID]
        mode = service_call.data[ATTR_MODE]
        for entity_id in entity_ids:
            entity = get_entity_from_entity_id(entity_id)
            if entity:
                if hasattr(entity, "set_mode"):
                    if mode.lower() in [option.lower() for option in entity._options]:
                        getattr(entity, "set_mode")(mode)
                    else:
                        _LOGGER.error(F"{mode} is not a valid mode for this device.  Options are {entity._options}")
                else:
                    _LOGGER.error(f"Cannot set mode for entity {entity_id}.  Please see integration instructions for entities to choose")
            else:
                _LOGGER.error(f"Invalid entity. {entity_id} does not exist in this integration")

    @callback
    async def async_boost_hotwater(service_call):
        time_period = service_call.data[ATTR_TIME_PERIOD]
        hub = service_call.data[ATTR_HUB]
        instance = data

        if get_instance_count(hass) > 1:
            if not hub:
                raise HomeAssistantError("Please specify a hub config entry id or name")
                return None
            else:
                #Find hub from config_entry_id or hub name
                if is_wiser_config_id(hass, hub):
                    instance = hass.data[DOMAIN][hub][DATA]
                else:
                    # Find hub by name
                    config_entry_id = get_config_entry_id_by_name(hass, hub)
                    if config_entry_id:
                        instance = hass.data[DOMAIN][config_entry_id][DATA]

        # If hub has hotwater functionality, call boost
        if instance.wiserhub.hotwater:
            if time_period > 0:
                _LOGGER.info(f"Boosting Hot Water for {time_period}m")
                await hass.async_add_executor_job(
                    instance.wiserhub.hotwater.boost, time_period
                )
            else:
                _LOGGER.info(f"Cancelling Hot Water boost")
                await hass.async_add_executor_job(
                    instance.wiserhub.hotwater.cancel_overrides
                )
        else:
            raise HomeAssistantError("This hub does not have hotwater functionality")
        await data.async_force_update()

    hass.services.async_register(
        DOMAIN,
        WISER_SERVICES["SERVICE_GET_SCHEDULE"],
        get_schedule,
        schema=GET_SCHEDULE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        WISER_SERVICES["SERVICE_SET_SCHEDULE"],
        set_schedule,
        schema=SET_SCHEDULE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        WISER_SERVICES["SERVICE_COPY_SCHEDULE"],
        copy_schedule,
        schema=COPY_SCHEDULE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        WISER_SERVICES["SERVICE_ASSIGN_SCHEDULE"],
        assign_schedule,
        schema=ASSIGN_SCHEDULE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        WISER_SERVICES["SERVICE_SET_DEVICE_MODE"],
        set_device_mode,
        schema=SET_DEVICE_MODE_SCHEMA,
    )

    if data.wiserhub.hotwater:
        hass.services.async_register(
            DOMAIN,
            WISER_SERVICES["SERVICE_BOOST_HOTWATER"],
            async_boost_hotwater,
            schema=BOOST_HOTWATER_SCHEMA,
        )