import logging
import aiohttp
import async_timeout
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_NAME, CONF_URL
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Thermal Motion Sensor"
DEFAULT_MOTION_THRESHOLD = 8
DEFAULT_PATH = "json"
DEFAULT_AVERAGE_FIELD = "average"
DEFAULT_HIGHEST_FIELD = "highest"

CONF_PATH = "path"
CONF_MOTION_THRESHOLD = "motion_threshold"
CONF_AVERAGE_FIELD = "average_field"
CONF_HIGHEST_FIELD = "highest_field"

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.url,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
    vol.Optional(CONF_MOTION_THRESHOLD, default=DEFAULT_MOTION_THRESHOLD): cv.positive_int,
    vol.Optional(CONF_AVERAGE_FIELD, default=DEFAULT_AVERAGE_FIELD): cv.string,
    vol.Optional(CONF_HIGHEST_FIELD, default=DEFAULT_HIGHEST_FIELD): cv.string,
})

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the thermal motion sensor asynchronously."""
    name = config[CONF_NAME]
    url = config[CONF_URL]
    path = config[CONF_PATH]
    motion_threshold = config[CONF_MOTION_THRESHOLD]
    average_field = config[CONF_AVERAGE_FIELD]
    highest_field = config[CONF_HIGHEST_FIELD]

    # Reuse or create a persistent session for this platform
    session = hass.data.get("thermal_camera_session")
    if session is None:
        session = aiohttp.ClientSession()
        hass.data["thermal_camera_session"] = session

    async_add_entities([ThermalMotionSensor(name, url, path, motion_threshold, average_field, highest_field, session)])

class ThermalMotionSensor(BinarySensorEntity):
    """Representation of a thermal motion detection sensor."""

    def __init__(self, name, url, path, motion_threshold, average_field, highest_field, session):
        """Initialize the motion sensor."""
        self._name = name
        self._url = f"{url}/{path}"
        self._motion_threshold = motion_threshold
        self._average_field = average_field
        self._highest_field = highest_field
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

            avg_temp = data.get(self._average_field)
            max_temp = data.get(self._highest_field)

            if avg_temp is None or max_temp is None:
                _LOGGER.error("Missing '%s' or '%s' in JSON response", self._average_field, self._highest_field)
                return

            temp_diff = max_temp - avg_temp
            self._is_on = temp_diff > self._motion_threshold

        except aiohttp.ClientError as e:
            _LOGGER.error("Client error when fetching data from %s: %s", self._url, e)
            self._is_on = False
        except Exception as e:
            _LOGGER.error("Unexpected error during async_update: %s", e)
            self._is_on = False
