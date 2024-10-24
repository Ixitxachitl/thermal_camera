import logging
import aiohttp
import async_timeout
from io import BytesIO
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_URL
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Thermal Camera"
ROWS, COLS = 24, 32

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_URL): cv.url,
})

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the thermal camera platform asynchronously."""
    name = config.get(CONF_NAME)
    url = config.get(CONF_URL)

    # Reuse or create a persistent session for this platform
    session = hass.data.get("thermal_camera_session")
    if session is None:
        session = aiohttp.ClientSession()
        hass.data["thermal_camera_session"] = session

    async_add_entities([ThermalCamera(name, url, session)], True)

class ThermalCamera(Camera):
    """Representation of a thermal camera."""

    def __init__(self, name, url, session):
        """Initialize the thermal camera."""
        super().__init__()
        self._name = name
        self._url = url
        self._session = session
        self._frame = None

    @property
    def name(self):
        """Return the name of the camera."""
        return self._name

    def map_to_color(self, value, min_value, max_value):
        """Map the thermal value to a color with yellow in the mid-range."""
        normalized = (value - min_value) / (max_value - min_value)
        if normalized < 0.5:
            # Interpolate between blue and yellow
            b = int(255 * (1 - 2 * normalized))
            g = int(255 * (2 * normalized))
            r = 0
        else:
            # Interpolate between yellow and red
            b = 0
            g = int(255 * (2 * (1 - normalized)))
            r = int(255 * (2 * (normalized - 0.5)))
        return (r, g, b)

    async def fetch_data(self):
        """Fetch data from the URL and process the frame asynchronously."""
        try:
            _LOGGER.debug("Fetching data from URL: %s", self._url)
            async with async_timeout.timeout(10):
                async with self._session.get(f"{self._url}/json") as response:
                    if response.status != 200:
                        _LOGGER.error("Error fetching data, status code: %s", response.status)
                        return

                    data = await response.json()

            frame_data = np.array(data["frame"]).reshape(ROWS, COLS)
            min_value = data["lowest"]
            max_value = data["highest"]

            _LOGGER.debug("Frame data fetched successfully. Min: %s, Max: %s", min_value, max_value)

            # Create an RGB image using PIL
            img = Image.new("RGB", (COLS, ROWS))
            draw = ImageDraw.Draw(img)

            # Map frame data to colors
            for r in range(ROWS):
                for c in range(COLS):
                    color = self.map_to_color(frame_data[r, c], min_value, max_value)
                    draw.point((c, r), fill=color)

            # Scale up the image
            scale_factor = 20
            img = img.resize((COLS * scale_factor, ROWS * scale_factor), resample=Image.BICUBIC)

            # Draw the highest temperature text after scaling
            max_index = np.argmax(frame_data)
            max_row, max_col = divmod(max_index, COLS)
            text = f"{frame_data[max_row, max_col]:.1f}°"
            text_x = min(max_col * scale_factor, img.width - 100)
            text_y = min(max_row * scale_factor, img.height - 40)

            # Load Google Font for text
            font_url = "https://github.com/google/fonts/raw/main/ofl/spacemono/SpaceMono-Regular.ttf"
            try:
                async with self._session.get(font_url) as font_response:
                    font_response.raise_for_status()
                    font_data = await font_response.read()
                    font = ImageFont.truetype(BytesIO(font_data), 40)  # Increased font size
                    _LOGGER.debug("Google Font loaded successfully.")
            except Exception as e:
                _LOGGER.error(f"Failed to load Google Font: {e}")
                font = ImageFont.load_default()
                _LOGGER.debug("Using default font.")

            # Draw the text with a shadow for visibility
            shadow_offset = 3
            for dx in range(-shadow_offset, shadow_offset + 1):
                for dy in range(-shadow_offset, shadow_offset + 1):
                    if dx != 0 or dy != 0:
                        draw.text((text_x + dx, text_y + dy), text, fill="black", font=font)

            # Draw the main text (white)
            draw.text((text_x, text_y), text, fill="white", font=font)

            # Convert to JPEG bytes
            self._frame = self.image_to_jpeg_bytes(img)
            _LOGGER.debug("Image converted to JPEG bytes successfully.")
        except Exception as e:
            _LOGGER.error("Error fetching or processing data: %s", e)

    def image_to_jpeg_bytes(self, img):
        """Convert PIL image to JPEG bytes."""
        with BytesIO() as output:
            img.save(output, format="JPEG")
            return output.getvalue()

    async def async_camera_image(self, width=None, height=None):
        """Return the camera image asynchronously."""
        await self.fetch_data()
        return self._frame

    def stream_source(self):
        """Return the URL of the video stream."""
        return None

    @property
    def should_poll(self):
        """Camera polling is required."""
        return True
