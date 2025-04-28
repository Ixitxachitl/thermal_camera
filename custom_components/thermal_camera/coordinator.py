import asyncio
import logging
import aiohttp
from datetime import timedelta
import async_timeout
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

class ThermalCameraDataCoordinator(DataUpdateCoordinator):
    """Class to manage polling data from the thermal camera API."""

    def __init__(self, hass, session, url, path, data_field, lowest_field, highest_field, average_field):
        super().__init__(
            hass,
            _LOGGER,
            name="Thermal Camera Data Coordinator",
            update_interval=timedelta(milliseconds=500),  # Keep fast 500ms updates
        )
        self.session = session
        self.url = url
        self.path = path
        self.data_field = data_field
        self.lowest_field = lowest_field
        self.highest_field = highest_field
        self.average_field = average_field
        self._last_data = {
            "frame_data": [],
            "min_value": 0.0,
            "max_value": 0.0,
            "avg_value": 0.0
        }

    async def _async_update_data(self):
        """Fetch data from the camera API, retaining last known data if fetch fails."""
        try:
            _LOGGER.debug("Attempting to fetch data from the thermal camera API.")
            start = asyncio.get_event_loop().time()
            async with async_timeout.timeout(1.5):  # Faster timeout to detect issues sooner
                async with self.session.get(f"{self.url}/{self.path}", headers={"Connection": "close"}) as response:
                    duration = asyncio.get_event_loop().time() - start
                    _LOGGER.debug(f"Fetch took {duration:.2f} seconds")

                    if response.status != 200:
                        _LOGGER.warning(f"Failed to fetch data: {response.status}")
                        return self._last_data

                    data = await response.json()
                    self._last_data = {
                        "frame_data": data.get(self.data_field, []),
                        "min_value": data.get(self.lowest_field, 0.0),
                        "max_value": data.get(self.highest_field, 0.0),
                        "avg_value": data.get(self.average_field, 0.0),
                    }
                    _LOGGER.debug("Data fetched and processed successfully.")

                    self.async_update_listeners()

                    return self._last_data

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error(f"Network error fetching data: {e}")
            return self._last_data
        except Exception as e:
            _LOGGER.error(f"Unexpected error communicating with API: {e}")
            return self._last_data
