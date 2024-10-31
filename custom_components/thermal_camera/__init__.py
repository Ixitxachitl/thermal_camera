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

    # Set up the coordinator with field mappings from the config entry
    coordinator = ThermalCameraDataCoordinator(
        hass,
        session=session,
        url=config_entry.data.get("url"),
        path=config_entry.data.get("path"),
        data_field=config_entry.data.get("data_field", "frame"),
        lowest_field=config_entry.data.get("lowest_field", "lowest"),
        highest_field=config_entry.data.get("highest_field", "highest"),
        average_field=config_entry.data.get("average_field", "average")
    )

    # Wait for initial data load
    await coordinator.async_config_entry_first_refresh()

    # Generate unique IDs for entities if not already in the config entry data
    updated_data = config_entry.data.copy()
    if "unique_id" not in updated_data:
        updated_data["unique_id"] = str(uuid.uuid4())
    if "unique_id_motion_sensor" not in updated_data:
        updated_data["unique_id_motion_sensor"] = str(uuid.uuid4())
    if "unique_id_highest_sensor" not in updated_data:
        updated_data["unique_id_highest_sensor"] = str(uuid.uuid4())
    if "unique_id_lowest_sensor" not in updated_data:
        updated_data["unique_id_lowest_sensor"] = str(uuid.uuid4())
    if "unique_id_average_sensor" not in updated_data:
        updated_data["unique_id_average_sensor"] = str(uuid.uuid4())

    # Update the config entry if unique IDs were added
    if updated_data != config_entry.data:
        hass.config_entries.async_update_entry(config_entry, data=updated_data)

    # Store coordinator and config
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "coordinator": coordinator,
        "config": updated_data,
    }

    # Forward setup for camera, binary sensor, and temperature sensors
    await hass.config_entries.async_forward_entry_setups(config_entry, ["camera", "binary_sensor", "sensor"])

    return True

async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload the config entry."""
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)

import asyncio

async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    platforms = ["camera", "binary_sensor", "sensor"]
    
    # Use asyncio.gather to await each unload operation
    unload_results = await asyncio.gather(
        *[hass.config_entries.async_forward_entry_unload(config_entry, platform) for platform in platforms]
    )

    # Ensure unload_ok is True only if all platforms are unloaded successfully
    unload_ok = all(unload_results)

    # Clean up integration data if all platforms are unloaded successfully
    if unload_ok and config_entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
