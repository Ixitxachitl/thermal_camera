import voluptuous as vol
import uuid
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .constants import DOMAIN, DEFAULT_NAME, DEFAULT_ROWS, DEFAULT_COLS, DEFAULT_PATH, DEFAULT_DATA_FIELD, DEFAULT_LOW_FIELD, DEFAULT_HIGHEST_FIELD, DEFAULT_RESAMPLE_METHOD, DEFAULT_MOTION_THRESHOLD, DEFAULT_AVERAGE_FIELD

# Configuration schema for the UI
CONFIG_SCHEMA = vol.Schema({
    # Required URL of the device providing the thermal data.
    # URL of the device providing the thermal data.
    vol.Required("url", description="The URL of the device providing the thermal data."): str,  # Required URL of the device providing the thermal data.
    vol.Optional("name", default=DEFAULT_NAME, description="The name of the thermal camera."): str,  # Optional name of the thermal camera.
    vol.Optional("rows", default=DEFAULT_ROWS, description="Number of rows in the thermal frame."): int,  # Number of rows in the thermal frame.
    vol.Optional("columns", default=DEFAULT_COLS, description="Number of columns in the thermal frame."): int,  # Number of columns in the thermal frame.
    vol.Optional("path", default=DEFAULT_PATH, description="URL path to access the JSON data."): str,  # URL path to access the JSON data.
    vol.Optional("data_field", default=DEFAULT_DATA_FIELD, description="JSON field name containing the thermal frame data."): str,  # JSON field name containing the thermal frame data.
    vol.Optional("low_field", default=DEFAULT_LOW_FIELD, description="JSON field name containing the lowest temperature value."): str,  # JSON field name containing the lowest temperature value.
    vol.Optional("highest_field", default=DEFAULT_HIGHEST_FIELD, description="JSON field name containing the highest temperature value."): str,  # JSON field name containing the highest temperature value.
    vol.Optional("average_field", default=DEFAULT_AVERAGE_FIELD, description="JSON field name containing the average temperature value."): str,  # JSON field name containing the average temperature value.
    vol.Optional("resample", default=DEFAULT_RESAMPLE_METHOD, description="Resampling method for resizing the thermal image."): vol.In(["NEAREST", "BILINEAR", "BICUBIC", "LANCZOS"]),  # Resampling method for resizing the thermal image.
    vol.Optional("motion_threshold", default=DEFAULT_MOTION_THRESHOLD, description="Temperature difference threshold for motion detection."): int,  # Temperature difference threshold for motion detection.
})

class ThermalCameraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    """Handle a config flow for the Thermal Camera integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                # Validate the URL and create entry if successful
                session = async_get_clientsession(self.hass)
                async with session.get(user_input["url"]) as response:
                    response.raise_for_status()
                # Generate and store unique IDs for camera and binary sensor
                if "unique_id" not in user_input:
                    user_input["unique_id"] = str(uuid.uuid4())
                if "unique_id_motion_sensor" not in user_input:
                    user_input["unique_id_motion_sensor"] = str(uuid.uuid4())
                return self.async_create_entry(title=user_input["name"], data=user_input)
            except Exception:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
            description_placeholders={
                "url": "The URL of the device providing the thermal data.",
                "name": "The name of the thermal camera.",
                "rows": "Number of rows in the thermal frame.",
                "columns": "Number of columns in the thermal frame.",
                "path": "URL path to access the JSON data.",
                "data_field": "JSON field name containing the thermal frame data.",
                "low_field": "JSON field name containing the lowest temperature value.",
                "highest_field": "JSON field name containing the highest temperature value.",
                "average_field": "JSON field name containing the average temperature value.",
                "resample": "Resampling method for resizing the thermal image.",
                "motion_threshold": "Temperature difference threshold for motion detection."
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ThermalCameraOptionsFlowHandler(config_entry)

class ThermalCameraOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for the Thermal Camera integration."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options for the thermal camera."""
        if user_input is not None:
            # Update the config entry with new user input values
            self.hass.config_entries.async_update_entry(self.config_entry, data={**self.config_entry.data, **user_input})
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema({
            vol.Optional("url", default=self.config_entry.data.get("url")): str,
            vol.Optional("name", default=self.config_entry.data.get("name", DEFAULT_NAME)): str,
            vol.Optional("rows", default=self.config_entry.data.get("rows", DEFAULT_ROWS)): int,
            vol.Optional("columns", default=self.config_entry.data.get("columns", DEFAULT_COLS)): int,
            vol.Optional("path", default=self.config_entry.data.get("path", DEFAULT_PATH)): str,
            vol.Optional("data_field", default=self.config_entry.data.get("data_field", DEFAULT_DATA_FIELD)): str,
            vol.Optional("low_field", default=self.config_entry.data.get("low_field", DEFAULT_LOW_FIELD)): str,
            vol.Optional("highest_field", default=self.config_entry.data.get("highest_field", DEFAULT_HIGHEST_FIELD)): str,
            vol.Optional("average_field", default=self.config_entry.data.get("average_field", DEFAULT_AVERAGE_FIELD)): str,
            vol.Optional("resample", default=self.config_entry.data.get("resample", DEFAULT_RESAMPLE_METHOD)): vol.In(["NEAREST", "BILINEAR", "BICUBIC", "LANCZOS"]),
            vol.Optional("motion_threshold", default=self.config_entry.data.get("motion_threshold", DEFAULT_MOTION_THRESHOLD)): int,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            description_placeholders={
                "url": "The URL of the device providing the thermal data.",
                "name": "The name of the thermal camera.",
                "rows": "Number of rows in the thermal frame.",
                "columns": "Number of columns in the thermal frame.",
                "path": "URL path to access the JSON data.",
                "data_field": "JSON field name containing the thermal frame data.",
                "low_field": "JSON field name containing the lowest temperature value.",
                "highest_field": "JSON field name containing the highest temperature value.",
                "average_field": "JSON field name containing the average temperature value.",
                "resample": "Resampling method for resizing the thermal image.",
                "motion_threshold": "Temperature difference threshold for motion detection."
            }
        )
