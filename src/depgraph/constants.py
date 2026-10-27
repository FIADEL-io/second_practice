import re

KEY_PACKAGE_NAME = "package_name"
KEY_REPOSITORY = "repository"
KEY_TEST_REPOSITORY_MODE = "test_repository_mode"
KEY_GRAPH_IMAGE_NAME = "graph_image_name"
KEY_FILTER_SUBSTRING = "filter_substring"

REQUIRED_KEYS = (
    KEY_PACKAGE_NAME,
    KEY_REPOSITORY,
    KEY_TEST_REPOSITORY_MODE,
    KEY_GRAPH_IMAGE_NAME,
    KEY_FILTER_SUBSTRING,
)

MAX_PACKAGE_NAME_LENGTH = 64
MAX_FILENAME_LENGTH = 255
PNG_EXTENSION = ".png"
HTTP_SCHEMES = ("http", "https")

PACKAGE_NAME_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
)
IMAGE_NAME_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*\.png$",
    re.IGNORECASE,
)

EXIT_OK = 0
EXIT_CONFIG = 1
