# Thermal Camera

A custom Home Assistant integration for visualizing thermal camera data.

## Installation

### HACS Installation
1. Add this repository as a custom repository in HACS.
2. Search for "Thermal Camera" in HACS and install it.
3. Restart Home Assistant.

### Manual Installation
1. Copy the `thermal_camera` folder to your `custom_components` directory.
2. Restart Home Assistant.

## Configuration

Add the following to your `configuration.yaml`:
```yaml
camera:
  - platform: thermal_camera
    name: "Thermal Camera"
    url: "http://192.168.50.210"
