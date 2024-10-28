import asyncio
import logging
import os
import uuid
import aiohttp
import async_timeout
import socket
from io import BytesIO
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from .constants import DOMAIN, DEFAULT_NAME, DEFAULT_ROWS, DEFAULT_COLS, DEFAULT_PATH, DEFAULT_DATA_FIELD, DEFAULT_LOWEST_FIELD, DEFAULT_HIGHEST_FIELD, DEFAULT_AVERAGE_FIELD, DEFAULT_RESAMPLE_METHOD, DEFAULT_MJPEG_PORT, DEFAULT_DESIRED_HEIGHT, CONF_ROWS, CONF_COLUMNS, CONF_PATH, CONF_DATA_FIELD, CONF_LOWEST_FIELD, CONF_HIGHEST_FIELD, CONF_AVERAGE_FIELD, CONF_RESAMPLE, CONF_MJPEG_PORT, CONF_DESIRED_HEIGHT, RESAMPLE_METHODS
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.network import get_url
from aiohttp import web
import threading

_LOGGER = logging.getLogger(__name__)

FONT_PATH = os.path.join(os.path.dirname(__file__), 'DejaVuSans-Bold.ttf')

RESAMPLE_METHODS = {
    "NEAREST": Image.NEAREST,
    "BILINEAR": Image.BILINEAR,
    "BICUBIC": Image.BICUBIC,
    "LANCZOS": Image.LANCZOS,
}

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the thermal camera platform from a config entry."""
    config = config_entry.data
    name = config.get("name", DEFAULT_NAME)
    url = config.get("url")
    rows = config.get("rows", DEFAULT_ROWS)
    cols = config.get("columns", DEFAULT_COLS)
    path = config.get("path", DEFAULT_PATH)
    data_field = config.get("data_field", DEFAULT_DATA_FIELD)
    lowest_field = config.get("lowest_field", DEFAULT_LOWEST_FIELD)
    highest_field = config.get("highest_field", DEFAULT_HIGHEST_FIELD)
    average_field = config.get("average_field", DEFAULT_AVERAGE_FIELD)
    resample_method = RESAMPLE_METHODS[config.get("resample", DEFAULT_RESAMPLE_METHOD)]
    mjpeg_port = config.get("mjpeg_port", DEFAULT_MJPEG_PORT)
    desired_height = config.get("desired_height", DEFAULT_DESIRED_HEIGHT)

    # Reuse or create a persistent session for this platform
    session = hass.data.get("thermal_camera_session")
    if session and session.closed:
        session = None
    if session is None:
        session = aiohttp.ClientSession()
        hass.data["thermal_camera_session"] = session

    # Generate a unique ID if it does not already exist
    unique_id = config_entry.data.get("unique_id")
    if unique_id is None:
        unique_id = str(uuid.uuid4())
        hass.config_entries.async_update_entry(config_entry, data={**config_entry.data, "unique_id": unique_id})

    async_add_entities([ThermalCamera(name, url, rows, cols, path, data_field, lowest_field, highest_field, average_field, resample_method, session, mjpeg_port, desired_height, config_entry=config_entry, unique_id=unique_id)], True)

class ThermalCamera(Camera):
    """Representation of a thermal camera."""
    def __init__(self, name, url, rows, cols, path, data_field, lowest_field, highest_field, average_field, resample_method, session, mjpeg_port, desired_height, config_entry=None, unique_id=None):
        super().__init__()
        self._config_entry = config_entry
        self._name = name
        self._url = url
        self._rows = rows
        self._cols = cols
        self._path = path
        self._data_field = data_field
        self._lowest_field = lowest_field
        self._highest_field = highest_field
        self._average_field = average_field
        self._resample_method = resample_method
        self._session = session
        self._unique_id = unique_id
        self._frame = None
        self._mjpeg_port = mjpeg_port
        self._desired_height = desired_height
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
        async def run_server():
            await self._runner.setup()
            site = web.TCPSite(self._runner, '0.0.0.0', self._mjpeg_port)
            await site.start()

        asyncio.run_coroutine_threadsafe(run_server(), self._loop)

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

    def map_to_color(self, value, min_value, max_value):
        """Map thermal value to a color gradient."""
        normalized = max(0.0, min(1.0, (value - min_value) / (max_value - min_value)))
        if normalized < 0.25:  # Black to Blue
            return (0, 0, int(255 * (normalized / 0.25)))
        elif normalized < 0.5:  # Blue to Green (improved blend)
            blue = int(255 * (1 - (normalized - 0.25) / 0.25))
            green = int(255 * ((normalized - 0.25) / 0.25))
            return (0, green, blue)
        elif normalized < 0.75:  # Green to Yellow
            return (int(255 * ((normalized - 0.5) / 0.25)), 255, 0)
        elif normalized < 0.9:  # Yellow to Red
            return (255, int(255 * (1 - (normalized - 0.75) / 0.15)), 0)
        else:  # Red to White
            return (255, int(255 * ((normalized - 0.9) / 0.1)), int(255 * ((normalized - 0.9) / 0.1)))

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
            min_value = data[self._lowest_field]
            max_value = data[self._highest_field]
            avg_value = data[self._average_field]

            _LOGGER.debug("Frame data fetched successfully. Min: %s, Max: %s, Avg: %s", min_value, max_value, avg_value)

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

            # Draw the scale bar with shadow
            bar_width = 10  # Make the bar half as wide
            bar_height = img.height - 20
            bar_x = img.width - bar_width - 10
            bar_y = 10
            self.draw_scale_bar_with_shadow(img, bar_x, bar_y, bar_width, bar_height, min_value, max_value, avg_value, self._font)

            # Scale the image to the desired height while maintaining the aspect ratio if needed
            if img.height != self._desired_height:
                aspect_ratio = img.width / img.height
                new_width = int(self._desired_height * aspect_ratio)

                img = img.resize((new_width, self._desired_height), resample=self._resample_method)

                _LOGGER.debug("Image resized to desired height. New size: %s", img.size)

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

    def draw_scale_bar_with_shadow(self, img, bar_x, bar_y, bar_width, bar_height, min_value, max_value, avg_value, font):
        """Draw the scale bar with a shadow and gradient."""
        shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))  # Create a fully transparent RGBA layer
        shadow_draw = ImageDraw.Draw(shadow_layer)

        shadow_offset = 5  # Offset for the shadow
        shadow_color = (0, 0, 0, 100)  # Semi-transparent black

        # Draw the shadow for the scale bar
        shadow_draw.rectangle([bar_x + shadow_offset, bar_y + shadow_offset, bar_x + bar_width + shadow_offset, bar_y + bar_height + shadow_offset], fill=shadow_color)

        # Add the shadow layer to the main image
        img_rgba = img.convert("RGBA")
        combined = Image.alpha_composite(img_rgba, shadow_layer)

        # Convert back to RGB (to remove the alpha channel)
        img_rgb = combined.convert("RGB")
        img.paste(img_rgb)

        draw = ImageDraw.Draw(img)

        # Draw gradient on scale bar (from bottom to top, black to white)
        for i in range(bar_height):
            color_value = min_value + (max_value - min_value) * ((bar_height - i - 1) / bar_height)
            color = self.map_to_color(color_value, min_value, max_value)
            draw.line([(bar_x, bar_y + i), (bar_x + bar_width, bar_y + i)], fill=color)

        # Draw min, max, and average values to the left of the scale bar
        label_x = bar_x - 95
        self.draw_text_with_shadow(img, label_x, bar_y, f"{max_value:.1f}°", font)
        self.draw_text_with_shadow(img, label_x, bar_y + bar_height - 40, f"{min_value:.1f}°", font)
        self.draw_text_with_shadow(img, label_x, (bar_y + bar_height) // 2, f"{avg_value:.1f}°", font)

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

    async def async_stream_source(self):
        """Return the URL of the video stream."""
        if self.hass and self.entity_id:
            # Generate an access token to be used for streaming
            access_token = self.access_tokens[-1] if self.access_tokens else None
            if access_token:
                return f"{get_url(self.hass)}/api/camera_proxy_stream/{self.entity_id}?token={access_token}"
        
        # Fallback URL if Home Assistant is not available
        local_ip = self.get_local_ip()
        return f'http://{local_ip}:{self._mjpeg_port}/mjpeg'
      
    @property
    def should_poll(self):
        """Camera polling is required."""
        return True

    async def async_will_remove_from_hass(self):
        """Called when the entity is about to be removed from Home Assistant."""
        # Do not close the shared session here, it's managed by the integration
        pass
