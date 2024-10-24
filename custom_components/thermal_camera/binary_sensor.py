import logging
import aiohttp
import async_timeout
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_NAME, CONF_URL
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Thermal Motion Sensor"
MOTION_THRESHOLD = 8  # Adjust this value based on your testing

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.url,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the thermal motion sensor asynchronously."""
    name = config[CONF_NAME]
    url = config[CONF_URL]
    async_add_entities([ThermalMotionSensor(name, url)])

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

    async def async_update(self):
        """Fetch the latest data from the URL and update the sensor state asynchronously."""
        try:
            _LOGGER.debug("Fetching data from URL: %s", self._url)
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.get(self._url) as response:
                        if response.status != 200:
                            _LOGGER.error("Error fetching data, status code: %s", response.status)
                            self._is_on = False
                            return
                        data = await response.json()

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

        except aiohttp.ClientError as e:
            _LOGGER.error("Error fetching data from %s: %s", self._url, e)
            self._is_on = False
        except Exception as e:
            _LOGGER.error("Unexpected error: %s", e)
            self._is_on = False
