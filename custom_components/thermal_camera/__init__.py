import uuid
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from .constants import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the thermal camera integration using YAML."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the thermal camera integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {"config": config_entry.data}

    # Generate unique IDs for camera, motion sensor, and temperature sensors if not already present
    updated_data = config_entry.data.copy()
    if not updated_data.get("unique_id"):
        updated_data["unique_id"] = str(uuid.uuid4())
    if not updated_data.get("unique_id_motion_sensor"):
        updated_data["unique_id_motion_sensor"] = str(uuid.uuid4())
    hass.config_entries.async_update_entry(config_entry, data=updated_data)

    # Forward setups for camera, binary sensor, and temperature sensors
    await hass.config_entries.async_forward_entry_setups(config_entry, ["camera", "binary_sensor", "sensor"])

    return True

async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload the config entry."""
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)

async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload the camera, binary sensor, and temperature sensor entities
    unload_ok = all(
        await hass.config_entries.async_forward_entry_unload(config_entry, platform)
        for platform in ["camera", "binary_sensor", "sensor"]
    )

    # Clean up integration data if all platforms are unloaded successfully
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
