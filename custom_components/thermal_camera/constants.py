# Constants used throughout the Thermal Camera integration

DOMAIN = "thermal_camera"

DEFAULT_NAME = "Thermal Camera"
DEFAULT_ROWS = 24
DEFAULT_COLS = 32
DEFAULT_PATH = "json"
DEFAULT_DATA_FIELD = "frame"
DEFAULT_LOW_FIELD = "lowest"
DEFAULT_HIGH_FIELD = "highest"
DEFAULT_RESAMPLE_METHOD = "NEAREST"
DEFAULT_MOTION_THRESHOLD = 8

CONF_DIMENSIONS = "dimensions"
CONF_ROWS = "rows"
CONF_COLUMNS = "columns"
CONF_PATH = "path"
CONF_DATA_FIELD = "data_field"
CONF_LOW_FIELD = "low_field"
CONF_HIGH_FIELD = "high_field"
CONF_RESAMPLE = "resample"

RESAMPLE_METHODS = {
    "NEAREST": "NEAREST",
    "BILINEAR": "BILINEAR",
    "BICUBIC": "BICUBIC",
    "LANCZOS": "LANCZOS",
}
