# import asyncio
import logging
import os
import uuid
import aiohttp
# import socket
from aiohttp import web
# import threading
from homeassistant.components.camera import Camera
from homeassistant.helpers.network import get_url
from .constants import DOMAIN, DEFAULT_NAME, DEFAULT_ROWS, DEFAULT_COLS, DEFAULT_DATA_FIELD, DEFAULT_LOWEST_FIELD, DEFAULT_HIGHEST_FIELD, DEFAULT_AVERAGE_FIELD, DEFAULT_RESAMPLE_METHOD, DEFAULT_MJPEG_PORT, DEFAULT_DESIRED_HEIGHT
from .frame_processor import process_frame
from .coordinator import ThermalCameraDataCoordinator
from PIL import Image, ImageFont
import numpy as np
import hashlib

_LOGGER = logging.getLogger(__name__)

FONT_PATH = os.path.join(os.path.dirname(__file__), 'DejaVuSans-Bold.ttf')

# Resample method mappings
RESAMPLE_METHODS = {
    "NEAREST": Image.NEAREST,
    "BILINEAR": Image.BILINEAR,
    "BICUBIC": Image.BICUBIC,
    "LANCZOS": Image.LANCZOS,
}

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the thermal camera platform from a config entry."""
    config = config_entry.data

    # Retrieve the shared coordinator instance from hass.data
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    # Retrieve configuration values with defaults
    name = config.get("name", DEFAULT_NAME)
    rows = config.get("rows", DEFAULT_ROWS)
    cols = config.get("columns", DEFAULT_COLS)
    data_field = config.get("data_field", DEFAULT_DATA_FIELD)
    lowest_field = config.get("lowest_field", DEFAULT_LOWEST_FIELD)
    highest_field = config.get("highest_field", DEFAULT_HIGHEST_FIELD)
    average_field = config.get("average_field", DEFAULT_AVERAGE_FIELD)
    resample_method = RESAMPLE_METHODS.get(config.get("resample", DEFAULT_RESAMPLE_METHOD), Image.NEAREST)
    mjpeg_port = config.get("mjpeg_port", DEFAULT_MJPEG_PORT)
    desired_height = config.get("desired_height", DEFAULT_DESIRED_HEIGHT)

    # Initialize or reuse the session
    session = hass.data.get("thermal_camera_session")
    if session is None or session.closed:
        session = aiohttp.ClientSession()
        hass.data["thermal_camera_session"] = session

    # Generate a unique ID if it does not already exist
    unique_id = config_entry.data.get("unique_id")
    if unique_id is None:
        unique_id = str(uuid.uuid4())
        hass.config_entries.async_update_entry(config_entry, data={**config_entry.data, "unique_id": unique_id})

    # Add the thermal camera entity
    async_add_entities([
        ThermalCamera(
            name=name,
            coordinator=coordinator,
            rows=rows,
            cols=cols,
            data_field=data_field,
            lowest_field=lowest_field,
            highest_field=highest_field,
            average_field=average_field,
            resample_method=resample_method,
            session=session,
            mjpeg_port=mjpeg_port,
            desired_height=desired_height,
            config_entry=config_entry,
            unique_id=unique_id,
        )
    ], update_before_add=True)

class ThermalCamera(Camera):
    """Representation of a thermal camera using centralized polling with a DataUpdateCoordinator."""

    def __init__(self, name, coordinator, rows, cols, data_field, lowest_field, highest_field, average_field, resample_method, session, mjpeg_port, desired_height, config_entry=None, unique_id=None):
        super().__init__()
        self._config_entry = config_entry
        self._name = name
        self.coordinator = coordinator  # Use the coordinator for centralized polling
        self._rows = rows
        self._cols = cols
        self._data_field = data_field
        self._lowest_field = lowest_field
        self._highest_field = highest_field
        self._average_field = average_field
        self._resample_method = resample_method
        self._session = session
        self._unique_id = unique_id
        self._frame = None  # Initialize frame as None
        # self._frame_lock = threading.Lock()
        self._mjpeg_port = mjpeg_port
        self._desired_height = desired_height
        self._last_frame_data = None  # Store a hash of the last processed frame

        # Load font data
        try:
            self._font = ImageFont.truetype(FONT_PATH, 30)
        except IOError:
            _LOGGER.error("Failed to load DejaVu font, using default font.")
            self._font = ImageFont.load_default()

        # Set up MJPEG server for streaming
        # self._app = web.Application()
        # self._app.router.add_get('/mjpeg', self.handle_mjpeg)
        # self._runner = web.AppRunner(self._app)
        # self._loop = asyncio.get_event_loop()
        # threading.Thread(target=self.start_server).start()

        # Listen for updates from the coordinator
        self._remove_listener = None

    # def start_server(self):
    #     """Start the MJPEG server for streaming."""
    #     async def run_server():
    #         await self._runner.setup()
    #         site = web.TCPSite(self._runner, '0.0.0.0', self._mjpeg_port)
    #         await site.start()

    #     asyncio.run_coroutine_threadsafe(run_server(), self._loop)

    # async def handle_mjpeg(self, request):
    #     response = web.StreamResponse(
    #         status=200,
    #         reason='OK',
    #         headers={'Content-Type': 'multipart/x-mixed-replace; boundary=--frame'}
    #     )
    #     await response.prepare(request)

    #     try:
    #         while True:
    #             with self._frame_lock:
    #                 frame = self._frame

    #             if frame:
    #                 await response.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
    #             else:
    #                 _LOGGER.info("MJPEG stream has no frame data; waiting for update.")
    #             await asyncio.sleep(0.1)
    #     except asyncio.CancelledError:
    #         pass
    #     return response

    async def async_update(self):
        """Request a data refresh from the coordinator and update the frame only if there's new data."""
        _LOGGER.debug("ThermalCamera async_update called")
        data = self.coordinator.data

        if data is None or "frame_data" not in data:
            _LOGGER.info("No valid frame data available from coordinator.")
            return

        # Check if frame_data is empty and handle appropriately
        frame_data = data["frame_data"]
        if len(frame_data) == 0:
            _LOGGER.warning("Received empty frame_data. Using default empty array.")
            frame_data = np.zeros((self._rows, self._cols))  # Create an empty array of the correct shape
        else:
            # Convert frame_data to a NumPy array and reshape
            frame_data = np.array(frame_data).reshape(self._rows, self._cols)

        # Compute checksum and update frame if necessary
        frame_checksum = hashlib.md5(frame_data.tobytes()).hexdigest()
        if frame_checksum != self._last_frame_data:
            self._frame = process_frame(
                frame_data,
                data["min_value"],
                data["max_value"],
                data["avg_value"],
                self._rows,
                self._cols,
                self._resample_method,
                self._font,
                self._desired_height
            )
            self._last_frame_data = frame_checksum
            _LOGGER.debug("Frame updated with new data.")

    @property
    def unique_id(self):
        """Return a unique ID for the camera."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information to group camera and binary sensor."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": self._config_entry.data.get("name", DEFAULT_NAME),
            "manufacturer": "Your Manufacturer",
            "model": "Thermal Camera",
        }

    @property
    def name(self):
        """Return the name of the camera."""
        return self._name

    async def async_camera_image(self, width=None, height=None):
        """Return the camera image asynchronously."""
        # with self._frame_lock:
        return self._frame

    # def get_local_ip(self):
    #     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #     try:
    #         s.connect(("8.8.8.8", 80))
    #         local_ip = s.getsockname()[0]
    #     except Exception:
    #         local_ip = "127.0.0.1"
    #     finally:
    #         s.close()
    #     return local_ip

    async def async_stream_source(self):
        """Return the URL of the video stream."""
        if self.hass and self.entity_id:
            # Generate an access token to be used for streaming
            access_token = self.access_tokens[-1] if self.access_tokens else None
            if access_token:
                return f"{get_url(self.hass)}/api/camera_proxy_stream/{self.entity_id}?token={access_token}"
        
        # Fallback URL if Home Assistant is not available
        # local_ip = self.get_local_ip()
        # eturn f'http://{local_ip}:{self._mjpeg_port}/mjpeg'
        return None
      
    @property
    def should_poll(self):
        """Camera polling is required."""
        return True

    async def async_added_to_hass(self):
        """Called when the entity is added to Home Assistant."""
        # Now attach the listener since hass is guaranteed to be available
        self._remove_listener = self.coordinator.async_add_listener(self.async_write_ha_state) 

    async def async_will_remove_from_hass(self):
        """Clean up when the sensor is removed from Home Assistant."""
        if self._remove_listener:
            self._remove_listener()  # Remove the listener when removing the entity
            self._remove_listener = None

        # # Stop the MJPEG server properly
        # if self._runner is not None:
        #     await self._runner.cleanup()

        # # Ensure all related resources are cleaned up
        # if self._session and not self._session.closed:
        #     await self._session.close()
