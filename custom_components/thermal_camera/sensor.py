import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTemperature
from .constants import DOMAIN, DEFAULT_NAME
from .coordinator import ThermalCameraDataCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the thermal camera sensors from a config entry."""
    # Retrieve the coordinator from the main integration data
    coordinator = hass.data[DOMAIN].get(config_entry.entry_id).get("coordinator")
    if coordinator is None:
        _LOGGER.error("Data coordinator not found for Thermal Camera Sensors")
        return

    # Initialize three sensors: highest, lowest, and average temperature
    async_add_entities([
        ThermalCameraTemperatureSensor(
            coordinator,
            config_entry,
            "highest",
            unique_id=config_entry.data["unique_id_highest_sensor"]
        ),
        ThermalCameraTemperatureSensor(
            coordinator,
            config_entry,
            "lowest",
            unique_id=config_entry.data["unique_id_lowest_sensor"]
        ),
        ThermalCameraTemperatureSensor(
            coordinator,
            config_entry,
            "average",
            unique_id=config_entry.data["unique_id_average_sensor"]
        ),
    ])


class ThermalCameraTemperatureSensor(SensorEntity):
    """Representation of a thermal camera temperature sensor."""

    def __init__(self, coordinator, config_entry, sensor_type, unique_id=None):
        super().__init__()
        self.coordinator = coordinator
        self._config_entry = config_entry
        self._sensor_type = sensor_type  # "highest", "lowest", or "average"
        self.field = (
            "max_value" if sensor_type == "highest" else
            "min_value" if sensor_type == "lowest" else
            "avg_value"
        )
        self._unique_id = unique_id  # Store the unique ID

        # Define sensor attributes based on the type
        self._attr_name = f"{config_entry.data.get('name', DEFAULT_NAME)} {sensor_type.capitalize()} Temperature"
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}_temperature" if not unique_id else unique_id
        self._attr_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = "temperature"  # Optional: assign a device class for better UI display

        # Register this sensor to listen for updates from the coordinator
        self.coordinator.async_add_listener(self.async_write_ha_state)

    @property
    def state(self):
        """Return the current temperature value for this sensor type."""
        data = self.coordinator.data
        if data:
            return data.get(self.field)
        return None

    @property
    def device_info(self):
        """Return device information to group this sensor with the main thermal camera device."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": self._config_entry.data.get("name", DEFAULT_NAME),
            "manufacturer": "Your Manufacturer",
            "model": "Thermal Camera Sensor",
        }

    async def async_update(self):
        """Update the sensor based on coordinator data."""
        data = self.coordinator.data

        if data is None:
            _LOGGER.warning(f"{self.name}: Coordinator data is not available.")
            return
        
        # Update internal state directly from the coordinator data
        self._attr_native_value = data.get(self.field)
        if self._attr_native_value is None:
            _LOGGER.warning(f"{self.name}: Missing '{self.field}' data in coordinator response.")

    async def async_will_remove_from_hass(self):
        """Clean up when the entity is removed from Home Assistant."""
        # Remove the update listener if registered
        if hasattr(self, "async_write_ha_state"):
            self.coordinator.async_remove_listener(self.async_write_ha_state)
