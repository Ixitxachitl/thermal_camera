import logging
import aiohttp
import async_timeout
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_NAME, CONF_URL
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Thermal Motion Sensor"
MOTION_THRESHOLD = 8

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.url,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the thermal motion sensor asynchronously."""
    name = config[CONF_NAME]
    url = config[CONF_URL]

    # Reuse or create a persistent session for this platform
    session = hass.data.get("thermal_camera_session")
    if session is None:
        session = aiohttp.ClientSession()
        hass.data["thermal_camera_session"] = session

    async_add_entities([ThermalMotionSensor(name, url, session)])

class ThermalMotionSensor(BinarySensorEntity):
    """Representation of a thermal motion detection sensor."""

    def __init__(self, name, url, session):
        """Initialize the motion sensor."""
        self._name = name
        self._url = f"{url}/json"
        self._is_on = False
        self._session = session

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
        """Fetch data and update state."""
        try:
            _LOGGER.debug("Fetching data from URL: %s", self._url)
            async with async_timeout.timeout(10):
                async with self._session.get(self._url) as response:
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
            self._is_on = temp_diff > MOTION_THRESHOLD

        except aiohttp.ClientError as e:
            _LOGGER.error("Client error when fetching data from %s: %s", self._url, e)
            self._is_on = False
        except Exception as e:
            _LOGGER.error("Unexpected error during async_update: %s", e)
            self._is_on = False
