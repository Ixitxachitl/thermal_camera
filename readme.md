# Thermal Camera Integration for M5Stack T-Lite

A custom Home Assistant integration that visualizes thermal data from the M5Stack T-Lite device.

## Features
- Maps thermal data to a color gradient (blue, yellow, red) based on temperature.
- Lightweight implementation using PIL (Pillow), optimized for Raspberry Pi and other low-resource devices.
- Designed specifically for the M5Stack T-Lite.

## Installation

### HACS Installation
1. Add this repository as a custom repository in HACS.
2. Search for "Thermal Camera for M5Stack T-Lite" in HACS and install it.
3. Restart Home Assistant.

### Manual Installation
1. Copy the `thermal_camera` folder to your `custom_components` directory.
2. Restart Home Assistant.

## Configuration

Add the following to your `configuration.yaml`:

```yaml
camera:
  - platform: thermal_camera
    name: "M5Stack T-Lite Thermal Camera"
    url: "http://<device-ip>"
