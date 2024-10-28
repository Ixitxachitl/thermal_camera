import logging
import uuid
import aiohttp
import async_timeout
from homeassistant.components.binary_sensor import BinarySensorEntity
from .constants import DOMAIN, DEFAULT_NAME, DEFAULT_MOTION_THRESHOLD, DEFAULT_PATH, DEFAULT_AVERAGE_FIELD, DEFAULT_HIGHEST_FIELD, CONF_PATH, CONF_MOTION_THRESHOLD, CONF_AVERAGE_FIELD, CONF_HIGHEST_FIELD
from homeassistant.const import CONF_NAME, CONF_URL
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from .coordinator import ThermalDataCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the thermal motion sensor from a config entry."""
    config = config_entry.data
    name = config.get(CONF_NAME, DEFAULT_NAME)
    url = config.get(CONF_URL)
    path = config.get(CONF_PATH, DEFAULT_PATH)
    motion_threshold = config.get(CONF_MOTION_THRESHOLD, DEFAULT_MOTION_THRESHOLD)
    average_field = config.get(CONF_AVERAGE_FIELD, DEFAULT_AVERAGE_FIELD)
    highest_field = config.get(CONF_HIGHEST_FIELD, DEFAULT_HIGHEST_FIELD)  # Use the shared field name

    # Reuse or create a persistent session for this platform
    session = hass.data.get("thermal_camera_session")
    if session is None or session.closed:
        session = aiohttp.ClientSession()
        hass.data["thermal_camera_session"] = session

    # Create the shared data coordinator
    coordinator = ThermalDataCoordinator(hass, session, url, path)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([ThermalMotionSensor(name, motion_threshold, average_field, highest_field, coordinator, config_entry=config_entry)])

class ThermalMotionSensor(BinarySensorEntity):
    """Representation of a thermal motion detection sensor."""
    def __init__(self, name, motion_threshold, average_field, highest_field, coordinator, config_entry=None):
        super().__init__()
        self._config_entry = config_entry
        self._name = name
        self._motion_threshold = motion_threshold
        self._average_field = average_field
        self._highest_field = highest_field
        self.coordinator = coordinator

        # Attach the coordinator's update callback to this entity's update method
        self.coordinator.async_add_listener(self.async_write_ha_state)

    @property
    def unique_id(self):
        """Return a unique ID for the sensor."""
        return f"{self._config_entry.entry_id}_motion_sensor"

    @property
    def device_info(self):
        """Return device information to group camera and binary sensor."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": self._config_entry.data.get("name", DEFAULT_NAME),
            "manufacturer": "Your Manufacturer",
            "model": "Thermal Motion Sensor",
        }

    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        # Update the state based on the coordinator's data
        data = self.coordinator.data
        if data is not None:
            avg_temp = data.get(self._average_field)
            max_temp = data.get(self._highest_field)

            if avg_temp is not None and max_temp is not None:
                temp_diff = max_temp - avg_temp
                return temp_diff > self._motion_threshold
        return False

    @property
    def icon(self):
        return "mdi:motion-sensor"

    async def async_will_remove_from_hass(self):
        """Called when the entity is about to be removed from Home Assistant."""
        # Remove the listener when the entity is removed
        self.coordinator.async_remove_listener(self.async_write_ha_state)
