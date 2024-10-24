import logging
import aiohttp
import async_timeout
from io import BytesIO
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import requests
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_URL
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Thermal Camera"
ROWS, COLS = 24, 32
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/spacemono/SpaceMono-Regular.ttf"

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

    # Load the font asynchronously during setup
    font = await load_font_async(session)
    if font is None:
        font = ImageFont.load_default()
    _LOGGER.debug(f"Font loaded: {font}")

    async_add_entities([ThermalCamera(name, url, session, font)], True)

async def load_font_async(session, size=40):
    """Asynchronously load the Google Font."""
    try:
        async with async_timeout.timeout(10):
            async with session.get(FONT_URL) as response:
                if response.status != 200:
                    _LOGGER.error("Error fetching font, status code: %s", response.status)
                    return None

                font_data = await response.read()
                font = ImageFont.truetype(BytesIO(font_data), size)
                _LOGGER.debug("Google Font loaded successfully.")
                return font
    except Exception as e:
        _LOGGER.error(f"Failed to load Google Font asynchronously: {e}")
        return None

class ThermalCamera(Camera):
    """Representation of a thermal camera."""

    def __init__(self, name, url, session, font):
        """Initialize the thermal camera."""
        super().__init__()
        self._name = name
        self._url = url
        self._session = session
        self._frame = None
        self._font = font

    @property
    def name(self):
        """Return the name of the camera."""
        return self._name

    def map_to_color(self, value, min_value, max_value):
        """Map the thermal value to a color with yellow in the mid-range."""
        normalized = (value - min_value) / (max_value - min_value)
        if normalized < 0.5:
            b = int(255 * (1 - 2 * normalized))
            g = int(255 * (2 * normalized))
            r = 0
        else:
            b = 0
            g = int(255 * (2 * (1 - normalized)))
            r = int(255 * (2 * (normalized - 0.5)))
        return (r, g, b)

    def fetch_data(self):
        """Fetch data from the URL and process the frame."""
        try:
            _LOGGER.debug("Fetching data from URL: %s", self._url)
            response = requests.get(f"{self._url}/json", timeout=5)
            response.raise_for_status()
            data = response.json()

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

            _LOGGER.debug(f"Image size: {img.size}, Scale factor: {scale_factor}")
            _LOGGER.debug(f"Text coordinates: ({text_x}, {text_y}), Text: {text}")

            # Ensure the font is loaded
            if not self._font:
                _LOGGER.error("Font is not loaded, using default.")
                self._font = ImageFont.load_default()

            # Draw the text with a shadow for visibility
            shadow_offset = 3
            for dx in range(-shadow_offset, shadow_offset + 1):
                for dy in range(-shadow_offset, shadow_offset + 1):
                    if dx != 0 or dy != 0:
                        draw.text((text_x + dx, text_y + dy), text, fill="black", font=self._font)

            # Draw the main text (white)
            draw.text((text_x, text_y), text, fill="white", font=self._font)

            text_x, text_y = 50, 50  # Force fixed position for debugging
            draw.text((text_x, text_y), text, fill="red", font=self._font)

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

    def camera_image(self, width=None, height=None):
        """Return the camera image synchronously."""
        self.fetch_data()
        return self._frame

    def stream_source(self):
        """Return the URL of the video stream."""
        return None

    @property
    def should_poll(self):
        """Camera polling is required."""
        return True
