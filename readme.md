# <img src="https://raw.githubusercontent.com/Ixitxachitl/thermal_camera/refs/heads/main/icon.png" alt="icon" width="64px"> Thermal Camera Integration

<img src="https://raw.githubusercontent.com/Ixitxachitl/thermal_camera/refs/heads/main/screenshot.png" alt="screenshot" width="45%"> <img src="https://raw.githubusercontent.com/Ixitxachitl/thermal_camera/refs/heads/main/screenshot2.png" alt="screenshot2" width="45%">

A custom Home Assistant integration that visualizes thermal data from the M5Stack T-Lite device or any compatible device that provides the required JSON data format.

## Features
- Maps thermal data to a color gradient (black, blue, green, yellow, orange, red, white) based on temperature.
- Includes a motion detection binary sensor based on temperature changes.
- Lightweight implementation using PIL (Pillow), optimized for Raspberry Pi and other low-resource devices.
- Designed specifically for the M5Stack T-Lite but can be adapted to other devices.
- Configurable thermal image dimensions, URL path, and JSON field names.
- Supports configurable image resampling methods for resizing (NEAREST, BILINEAR, BICUBIC, LANCZOS).
- Provides an MJPEG stream for easy integration with Home Assistant camera cards.
- Configurable desired height for thermal image display.
- Configurable MJPEG stream port for flexible network integration.

## Installation

### HACS Installation
1. Add this repository as a custom repository in HACS.
2. Search for "Thermal Camera Integration" in HACS and install it.
3. Restart Home Assistant.

### Manual Installation
1. Copy the `thermal_camera` folder to your `custom_components` directory.
2. Restart Home Assistant.

## Configuration

This integration is now configurable through the Home Assistant UI.
1. Go to **Settings** > **Devices & Services** > **Integrations**.
2. Click **Add Integration** and search for "Thermal Camera".
3. Follow the prompts to configure your thermal camera and motion sensor.

### Configuration Options
- **`url`** (Required): The URL of the device providing the thermal data.
- **`name`** (Optional): The name of the camera or motion sensor. Defaults to "Thermal Camera" or "Thermal Motion Sensor".
- **`rows`** (Optional): The number of rows in the thermal frame. Defaults to 24.
- **`columns`** (Optional): The number of columns in the thermal frame. Defaults to 32.
- **`path`** (Optional): The URL path to access the JSON data. Defaults to `json`. Use this to specify a different endpoint if necessary.
- **`data_field`** (Optional): The JSON field name that contains the thermal frame data. Defaults to `frame`. Use this to match the JSON format of your device.
- **`lowest_field`** (Optional): The JSON field name that contains the lowest temperature value. Defaults to `lowest`. Use this to match the JSON format of your device.
- **`highest_field`** (Optional): The JSON field name that contains the highest temperature value. Defaults to `highest`. Use this to match the JSON format of your device.
- **`average_field`** (Optional): The JSON field name that contains the average temperature value. Defaults to `average`. Use this to match the JSON format of your device.
- **`resample`** (Optional): The resampling method used for resizing the thermal image. Options are `NEAREST`, `BILINEAR`, `BICUBIC`, and `LANCZOS`. Defaults to `NEAREST`. This allows you to control the quality and performance of the resizing operation.
- **`motion_threshold`** (Optional): The temperature difference threshold used to detect motion. Defaults to `8`. This determines how sensitive the sensor is to temperature changes.
- **`mjpeg_port`** (Optional): The port for the MJPEG stream. Defaults to `8169`. Use this to specify a different port if necessary.
- **`desired_height`** (Optional): The desired height of the thermal image. Defaults to `720`. This allows for customizing the output height of the thermal image.

## Expected URL and JSON Format

The integration expects to fetch thermal data from the URL provided in the configuration. The device should serve the data as JSON in the following format:

### Example JSON Format

```json
{
  "average": 78.7,
  "highest": 82.8,
  "lowest": 67.2,
  "frame": [
    80.2, 80.4, 83.4, 83.3, ..., 68.6, 67.8  // A 768-element array (32x24)
  ]
}
```

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

## MJPEG Stream

The thermal camera integration provides an MJPEG stream accessible at `http://<local-ip>:<mjpeg_port>/mjpeg`. This can be added as a camera entity in Home Assistant or viewed directly in a web browser on the same network. The IP address (`<local-ip>`) and port (`<mjpeg_port>`) will be automatically determined by the integration based on the configuration.

### Interfacing with the T-Lite Output Stream
For interfacing with the output stream of the M5Stack T-Lite in Home Assistant using the MJPEG integration, use the `/stream` endpoint from the device IP. Note that this integration does not use the `/stream` endpoint directly; instead, it uses JSON data to render its own image. 

If you would like to add the MJPEG source to go2rtc, an example configuration would look like this:

```
- ffmpeg:http://<device-ip>/stream#video=h264#hardware#width=1920#height=1080#raw=-sws_flags neighbor
```

You can modify the options as needed, but this worked for me. Note that integrating the MJPEG source into go2rtc is outside the scope of this project.

## Configuring Devices with ESP8266 AMG8833 Firmware
This integration is compatible with devices running firmware based on ESP8266 that serves thermal data in JSON format. To make devices running this firmware work with the integration, the following configuration options are required:

- **Endpoint URL**: Ensure that the `path` points to the `raw` endpoint of the device, which serves the thermal data in JSON format. The endpoint should provide data at `http://<device-ip>/raw`.
- **Data Field Configuration**:
  - **`data_field`**: Set to `data` to align with the firmware's JSON response.
  - **`lowest_field`**: Set to `min` to access the lowest temperature in the frame.
  - **`highest_field`**: Set to `max` for the highest temperature value.
  - **`average_field`**: Set to `avg` to obtain the average temperature across the grid.
- **Resolution Configuration**:
  - The firmware uses an 8x8 resolution, so set **`rows`** and **`columns`** to `8` accordingly.
- **Motion Detection**:
  - The firmware includes a `person_detected` field, but this data is not used by the integration for motion detection. Instead, motion detection is handled externally by the integration, which uses temperature differences to determine motion.

## Development

- Adjustments can be made in the integration's settings through the Home Assistant UI.
- You can modify the font, scaling, color mapping logic, or resampling method in the code if deeper customization is needed.
- For the motion detection sensor, you can customize the temperature difference threshold in the configuration to fine-tune sensitivity.

## Troubleshooting

If the camera feed shows a broken image, check:
- The URL is reachable and returns the expected JSON format.
- The device is correctly configured to provide frame data with the specified dimensions.
- Review the Home Assistant logs for error messages.

### Font License
This integration includes the DejaVu font. The license for the DejaVu font can be found in the `custom_components/thermal_camera/fonts/DejaVuSans-License.txt`.

For further assistance, feel free to open an issue on the GitHub repository.