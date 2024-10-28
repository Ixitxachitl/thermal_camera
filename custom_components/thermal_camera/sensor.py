import uuid
import logging
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import DEVICE_CLASS_TEMPERATURE
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .constants import DOMAIN, DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the thermal temperature sensors from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id].get("coordinator")
    name = config_entry.data.get("name", DEFAULT_NAME)
    unique_id_prefix = config_entry.data.get("unique_id")

    sensors = [
        ThermalTemperatureSensor(coordinator, name, unique_id_prefix, "lowest", "Lowest Temperature"),
        ThermalTemperatureSensor(coordinator, name, unique_id_prefix, "highest", "Highest Temperature"),
        ThermalTemperatureSensor(coordinator, name, unique_id_prefix, "average", "Average Temperature")
    ]

    async_add_entities(sensors)

class ThermalTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Thermal Temperature Sensor."""

    def __init__(self, coordinator, name, unique_id_prefix, temp_type, sensor_name):
        """Initialize the temperature sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._attr_name = f"{name} {sensor_name}"
        self._attr_unique_id = f"{unique_id_prefix}_{temp_type}_temperature"
        self._temp_type = temp_type
        self._attr_device_class = DEVICE_CLASS_TEMPERATURE
        self._attr_unit_of_measurement = None  # Don't specify unit (C/F) since input could be either

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._coordinator.data is None:
            return None

        if self._temp_type == "lowest":
            return self._coordinator.data.get("lowest_field")
        elif self._temp_type == "highest":
            return self._coordinator.data.get("highest_field")
        elif self._temp_type == "average":
            return self._coordinator.data.get("average_field")

        return None

    @property
    def device_info(self):
        """Return device information to group sensors together."""
        return {
            "identifiers": {(DOMAIN, self._coordinator.config_entry.entry_id)},
            "name": self._coordinator.config_entry.data.get("name", DEFAULT_NAME),
            "manufacturer": "Your Manufacturer",
            "model": "Thermal Camera",
        }
