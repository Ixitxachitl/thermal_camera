# Constants used throughout the Thermal Camera integration

DOMAIN = "thermal_camera"

DEFAULT_NAME = "Thermal Camera"
DEFAULT_ROWS = 24
DEFAULT_COLS = 32
DEFAULT_PATH = "json"
DEFAULT_DATA_FIELD = "frame"
DEFAULT_LOWEST_FIELD = "lowest"
DEFAULT_HIGHEST_FIELD = "highest"
DEFAULT_AVERAGE_FIELD = "average"
DEFAULT_RESAMPLE_METHOD = "NEAREST"
DEFAULT_MOTION_THRESHOLD = 8
DEFAULT_MJPEG_PORT = 8169
DEFAULT_DESIRED_HEIGHT = 720

CONF_DIMENSIONS = "dimensions"
CONF_ROWS = "rows"
CONF_COLUMNS = "columns"
CONF_PATH = "path"
CONF_DATA_FIELD = "data_field"
CONF_LOWEST_FIELD = "lowest_field"
CONF_HIGHEST_FIELD = "highest_field"
CONF_AVERAGE_FIELD = "average_field"
CONF_RESAMPLE = "resample"
CONF_MOTION_THRESHOLD = "motion_threshold"
CONF_MJPEG_PORT = "mjpeg_port"
CONF_DESIRED_HEIGHT = "desired_height"

RESAMPLE_METHODS = {
    "NEAREST": "NEAREST",
    "BILINEAR": "BILINEAR",
    "BICUBIC": "BICUBIC",
    "LANCZOS": "LANCZOS",
}