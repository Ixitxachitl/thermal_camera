from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
import logging

from .constants import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up thermal camera integration using YAML."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up thermal camera from a config entry."""
    hass.data[DOMAIN][config_entry.entry_id] = config_entry.data

    # Set up the camera entity
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "camera")
    )

    # Set up the binary sensor entity
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "binary_sensor")
    )

    return True

async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(config_entry, "camera")
    unload_ok = unload_ok and await hass.config_entries.async_forward_entry_unload(config_entry, "binary_sensor")

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
