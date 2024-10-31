import logging
import aiohttp
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

class ThermalCameraDataCoordinator(DataUpdateCoordinator):
    """Class to manage polling data from the thermal camera API."""

    def __init__(self, hass, session, url, path):
        """Initialize the coordinator with necessary details."""
        super().__init__(
            hass,
            _LOGGER,
            name="Thermal Camera Data Coordinator",
            update_interval=timedelta(seconds=0.1),  # Adjust interval as needed
        )
        self.session = session
        self.url = url
        self.path = path

    async def _async_update_data(self):
        """Fetch data from the camera API."""
        try:
            async with self.session.get(f"{self.url}/{self.path}") as response:
                if response.status != 200:
                    raise UpdateFailed(f"Failed to fetch data: {response.status}")
                try:
                    data = await response.json()
                except aiohttp.ContentTypeError:
                    raise UpdateFailed("Response not in JSON format.")

            # Return relevant data fields with defaults to prevent missing keys
            return {
                "frame_data": data.get("frame_data", []),
                "min_value": data.get("min_value", 0.0),
                "max_value": data.get("max_value", 0.0),
                "avg_value": data.get("avg_value", 0.0),
            }
        except Exception as e:
            raise UpdateFailed(f"Error communicating with API: {e}")
