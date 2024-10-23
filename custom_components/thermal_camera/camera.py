import logging
import requests
import numpy as np
from PIL import Image, ImageDraw
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

CONF_URL = "url"
DEFAULT_NAME = "Thermal Camera"
ROWS, COLS = 24, 32

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_URL): cv.url,
})

def setup_platform(hass, config, add_entities, discovery_info=None):
    name = config.get(CONF_NAME)
    url = config.get(CONF_URL)
    add_entities([ThermalCamera(name, url)], True)

class ThermalCamera(Camera):
    """Representation of a thermal camera."""

    def __init__(self, name, url):
        """Initialize the thermal camera."""
        super().__init__()
        self._name = name
        self._url = url
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

            # Find the index of the highest value
            max_index = np.argmax(frame_data)
            max_row, max_col = divmod(max_index, COLS)

            # Create an RGB image using PIL
            img = Image.new("RGB", (COLS, ROWS))
            draw = ImageDraw.Draw(img)

            # Map frame data to colors
            for r in range(ROWS):
                for c in range(COLS):
                    color = self.map_to_color(frame_data[r, c], min_value, max_value)
                    draw.point((c, r), fill=color)

            # Scale up the image
            scale_factor = 20  # Adjust scale factor for better visibility
            img = img.resize((COLS * scale_factor, ROWS * scale_factor), resample=Image.NEAREST)

            # Add the highest value text after scaling
            draw = ImageDraw.Draw(img)
            text = f"{frame_data[max_row, max_col]:.1f}"
            text_x, text_y = max_col * scale_factor, max_row * scale_factor

            # Optional: Load a custom font (if available)
            try:
                font = ImageFont.truetype("arial.ttf", 20)  # Replace with your font path
            except IOError:
                font = ImageFont.load_default()

            draw.text((text_x, text_y), text, fill="white", font=font)

            # Convert to JPEG bytes
            self._frame = self.image_to_jpeg_bytes(img)
            _LOGGER.debug("Image converted to JPEG bytes successfully.")
        except Exception as e:
            _LOGGER.error("Error fetching or processing data: %s", e)

    def image_to_jpeg_bytes(self, img):
        """Convert PIL image to JPEG bytes."""
        from io import BytesIO
        with BytesIO() as output:
            img.save(output, format="JPEG")
            return output.getvalue()

    def camera_image(self, width=None, height=None):
        """Return the camera image, optionally resized."""
        self.fetch_data()
        return self._frame

    def stream_source(self):
        """Return the URL of the video stream."""
        return None

    @property
    def should_poll(self):
        """Camera polling is required."""
        return True
