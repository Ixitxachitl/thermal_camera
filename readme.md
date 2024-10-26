# Thermal Camera Integration for M5Stack T-Lite

![alt text](screenshot.png)

A custom Home Assistant integration that visualizes thermal data from the M5Stack T-Lite device or any compatible device that provides the required JSON data format.

## Features
- Maps thermal data to a color gradient (black, blue, green, yellow, orange, red, white) based on temperature.
- Includes a motion detection binary sensor based on temperature changes.
- Lightweight implementation using PIL (Pillow), optimized for Raspberry Pi and other low-resource devices.
- Designed specifically for the M5Stack T-Lite but can be adapted to other devices.
- Configurable thermal image dimensions, URL path, and JSON field names.
- Supports configurable image resampling methods for resizing (NEAREST, BILINEAR, BICUBIC, LANCZOS).

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

````yaml
camera:
  - platform: thermal_camera
    name: "M5Stack T-Lite Thermal Camera"
    url: "http://<device-ip>"
    dimensions:
      rows: 24
      columns: 32
    path: json
    data_field: frame
    low_field: lowest
    high_field: highest
    resample: NEAREST
````

### Configuration Options
- **`name`** (Optional): The name of the camera. Defaults to "Thermal Camera".
- **`url`** (Required): The URL of the device providing the thermal data.
- **`dimensions`** (Optional): Defines the dimensions of the thermal data.
  - **`rows`** (Optional): The number of rows in the thermal frame. Defaults to 24.
  - **`columns`** (Optional): The number of columns in the thermal frame. Defaults to 32.
- **`path`** (Optional): The URL path to access the JSON data. Defaults to `json`. Use this to specify a different endpoint if necessary.
- **`data_field`** (Optional): The JSON field name that contains the thermal frame data. Defaults to `frame`. Use this to match the JSON format of your device.
- **`low_field`** (Optional): The JSON field name that contains the lowest temperature value. Defaults to `lowest`. Use this to match the JSON format of your device.
- **`high_field`** (Optional): The JSON field name that contains the highest temperature value. Defaults to `highest`. Use this to match the JSON format of your device.
- **`resample`** (Optional): The resampling method used for resizing the thermal image. Options are `NEAREST`, `BILINEAR`, `BICUBIC`, and `LANCZOS`. Defaults to `NEAREST`. This allows you to control the quality and performance of the resizing operation.

### Motion Detection Sensor Configuration
````yaml
binary_sensor:
  - platform: thermal_motion
    name: "M5Stack T-Lite Motion Sensor"
    url: "http://<device-ip>"
    path: json
    motion_threshold: 8
    average_field: average
    highest_field: highest
````
Replace `<device-ip>` with the actual IP address of your M5Stack T-Lite or compatible device.

### Motion Detection Configuration Options
- **`name`** (Optional): The name of the motion sensor. Defaults to "Thermal Motion Sensor".
- **`url`** (Required): The URL of the device providing the thermal data.
- **`path`** (Optional): The URL path to access the JSON data. Defaults to `json`. Use this to specify a different endpoint if necessary.
- **`motion_threshold`** (Optional): The temperature difference threshold used to detect motion. Defaults to `8`. This determines how sensitive the sensor is to temperature changes.
- **`average_field`** (Optional): The JSON field name that contains the average temperature value. Defaults to `average`. Use this to match the JSON format of your device.
- **`highest_field`** (Optional): The JSON field name that contains the highest temperature value. Defaults to `highest`. Use this to match the JSON format of your device.

## Expected URL and JSON Format

The integration expects to fetch thermal data from the URL provided in the configuration. The device should serve the data as JSON in the following format:

### Example JSON Format

````json
{
  "average": 78.7,
  "highest": 82.8,
  "lowest": 67.2,
  "frame": [
    80.2, 80.4, 83.4, 83.3, ..., 68.6, 67.8  // A 768-element array (32x24)
  ]
}
````

### JSON Fields Description

- The unit of temperature (`average`, `highest`, `lowest`, and values in `frame`) is not important to the functionality of this integration and can be provided in any consistent unit.
- **`average`**: The average temperature of all the pixels in the frame (float).
- **`highest`**: The highest temperature in the frame (float).
- **`lowest`**: The lowest temperature in the frame (float).
- **`frame`**: An array of floating-point values representing the thermal image frame, ordered row by row.

### Device Requirements
- The device should serve the data over HTTP.
- The endpoint must return the JSON response described above.
- The device should be accessible via a URL in the format `http://<device-ip>/<path>` (default path is `json`).

## Motion Detection

The motion detection sensor calculates the difference between the "highest" and "average" temperatures in the frame. If the difference exceeds a certain threshold (default: 8), it indicates motion. You can adjust this threshold in the configuration.

## Development

- Adjustments can be made in the camera.py code to change the font, scaling, color mapping logic, or resampling method.
- For the motion detection sensor, you can customize the temperature difference threshold in the configuration to fine-tune sensitivity.

## Troubleshooting

If the camera feed shows a broken image, check:
- The URL is reachable and returns the expected JSON format.
- The device is correctly configured to provide frame data with the specified dimensions.
- Review the Home Assistant logs for error messages.

### Font License
This integration includes the DejaVu font. The license for the DejaVu font can be found in the `custom_components/thermal_camera/fonts/DejaVuSans-License.txt`.

For further assistance, feel free to open an issue on the GitHub repository.
