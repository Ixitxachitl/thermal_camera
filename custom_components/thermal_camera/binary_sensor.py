import logging
import requests
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_NAME, CONF_URL
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Thermal Motion Sensor"
MOTION_THRESHOLD = 2.5  # Adjust this value based on your testing

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_URL): cv.url,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the motion detection sensor."""
    name = config.get(CONF_NAME)
    url = config.get(CONF_URL)
    add_entities([ThermalMotionSensor(name, url)], True)

class ThermalMotionSensor(BinarySensorEntity):
    """Representation of a thermal motion detection sensor."""

    def __init__(self, name, url):
        """Initialize the motion sensor."""
        self._name = name
        self._url = f"{url}/json"
        self._is_on = False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return True if motion is detected."""
        return self._is_on

    @property
    def icon(self):
        """Return the icon for the sensor."""
        return "mdi:motion-sensor"

    def update(self):
        """Fetch the latest data from the URL and update the sensor state."""
        try:
            _LOGGER.debug("Fetching data from URL: %s", self._url)
            response = requests.get(self._url, timeout=5)
            response.raise_for_status()
            data = response.json()

            avg_temp = data.get("average")
            max_temp = data.get("highest")

            if avg_temp is None or max_temp is None:
                _LOGGER.error("Missing 'average' or 'highest' in JSON response")
                return

            temp_diff = max_temp - avg_temp

            # Determine if motion is detected based on the threshold
            self._is_on = temp_diff > MOTION_THRESHOLD

            _LOGGER.debug(
                "Motion detection update: avg_temp=%.2f, max_temp=%.2f, temp_diff=%.2f, motion=%s",
                avg_temp, max_temp, temp_diff, self._is_on
            )

        except Exception as e:
            _LOGGER.error("Error fetching or processing data: %s", e)
            self._is_on = False
