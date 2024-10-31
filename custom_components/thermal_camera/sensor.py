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
        ThermalCameraTemperatureSensor(coordinator, config_entry, "highest"),
        ThermalCameraTemperatureSensor(coordinator, config_entry, "lowest"),
        ThermalCameraTemperatureSensor(coordinator, config_entry, "average"),
    ], update_before_add=True)


class ThermalCameraTemperatureSensor(SensorEntity):
    """Representation of a thermal camera temperature sensor."""

    def __init__(self, coordinator, config_entry, sensor_type):
        super().__init__()
        self.coordinator = coordinator
        self._config_entry = config_entry
        self._sensor_type = sensor_type  # "highest", "lowest", or "average"
        
        # Define sensor attributes based on the type
        self._attr_name = f"{config_entry.data.get('name', DEFAULT_NAME)} {sensor_type.capitalize()} Temperature"
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}_temperature"
        self._attr_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = "temperature"  # Optional: assign a device class for better UI display

        # Register this sensor to listen for updates from the coordinator
        self.coordinator.async_add_listener(self.async_write_ha_state)

    @property
    def state(self):
        """Return the current temperature value for this sensor type."""
        data = self.coordinator.data
        if data:
            return data.get(self._sensor_type)
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
        """Request a data refresh from the coordinator and update the state."""
        await self.coordinator.async_request_refresh()
        data = self.coordinator.data

        # Check if data is available and has the required field
        if data:
            temp_value = data.get(self._sensor_type)
            if temp_value is not None:
                self._attr_native_value = temp_value
            else:
                _LOGGER.error(f"Missing '{self._sensor_type}' data in coordinator response.")
        else:
            _LOGGER.error("No data received from coordinator.")

    async def async_will_remove_from_hass(self):
        """Cleanup when the sensor is about to be removed."""
        # Remove the update listener from the coordinator
        self.coordinator.async_remove_listener(self.async_write_ha_state)
