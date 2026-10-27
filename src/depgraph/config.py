from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

import yaml

from depgraph.constants import (
    HTTP_SCHEMES,
    IMAGE_NAME_PATTERN,
    KEY_FILTER_SUBSTRING,
    KEY_GRAPH_IMAGE_NAME,
    KEY_PACKAGE_NAME,
    KEY_REPOSITORY,
    KEY_TEST_REPOSITORY_MODE,
    MAX_FILENAME_LENGTH,
    MAX_PACKAGE_NAME_LENGTH,
    PACKAGE_NAME_PATTERN,
    PNG_EXTENSION,
    REQUIRED_KEYS,
)


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class AppConfig:
    package_name: str
    repository: str
    test_repository_mode: bool
    graph_image_name: str
    filter_substring: str

    def as_pairs(self) -> tuple[tuple[str, str], ...]:
        if self.test_repository_mode:
            mode = "true"
        else:
            mode = "false"
        return (
            (KEY_PACKAGE_NAME, self.package_name),
            (KEY_REPOSITORY, self.repository),
            (KEY_TEST_REPOSITORY_MODE, mode),
            (KEY_GRAPH_IMAGE_NAME, self.graph_image_name),
            (KEY_FILTER_SUBSTRING, self.filter_substring),
        )


def load_config(path: str) -> AppConfig:
    raw = _read_yaml(path)
    if not isinstance(raw, dict):
        raise ConfigError(
            "корневой документ YAML должен быть набором параметров",
        )
    unknown = sorted(set(raw) - set(REQUIRED_KEYS))
    if unknown:
        names = ", ".join(str(key) for key in unknown)
        raise ConfigError(f"неизвестные параметры: {names}")

    package_name = _package_name(_value(raw, KEY_PACKAGE_NAME))
    test_mode = _test_mode(_value(raw, KEY_TEST_REPOSITORY_MODE))
    config_dir = os.path.dirname(os.path.abspath(path))
    repository = _repository(
        _value(raw, KEY_REPOSITORY),
        test_mode,
        config_dir,
    )
    image_name = _image_name(_value(raw, KEY_GRAPH_IMAGE_NAME))
    substring = _filter_text(_value(raw, KEY_FILTER_SUBSTRING))
    return AppConfig(
        package_name=package_name,
        repository=repository,
        test_repository_mode=test_mode,
        graph_image_name=image_name,
        filter_substring=substring,
    )


def _read_yaml(path: str) -> object:
    if not os.path.exists(path):
        raise ConfigError(f"файл конфигурации не найден: {path}")
    if not os.path.isfile(path):
        raise ConfigError(f"ожидался файл конфигурации: {path}")
    try:
        with open(path, encoding="utf-8") as config_file:
            return yaml.safe_load(config_file)
    except UnicodeDecodeError as error:
        raise ConfigError(
            "файл конфигурации должен быть в кодировке UTF-8",
        ) from error
    except OSError as error:
        raise ConfigError(
            "не удалось прочитать файл конфигурации: "
            f"{error.strerror}",
        ) from error
    except yaml.YAMLError as error:
        raise ConfigError(f"некорректный YAML: {error}") from error


def _value(options: dict[str, object], key: str) -> object:
    if key not in options:
        raise ConfigError(f"{key}: параметр отсутствует")
    return options[key]


def _text(key: str, value: object) -> str:
    if value is None:
        raise ConfigError(f"{key}: значение не задано")
    if type(value) is not str:
        raise ConfigError(f"{key}: ожидался тип «строка»")
    return value


def _test_mode(value: object) -> bool:
    key = KEY_TEST_REPOSITORY_MODE
    if value is None:
        raise ConfigError(f"{key}: значение не задано")
    if type(value) is not bool:
        raise ConfigError(f"{key}: ожидался тип «логический»")
    return value


def _package_name(value: object) -> str:
    name = _text(KEY_PACKAGE_NAME, value).strip()
    if name == "":
        raise ConfigError(
            f"{KEY_PACKAGE_NAME}: значение не может быть пустым",
        )
    if len(name) > MAX_PACKAGE_NAME_LENGTH:
        raise ConfigError(
            f"{KEY_PACKAGE_NAME}: длина больше "
            f"{MAX_PACKAGE_NAME_LENGTH} символов",
        )
    if PACKAGE_NAME_PATTERN.fullmatch(name) is None:
        raise ConfigError(
            f"{KEY_PACKAGE_NAME}: допустимы латиница, цифры, "
            "«-» и «_»; первый символ — буква или цифра",
        )
    return name


def _repository(value: object, test_mode: bool, config_dir: str) -> str:
    location = _text(KEY_REPOSITORY, value).strip()
    if location == "":
        raise ConfigError(
            f"{KEY_REPOSITORY}: значение не может быть пустым",
        )
    if test_mode:
        return _test_file(location, config_dir)
    return _remote_url(location)


def _test_file(location: str, config_dir: str) -> str:
    lowered = location.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        raise ConfigError(
            f"{KEY_REPOSITORY}: в тестовом режиме нужен путь "
            "к файлу, а не URL",
        )
    path = location
    if not os.path.isabs(path):
        path = os.path.join(config_dir, path)
    if not os.path.isfile(path):
        raise ConfigError(
            f"{KEY_REPOSITORY}: тестовый файл не найден: {location}",
        )
    return os.path.abspath(path)


def _remote_url(location: str) -> str:
    if any(char.isspace() for char in location):
        raise ConfigError(
            f"{KEY_REPOSITORY}: URL не должен содержать пробелы",
        )
    parsed = urlparse(location)
    if parsed.scheme not in HTTP_SCHEMES or parsed.netloc == "":
        raise ConfigError(
            f"{KEY_REPOSITORY}: нужен абсолютный URL "
            "со схемой http или https",
        )
    return location


def _image_name(value: object) -> str:
    name = _text(KEY_GRAPH_IMAGE_NAME, value).strip()
    if name == "":
        raise ConfigError(
            f"{KEY_GRAPH_IMAGE_NAME}: значение не может быть пустым",
        )
    if len(name) > MAX_FILENAME_LENGTH:
        raise ConfigError(
            f"{KEY_GRAPH_IMAGE_NAME}: длина больше "
            f"{MAX_FILENAME_LENGTH} символов",
        )
    if name != os.path.basename(name):
        raise ConfigError(
            f"{KEY_GRAPH_IMAGE_NAME}: укажите имя файла без каталога",
        )
    if not name.lower().endswith(PNG_EXTENSION):
        raise ConfigError(
            f"{KEY_GRAPH_IMAGE_NAME}: расширение должно быть .png",
        )
    if IMAGE_NAME_PATTERN.fullmatch(name) is None:
        raise ConfigError(
            f"{KEY_GRAPH_IMAGE_NAME}: в имени допустимы латиница, "
            "цифры, «.», «-» и «_»",
        )
    return name


def _filter_text(value: object) -> str:
    text = _text(KEY_FILTER_SUBSTRING, value)
    if "\n" in text or "\r" in text:
        raise ConfigError(
            f"{KEY_FILTER_SUBSTRING}: значение должно быть "
            "одной строкой без перевода строки",
        )
    return text
