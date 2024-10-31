import asyncio
import logging
import aiohttp
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

class ThermalCameraDataCoordinator(DataUpdateCoordinator):
    """Class to manage polling data from the thermal camera API."""

    def __init__(self, hass, session, url, path, data_field, lowest_field, highest_field, average_field):
        super().__init__(
            hass,
            _LOGGER,
            name="Thermal Camera Data Coordinator",
            update_interval=timedelta(seconds=0.1),
        )
        self.session = session
        self.url = url
        self.path = path
        self.data_field = data_field
        self.lowest_field = lowest_field
        self.highest_field = highest_field
        self.average_field = average_field
        self._last_data = {"frame_data": [], "min_value": 0.0, "max_value": 0.0, "avg_value": 0.0}

    async def _async_update_data(self):
        """Fetch data from the camera API, retaining last known data if fetch fails."""
        try:
            async with self.session.get(f"{self.url}/{self.path}") as response:
                if response.status != 200:
                    _LOGGER.warning(f"Failed to fetch data: {response.status}")
                    return self._last_data  # Return last known good data

                data = await response.json()

                # Update _last_data with successfully fetched data
                self._last_data = {
                    "frame_data": data.get(self.data_field, []),
                    "min_value": data.get(self.lowest_field, 0.0),
                    "max_value": data.get(self.highest_field, 0.0),
                    "avg_value": data.get(self.average_field, 0.0),
                }
                return self._last_data

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error(f"Error fetching data: {e}")
            return self._last_data  # Return last known good data

        except Exception as e:
            _LOGGER.error(f"Unexpected error communicating with API: {e}")
            return self._last_data  # Return last known good data
