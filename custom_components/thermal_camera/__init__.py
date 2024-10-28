import uuid
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
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = config_entry.data

    # Generate unique IDs for camera and binary sensor if not already present
    unique_id_camera = config_entry.data.get("unique_id")
    unique_id_motion_sensor = config_entry.data.get("unique_id_motion_sensor")
    if unique_id_camera is None or unique_id_motion_sensor is None:
        updated_data = config_entry.data.copy()
        if unique_id_camera is None:
            updated_data["unique_id"] = str(uuid.uuid4())
        if unique_id_motion_sensor is None:
            updated_data["unique_id_motion_sensor"] = str(uuid.uuid4())
        hass.config_entries.async_update_entry(config_entry, data=updated_data)

    # Set up the camera and binary sensor entities
    await hass.config_entries.async_forward_entry_setups(config_entry, ["camera"])
    await hass.config_entries.async_forward_entry_setups(config_entry, ["binary_sensor"])

    return True

async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload the config entry."""
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)

async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload the camera and binary sensor entities
    unload_camera = await hass.config_entries.async_forward_entry_unload(config_entry, "camera")
    unload_binary_sensor = await hass.config_entries.async_forward_entry_unload(config_entry, "binary_sensor")
    unload_ok = unload_camera and unload_binary_sensor

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok