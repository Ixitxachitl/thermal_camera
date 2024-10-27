import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .constants import DOMAIN, DEFAULT_NAME, DEFAULT_ROWS, DEFAULT_COLS, DEFAULT_PATH, DEFAULT_DATA_FIELD, DEFAULT_LOW_FIELD, DEFAULT_HIGH_FIELD, DEFAULT_RESAMPLE_METHOD

# Configuration schema for the UI
CONFIG_SCHEMA = vol.Schema({
    vol.Required("url"): str,
    vol.Optional("name", default=DEFAULT_NAME): str,
    vol.Optional("rows", default=DEFAULT_ROWS): int,
    vol.Optional("columns", default=DEFAULT_COLS): int,
    vol.Optional("path", default=DEFAULT_PATH): str,
    vol.Optional("data_field", default=DEFAULT_DATA_FIELD): str,
    vol.Optional("low_field", default=DEFAULT_LOW_FIELD): str,
    vol.Optional("high_field", default=DEFAULT_HIGH_FIELD): str,
    vol.Optional("resample", default=DEFAULT_RESAMPLE_METHOD): vol.In(["NEAREST", "BILINEAR", "BICUBIC", "LANCZOS"]),
})

class ThermalCameraConfigFlow(config_entries.ConfigFlow):
    DOMAIN = DOMAIN
    """Handle a config flow for the Thermal Camera integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title=user_input["name"], data=user_input)

        return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)

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
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema({
            vol.Optional("rows", default=self.config_entry.data.get("rows", DEFAULT_ROWS)): int,
            vol.Optional("columns", default=self.config_entry.data.get("columns", DEFAULT_COLS)): int,
            vol.Optional("resample", default=self.config_entry.data.get("resample", DEFAULT_RESAMPLE_METHOD)): vol.In(["NEAREST", "BILINEAR", "BICUBIC", "LANCZOS"]),
        })

        return self.async_show_form(step_id="init", data_schema=options_schema)
