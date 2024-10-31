import uuid
import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from .constants import DOMAIN
from .coordinator import ThermalCameraDataCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the thermal camera integration using YAML."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the thermal camera integration from a config entry."""
    # Initialize the session and coordinator
    session = hass.data.get("thermal_camera_session")
    if session is None or session.closed:
        session = aiohttp.ClientSession()
        hass.data["thermal_camera_session"] = session

    coordinator = ThermalCameraDataCoordinator(
        hass,
        session=session,
        url=config_entry.data.get("url"),
        path=config_entry.data.get("path"),
    )

    # Wait for initial data load
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator and config
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "coordinator": coordinator,
        "config": config_entry.data,
    }

    # Set up platforms
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
