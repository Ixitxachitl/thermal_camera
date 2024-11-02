import logging
import uuid
from homeassistant.components.binary_sensor import BinarySensorEntity
from .constants import DOMAIN, DEFAULT_NAME, DEFAULT_MOTION_THRESHOLD, DEFAULT_AVERAGE_FIELD, DEFAULT_HIGHEST_FIELD
from homeassistant.const import CONF_NAME
from .coordinator import ThermalCameraDataCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the thermal motion sensor from a config entry."""
    config = config_entry.data
    name = config.get(CONF_NAME, DEFAULT_NAME)
    motion_threshold = config.get("motion_threshold", DEFAULT_MOTION_THRESHOLD)

    # Retrieve the coordinator from the shared integration data
    coordinator = hass.data[DOMAIN].get(config_entry.entry_id).get("coordinator")
    if coordinator is None:
        _LOGGER.error("Data coordinator not found for Thermal Motion Sensor")
        return

    # Generate a unique ID for the sensor if it doesn’t exist
    unique_id = config_entry.data.get("unique_id_motion_sensor")
    if unique_id is None:
        unique_id = str(uuid.uuid4())
        hass.config_entries.async_update_entry(config_entry, data={**config_entry.data, "unique_id_motion_sensor": unique_id})

    async_add_entities([
        ThermalMotionSensor(
            name=name,
            coordinator=coordinator,
            motion_threshold=motion_threshold,
            config_entry=config_entry,
            unique_id=unique_id
        )
    ])

class ThermalMotionSensor(BinarySensorEntity):
    """Representation of a thermal motion detection sensor using the DataUpdateCoordinator."""

    def __init__(self, name, coordinator, motion_threshold, config_entry=None, unique_id=None):
        super().__init__()
        self._config_entry = config_entry
        self._name = name
        self.coordinator = coordinator  # Use the shared data coordinator
        self._motion_threshold = motion_threshold
        self._is_on = False
        self._unique_id = unique_id

        # Register the entity as a listener to the coordinator’s data updates
        self._remove_listener = None

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information to group with the main thermal camera device."""
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
        """Return True if motion is detected based on temperature difference."""
        return self._is_on

    @property
    def icon(self):
        return "mdi:motion-sensor"

    async def async_update(self):
        """Update the state based on coordinator data."""
        data = self.coordinator.data

        # Ensure coordinator data is available
        if data is None:
            _LOGGER.warning(f"{self.name}: No data available from coordinator.")
            return

        # Use the predefined keys from the coordinator directly
        avg_temp = data.get("avg_value")
        max_temp = data.get("max_value")

        if avg_temp is not None and max_temp is not None:
            temp_diff = max_temp - avg_temp
            self._is_on = temp_diff > self._motion_threshold
            _LOGGER.debug(f"{self.name}: Motion state updated. Temperature difference: {temp_diff}, Threshold: {self._motion_threshold}")
        else:
            _LOGGER.error(f"{self.name}: Missing required temperature data fields from coordinator.")

    async def async_added_to_hass(self):
        """Called when the entity is added to Home Assistant."""
        # Now attach the listener since hass is guaranteed to be available
        self._remove_listener = self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Clean up when the sensor is removed from Home Assistant."""
        if self._remove_listener:
            self._remove_listener()  # Remove the listener when removing the entity
            self._remove_listener = None
