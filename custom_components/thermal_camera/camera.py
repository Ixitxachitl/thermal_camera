import asyncio
import logging
import os
import aiohttp
import async_timeout
import socket
from io import BytesIO
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_URL
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from aiohttp import web
import threading

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Thermal Camera"
DEFAULT_ROWS, DEFAULT_COLS = 24, 32
DEFAULT_PATH = "json"
DEFAULT_DATA_FIELD = "frame"
DEFAULT_LOW_FIELD = "lowest"
DEFAULT_HIGH_FIELD = "highest"
DEFAULT_RESAMPLE_METHOD = "NEAREST"
FONT_PATH = os.path.join(os.path.dirname(__file__), 'DejaVuSans-Bold.ttf')

CONF_DIMENSIONS = "dimensions"
CONF_ROWS = "rows"
CONF_COLUMNS = "columns"
CONF_PATH = "path"
CONF_DATA_FIELD = "data_field"
CONF_LOW_FIELD = "low_field"
CONF_HIGH_FIELD = "high_field"
CONF_RESAMPLE = "resample"

RESAMPLE_METHODS = {
    "NEAREST": Image.NEAREST,
    "BILINEAR": Image.BILINEAR,
    "BICUBIC": Image.BICUBIC,
    "LANCZOS": Image.LANCZOS,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_URL): cv.url,
    vol.Optional(CONF_DIMENSIONS, default={}): vol.Schema({
        vol.Optional(CONF_ROWS, default=DEFAULT_ROWS): cv.positive_int,
        vol.Optional(CONF_COLUMNS, default=DEFAULT_COLS): cv.positive_int,
    }),
    vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
    vol.Optional(CONF_DATA_FIELD, default=DEFAULT_DATA_FIELD): cv.string,
    vol.Optional(CONF_LOW_FIELD, default=DEFAULT_LOW_FIELD): cv.string,
    vol.Optional(CONF_HIGH_FIELD, default=DEFAULT_HIGH_FIELD): cv.string,
    vol.Optional(CONF_RESAMPLE, default=DEFAULT_RESAMPLE_METHOD): vol.In(RESAMPLE_METHODS.keys()),
})

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the thermal camera platform asynchronously."""
    name = config.get(CONF_NAME)
    url = config.get(CONF_URL)
    dimensions = config.get(CONF_DIMENSIONS)
    rows = dimensions.get(CONF_ROWS, DEFAULT_ROWS)
    cols = dimensions.get(CONF_COLUMNS, DEFAULT_COLS)
    path = config.get(CONF_PATH)
    data_field = config.get(CONF_DATA_FIELD)
    low_field = config.get(CONF_LOW_FIELD)
    high_field = config.get(CONF_HIGH_FIELD)
    resample_method = RESAMPLE_METHODS[config.get(CONF_RESAMPLE)]

    # Reuse or create a persistent session for this platform
    session = hass.data.get("thermal_camera_session")
    if session is None:
        session = aiohttp.ClientSession()
        hass.data["thermal_camera_session"] = session

    async_add_entities([ThermalCamera(name, url, rows, cols, path, data_field, low_field, high_field, resample_method, session)], True)

class ThermalCamera(Camera):
    """Representation of a thermal camera."""

    def __init__(self, name, url, rows, cols, path, data_field, low_field, high_field, resample_method, session):
        """Initialize the thermal camera."""
        super().__init__()
        self._name = name
        self._url = url
        self._rows = rows
        self._cols = cols
        self._path = path
        self._data_field = data_field
        self._low_field = low_field
        self._high_field = high_field
        self._resample_method = resample_method
        self._session = session
        self._frame = None
        self._app = web.Application()
        self._app.router.add_get('/mjpeg', self.handle_mjpeg)
        self._runner = web.AppRunner(self._app)
        self._loop = asyncio.get_event_loop()
        threading.Thread(target=self.start_server).start()
        try:
            self._font = ImageFont.truetype(FONT_PATH, 40)  # Load DejaVu font
        except IOError:
            _LOGGER.error("Failed to load DejaVu font, using default font.")
            self._font = ImageFont.load_default()

    def start_server(self):
        asyncio.run_coroutine_threadsafe(self._runner.setup(), self._loop)
        asyncio.run_coroutine_threadsafe(web.TCPSite(self._runner, '0.0.0.0', 8169).start(), self._loop)

    async def handle_mjpeg(self, request):
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'multipart/x-mixed-replace; boundary=--frame'
            }
        )
        await response.prepare(request)

        try:
            while True:
                await self.fetch_data()
                if self._frame:
                    await response.write(
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + self._frame + b"\r\n"
                    )
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        return response

    @property
    def name(self):
        """Return the name of the camera."""
        return self._name

    def map_to_color(self, value, min_value, max_value):
        """Map thermal value to a simplified color gradient from black to white."""
        # Normalize the value between 0 and 1
        normalized = max(0.0, min(1.0, (value - min_value) / (max_value - min_value)))

        # Define the gradient mapping
        if normalized < 0.2:  # Black to Blue
            r = 0
            g = 0
            b = int(255 * (normalized / 0.2))
        elif normalized < 0.4:  # Blue to Green
            r = 0
            g = int(255 * ((normalized - 0.2) / 0.2))
            b = 255
        elif normalized < 0.6:  # Green to Yellow
            r = int(255 * ((normalized - 0.4) / 0.2))
            g = 255
            b = 0
        elif normalized < 0.8:  # Yellow to Red
            r = 255
            g = int(255 * (1 - (normalized - 0.6) / 0.2))
            b = 0
        else:  # Red to White
            r = 255
            g = int(255 * ((normalized - 0.8) / 0.2))
            b = int(255 * ((normalized - 0.8) / 0.2))

        # Convert to integers and return RGB tuple
        return (int(r), int(g), int(b))

    async def fetch_data(self):
        """Fetch data from the URL and process the frame asynchronously."""
        try:
            _LOGGER.debug("Fetching data from URL: %s", self._url)
            async with async_timeout.timeout(20):
                async with self._session.get(f"{self._url}/{self._path}") as response:
                    if response.status != 200:
                        _LOGGER.error("Error fetching data, status code: %s", response.status)
                        return

                    data = await response.json()

            frame_data = np.array(data[self._data_field]).reshape(self._rows, self._cols)
            min_value = data[self._low_field]
            max_value = data[self._high_field]

            _LOGGER.debug("Frame data fetched successfully. Min: %s, Max: %s", min_value, max_value)

            # Create an RGB image using PIL
            img = Image.new("RGB", (self._cols, self._rows))
            _LOGGER.debug("Initial image created. Image mode: %s, Image size: %s", img.mode, img.size)
            draw = ImageDraw.Draw(img)

            # Map frame data to colors
            for r in range(self._rows):
                for c in range(self._cols):
                    color = self.map_to_color(frame_data[r, c], min_value, max_value)
                    draw.point((c, r), fill=color)

            # Scale up the image
            scale_factor = 20
            img = img.resize((self._cols * scale_factor, self._rows * scale_factor), resample=self._resample_method)
            _LOGGER.debug("Image resized. New size: %s", img.size)

            # Reinitialize ImageDraw after resizing
            draw = ImageDraw.Draw(img)

            # Draw a reticle on the pixel with the highest temperature
            max_index = np.argmax(frame_data)
            max_row, max_col = divmod(max_index, self._cols)

            # Scale the coordinates
            center_x = (max_col + 0.5) * scale_factor
            center_y = (max_row + 0.5) * scale_factor
            reticle_radius = 9

            # Draw crosshairs and reticle (keeping everything in RGB mode)
            _LOGGER.debug("Drawing reticle at coordinates: (%s, %s)", center_x, center_y)
            draw.line(
                [(center_x, center_y - reticle_radius), (center_x, center_y + reticle_radius)],
                fill="red",
                width=1
            )
            draw.line(
                [(center_x - reticle_radius, center_y), (center_x + reticle_radius, center_y)],
                fill="red",
                width=1
            )
            draw.ellipse(
                [(center_x - reticle_radius + 2, center_y - reticle_radius + 2),
                (center_x + reticle_radius - 2, center_y + reticle_radius - 2)],
                outline="red",
                width=1
            )

            # Draw the highest temperature text after scaling
            text = f"{frame_data[max_row, max_col]:.1f}°"
            if max_row >= self._rows - 3:
                # If the reticle is in the bottom three rows, move the text above the reticle
                text_y = max(center_y - 50, 0)
            else:
                # Otherwise, place the text below the reticle
                text_y = min(center_y + reticle_radius, img.height)
            text_x = min(max(center_x, 0), img.width - 120)

            _LOGGER.debug(f"Text coordinates: ({text_x}, {text_y}), Text: {text}")

            # Draw the text with shadow
            self.draw_text_with_shadow(img, text_x, text_y, text, self._font)

            # Convert to JPEG bytes
            self._frame = self.image_to_jpeg_bytes(img)
            _LOGGER.debug("Image converted to JPEG bytes successfully.")
        except Exception as e:
            _LOGGER.error("Error fetching or processing data: %s", e, exc_info=True)

    def draw_text_with_shadow(self, img, text_x, text_y, text, font):
        """Draw text with both a black border and a semi-transparent shadow."""
        # Create a separate layer to draw the semi-transparent shadow
        shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))  # Create a fully transparent RGBA layer
        shadow_draw = ImageDraw.Draw(shadow_layer)

        # Define shadow properties
        shadow_offset = 5  # Offset for the shadow
        shadow_color = (0, 0, 0, 100)  # Semi-transparent black

        # Draw the semi-transparent shadow
        shadow_draw.text(
            (text_x + shadow_offset, text_y + shadow_offset),
            text,
            font=font,
            fill=shadow_color
        )

        # Add the shadow layer to the main image
        img_rgba = img.convert("RGBA")
        combined = Image.alpha_composite(img_rgba, shadow_layer)

        # Convert back to RGB (to remove the alpha channel)
        img_rgb = combined.convert("RGB")
        img.paste(img_rgb)

        # Reinitialize ImageDraw for drawing on the combined image
        draw = ImageDraw.Draw(img)

        # Draw the black border
        border_offset = 2  # Border thickness
        for dx in range(-border_offset, border_offset + 1):
            for dy in range(-border_offset, border_offset + 1):
                if dx != 0 or dy != 0:
                    draw.text((text_x + dx, text_y + dy), text, fill="black", font=font)

        # Draw the main text (white) in the center
        draw.text((text_x, text_y), text, fill="white", font=font)

    def image_to_jpeg_bytes(self, img):
        """Convert PIL image to JPEG bytes."""
        with BytesIO() as output:
            img.save(output, format="JPEG")
            return output.getvalue()

    async def async_camera_image(self, width=None, height=None):
        """Return the camera image asynchronously."""
        await self.fetch_data()
        await asyncio.sleep(0.5)
        return self._frame

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # This does not need to be reachable
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = "127.0.0.1"
        finally:
            s.close()
        return local_ip

    def stream_source(self):
        """Return the URL of the video stream."""
        local_ip = self.get_local_ip()
        return f'http://{local_ip}:8169/mjpeg'

    @property
    def should_poll(self):
        """Camera polling is required."""
        return True

    async def async_will_remove_from_hass(self):
        """Called when the entity is about to be removed from Home Assistant."""
        if self._session is not None:
            await self._session.close()
