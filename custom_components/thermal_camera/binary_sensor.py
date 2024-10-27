import logging
import aiohttp
import async_timeout
from homeassistant.components.binary_sensor import BinarySensorEntity
from .constants import DOMAIN, DEFAULT_NAME, DEFAULT_MOTION_THRESHOLD, DEFAULT_PATH, DEFAULT_AVERAGE_FIELD, DEFAULT_HIGH_FIELD, CONF_PATH, CONF_MOTION_THRESHOLD, CONF_AVERAGE_FIELD, CONF_HIGHEST_FIELD
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)



async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the thermal motion sensor from a config entry."""
    config = config_entry.data
    name = config.get(CONF_NAME, DEFAULT_NAME)
    url = config.get(CONF_URL)
    path = config.get(CONF_PATH, DEFAULT_PATH)
    motion_threshold = config.get(CONF_MOTION_THRESHOLD, DEFAULT_MOTION_THRESHOLD)
    average_field = config.get(CONF_AVERAGE_FIELD, DEFAULT_AVERAGE_FIELD)
    highest_field = config.get(CONF_HIGHEST_FIELD, DEFAULT_HIGH_FIELD)  # Use the shared field name

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
