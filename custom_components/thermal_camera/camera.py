import asyncio
import logging
import os
import aiohttp
import async_timeout
from io import BytesIO
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import requests  # Import for loading DejaVu font
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_URL
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Thermal Camera"
ROWS, COLS = 24, 32
FONT_PATH = os.path.join(os.path.dirname(__file__), 'DejaVuSans-Bold.ttf')

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
        try:
            self._font = ImageFont.truetype(FONT_PATH, 40)  # Load DejaVu font
        except IOError:
            _LOGGER.error("Failed to load DejaVu font, using default font.")
            self._font = ImageFont.load_default()

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
            _LOGGER.debug("Initial image created. Image mode: %s, Image size: %s", img.mode, img.size)
            draw = ImageDraw.Draw(img)

            # Map frame data to colors
            for r in range(ROWS):
                for c in range(COLS):
                    color = self.map_to_color(frame_data[r, c], min_value, max_value)
                    draw.point((c, r), fill=color)

            # Scale up the image
            scale_factor = 20
            img = img.resize((COLS * scale_factor, ROWS * scale_factor), resample=Image.NEAREST)
            _LOGGER.debug("Image resized. New size: %s", img.size)

            # Reinitialize ImageDraw after resizing
            draw = ImageDraw.Draw(img)

            # Draw a reticle on the pixel with the highest temperature
            max_index = np.argmax(frame_data)
            max_row, max_col = divmod(max_index, COLS)

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
            if max_row >= ROWS - 3:
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

    def stream_source(self):
        """Return the URL of the video stream."""
        return None

    @property
    def should_poll(self):
        """Camera polling is required."""
        return True

    async def async_will_remove_from_hass(self):
        """Called when the entity is about to be removed from Home Assistant."""
        if self._session is not None:
            await self._session.close()
