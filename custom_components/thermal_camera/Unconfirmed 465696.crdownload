import logging
import requests
import voluptuous as vol
import cv2
import numpy as np
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

# Set up logging
_LOGGER = logging.getLogger(__name__)

# Configuration constants
CONF_URL = "url"
DEFAULT_NAME = "Thermal Camera"
ROWS, COLS = 24, 32

# Validation schema for platform configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_URL): cv.url,
})

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the thermal camera platform."""
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
        return (max(0, min(255, b)), max(0, min(255, g)), max(0, min(255, r)))

    def fetch_data(self):
        """Fetch data from the URL and process the frame."""
        try:
            response = requests.get(f"{self._url}/json", timeout=5)
            data = response.json()

            frame_data = np.array(data["frame"]).reshape(ROWS, COLS)
            min_value = data["lowest"]
            max_value = data["highest"]

            # Create an empty RGB image
            img = np.zeros((ROWS, COLS, 3), dtype=np.uint8)

            # Map frame data to colors
            for r in range(ROWS):
                for c in range(COLS):
                    img[r, c] = self.map_to_color(frame_data[r, c], min_value, max_value)

            # Scale up the image for better visibility
            img_scaled = cv2.resize(img, (640, 480), interpolation=cv2.INTER_NEAREST)

            # Encode the image to JPEG
            ret, jpeg_img = cv2.imencode('.jpg', img_scaled)
            if ret:
                self._frame = jpeg_img.tobytes()
        except Exception as e:
            _LOGGER.error(f"Error fetching or processing data: {e}")

    def camera_image(self):
        """Return the camera image."""
        self.fetch_data()
        return self._frame

    def stream_source(self):
        """Return the URL of the video stream."""
        return None

    @property
    def should_poll(self):
        """Camera polling is required."""
        return True
