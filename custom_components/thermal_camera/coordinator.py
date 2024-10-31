import logging
import aiohttp
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

class ThermalCameraDataCoordinator(DataUpdateCoordinator):
    """Class to manage polling data from the thermal camera API."""

    def __init__(self, hass, session, url, path, data_field, lowest_field, highest_field, average_field):
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
        self.data_field = data_field
        self.lowest_field = lowest_field
        self.highest_field = highest_field
        self.average_field = average_field

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

            # Extract relevant data with defaults for missing fields
            frame_data = data.get(self.data_field)
            min_value = data.get(self.lowest_field)
            max_value = data.get(self.highest_field)
            avg_value = data.get(self.average_field)

            # Log and warn if any expected field is missing
            missing_fields = [
                field_name
                for field_name, field_value in {
                    self.data_field: frame_data,
                    self.lowest_field: min_value,
                    self.highest_field: max_value,
                    self.average_field: avg_value,
                }.items()
                if field_value is None
            ]
            if missing_fields:
                _LOGGER.warning("Missing fields in response data: %s", ", ".join(missing_fields))

            # Ensure returned data meets expected structure
            return {
                "frame_data": frame_data if frame_data is not None else [],
                "min_value": min_value if min_value is not None else 0.0,
                "max_value": max_value if max_value is not None else 0.0,
                "avg_value": avg_value if avg_value is not None else 0.0,
            }

        except Exception as e:
            raise UpdateFailed(f"Error communicating with API: {e}")
