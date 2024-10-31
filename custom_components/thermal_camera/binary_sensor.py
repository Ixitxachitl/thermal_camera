import logging
import uuid
from homeassistant.components.binary_sensor import BinarySensorEntity
from .constants import DOMAIN, DEFAULT_NAME, DEFAULT_MOTION_THRESHOLD, DEFAULT_PATH, DEFAULT_AVERAGE_FIELD, DEFAULT_HIGHEST_FIELD, CONF_PATH, CONF_MOTION_THRESHOLD, CONF_AVERAGE_FIELD, CONF_HIGHEST_FIELD
from homeassistant.const import CONF_NAME, CONF_URL
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from .coordinator import ThermalCameraDataCoordinator

_LOGGER = logging.getLogger(__name__)



async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the thermal motion sensor from a config entry."""
    config = config_entry.data
    name = config.get(CONF_NAME, DEFAULT_NAME)
    motion_threshold = config.get(CONF_MOTION_THRESHOLD, DEFAULT_MOTION_THRESHOLD)
    average_field = config.get(CONF_AVERAGE_FIELD, DEFAULT_AVERAGE_FIELD)
    highest_field = config.get(CONF_HIGHEST_FIELD, DEFAULT_HIGHEST_FIELD)

    # Retrieve the coordinator from the camera setup or create if necessary
    coordinator = hass.data[DOMAIN].get(config_entry.entry_id).get("coordinator")
    if coordinator is None:
        _LOGGER.error("Data coordinator not found for Thermal Motion Sensor")
        return

    # Generate a unique ID if it does not already exist
    unique_id = config_entry.data.get("unique_id_motion_sensor")
    if unique_id is None:
        unique_id = str(uuid.uuid4())
        hass.config_entries.async_update_entry(config_entry, data={**config_entry.data, "unique_id_motion_sensor": unique_id})

    async_add_entities([
        ThermalMotionSensor(
            name=name,
            coordinator=coordinator,
            motion_threshold=motion_threshold,
            average_field=average_field,
            highest_field=highest_field,
            config_entry=config_entry,
            unique_id=unique_id
        )
    ])

class ThermalMotionSensor(BinarySensorEntity):
    """Representation of a thermal motion detection sensor using the DataUpdateCoordinator."""

    def __init__(self, name, coordinator, motion_threshold, average_field, highest_field, config_entry=None, unique_id=None):
        super().__init__()
        self._config_entry = config_entry
        self._name = name
        self.coordinator = coordinator  # Use the coordinator for data
        self._motion_threshold = motion_threshold
        self._average_field = average_field
        self._highest_field = highest_field
        self._is_on = False
        self._unique_id = unique_id

        # Listen for updates from the coordinator
        self.coordinator.async_add_listener(self.async_write_ha_state)

    @property
    def unique_id(self):
        """Return a unique ID for the sensor."""
        return self._unique_id

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
        return self._is_on

    @property
    def icon(self):
        return "mdi:motion-sensor"

    async def async_update(self):
        """Request a data refresh from the coordinator and update the state."""
        data = self.coordinator.data

        # Skip if no data yet, log as info instead of error
        if data is None:
            _LOGGER.info("No data available from coordinator yet.")
            return
        
        # Check if data is available and contains required fields
        if data:
            avg_temp = data.get(self._average_field)
            max_temp = data.get(self._highest_field)

            if avg_temp is not None and max_temp is not None:
                temp_diff = max_temp - avg_temp
                self._is_on = temp_diff > self._motion_threshold
            else:
                _LOGGER.error("Missing required temperature data fields from coordinator.")
        else:
            _LOGGER.error("No data received from coordinator.")

    async def async_will_remove_from_hass(self):
        """Called when the entity is about to be removed from Home Assistant."""
        # Do not close the shared session or coordinator here, it's managed by the integration
        pass
