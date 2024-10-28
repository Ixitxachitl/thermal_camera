import aiohttp
import async_timeout
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from datetime import timedelta
import logging

_LOGGER = logging.getLogger(__name__)

class ThermalDataCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, session, url, path):
        """Initialize the data coordinator."""
        self._session = session
        self._url = f"{url}/{path}"
        super().__init__(
            hass,
            _LOGGER,
            name="Thermal Data Coordinator",
            update_interval=timedelta(seconds=0.5),  # Set the update frequency
        )

    async def _async_update_data(self):
        """Fetch data from the thermal camera."""
        try:
            _LOGGER.debug("Fetching data from URL: %s", self._url)
            async with async_timeout.timeout(10):
                async with self._session.get(self._url) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"Error fetching data: {response.status}")
                    return await response.json()
        except aiohttp.ClientError as e:
            raise UpdateFailed(f"Client error: {e}")
        except Exception as e:
            raise UpdateFailed(f"Unexpected error: {e}")
