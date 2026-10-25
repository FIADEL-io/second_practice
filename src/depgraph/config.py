"""Загрузка и проверка YAML-конфигурации этапа 1."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import cast
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
    TYPE_NAMES,
)


class ConfigError(Exception):
    """Конфигурация отсутствует, повреждена или нарушает ограничение."""


@dataclass(frozen=True)
class AppConfig:
    """Параметры визуализатора, которые задаёт пользователь."""

    package_name: str
    repository: str
    test_repository_mode: bool
    graph_image_name: str
    filter_substring: str

    def as_pairs(self) -> tuple[tuple[str, str], ...]:
        """Вернуть параметры в порядке задания, парами ключ-значение."""
        mode = "true" if self.test_repository_mode else "false"
        return (
            (KEY_PACKAGE_NAME, self.package_name),
            (KEY_REPOSITORY, self.repository),
            (KEY_TEST_REPOSITORY_MODE, mode),
            (KEY_GRAPH_IMAGE_NAME, self.graph_image_name),
            (KEY_FILTER_SUBSTRING, self.filter_substring),
        )


def load_config(path: str) -> AppConfig:
    """Прочитать YAML-файл и вернуть проверенную конфигурацию."""
    document = _read_document(path)
    mapping = _require_mapping(document)
    _reject_unknown_keys(mapping)
    package_name = _validate_package_name(
        _take(mapping, KEY_PACKAGE_NAME),
    )
    test_mode = _validate_test_mode(
        _take(mapping, KEY_TEST_REPOSITORY_MODE),
    )
    repository = _validate_repository(
        _take(mapping, KEY_REPOSITORY),
        test_mode,
        os.path.dirname(os.path.abspath(path)),
    )
    image_name = _validate_image_name(
        _take(mapping, KEY_GRAPH_IMAGE_NAME),
    )
    substring = _validate_filter(
        _take(mapping, KEY_FILTER_SUBSTRING),
    )
    return AppConfig(
        package_name=package_name,
        repository=repository,
        test_repository_mode=test_mode,
        graph_image_name=image_name,
        filter_substring=substring,
    )


def _read_document(path: str) -> object:
    """Прочитать один YAML-документ из файла."""
    _require_config_file(path)
    try:
        with open(path, encoding="utf-8") as handle:
            return yaml.safe_load(handle)
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
        raise ConfigError(
            f"некорректный YAML: {error}",
        ) from error


def _require_config_file(path: str) -> None:
    """Убедиться, что путь указывает на существующий файл."""
    if not os.path.exists(path):
        raise ConfigError(f"файл конфигурации не найден: {path}")
    if not os.path.isfile(path):
        raise ConfigError(f"ожидался файл конфигурации: {path}")


def _require_mapping(document: object) -> dict[str, object]:
    """Вернуть корневой словарь параметров."""
    if not isinstance(document, dict):
        raise ConfigError(
            "корневой документ YAML должен быть набором параметров",
        )
    return cast(dict[str, object], document)


def _reject_unknown_keys(mapping: dict[str, object]) -> None:
    """Запретить параметры, которых нет в задании."""
    unknown = sorted(set(mapping) - set(REQUIRED_KEYS))
    if not unknown:
        return
    names = ", ".join(str(key) for key in unknown)
    raise ConfigError(f"неизвестные параметры: {names}")


def _take(mapping: dict[str, object], key: str) -> object:
    """Вернуть значение обязательного параметра."""
    if key not in mapping:
        raise ConfigError(f"{key}: параметр отсутствует")
    return mapping[key]


def _expect_type(key: str, value: object, expected: type) -> object:
    """Проверить, что значение задано и имеет точный тип."""
    if value is None:
        raise ConfigError(f"{key}: значение не задано")
    if type(value) is not expected:
        name = TYPE_NAMES[expected]
        raise ConfigError(f"{key}: ожидался тип «{name}»")
    return value


def _validate_package_name(value: object) -> str:
    """Проверить имя пакета Cargo."""
    text = cast(str, _expect_type(KEY_PACKAGE_NAME, value, str))
    name = text.strip()
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


def _validate_test_mode(value: object) -> bool:
    """Проверить логический режим тестового репозитория."""
    flag = cast(
        bool,
        _expect_type(KEY_TEST_REPOSITORY_MODE, value, bool),
    )
    return flag


def _validate_repository(
    value: object,
    test_mode: bool,
    config_dir: str,
) -> str:
    """Проверить URL репозитория или путь к тестовому файлу."""
    text = cast(str, _expect_type(KEY_REPOSITORY, value, str))
    location = text.strip()
    if location == "":
        raise ConfigError(
            f"{KEY_REPOSITORY}: значение не может быть пустым",
        )
    if test_mode:
        return _validate_test_file(location, config_dir)
    return _validate_remote_url(location)


def _validate_test_file(location: str, config_dir: str) -> str:
    """Проверить путь к файлу тестового репозитория."""
    if _is_http_url(location):
        raise ConfigError(
            f"{KEY_REPOSITORY}: в тестовом режиме нужен путь "
            "к файлу, а не URL",
        )
    candidate = location
    if not os.path.isabs(candidate):
        candidate = os.path.join(config_dir, candidate)
    if not os.path.isfile(candidate):
        raise ConfigError(
            f"{KEY_REPOSITORY}: тестовый файл не найден: {location}",
        )
    return os.path.abspath(candidate)


def _validate_remote_url(location: str) -> str:
    """Проверить абсолютный http(s)-адрес репозитория."""
    if any(char.isspace() for char in location):
        raise ConfigError(
            f"{KEY_REPOSITORY}: URL не должен содержать пробелы",
        )
    parsed = urlparse(location)
    scheme_ok = parsed.scheme in HTTP_SCHEMES
    if not scheme_ok or parsed.netloc == "":
        raise ConfigError(
            f"{KEY_REPOSITORY}: нужен абсолютный URL "
            "со схемой http или https",
        )
    return location


def _is_http_url(location: str) -> bool:
    """Определить, похожа ли строка на http(s)-адрес."""
    lowered = location.lower()
    return (
        lowered.startswith("http://")
        or lowered.startswith("https://")
    )


def _validate_image_name(value: object) -> str:
    """Проверить имя PNG-файла с изображением графа."""
    text = cast(str, _expect_type(KEY_GRAPH_IMAGE_NAME, value, str))
    name = text.strip()
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


def _validate_filter(value: object) -> str:
    """Проверить подстроку фильтрации имён пакетов."""
    text = cast(str, _expect_type(KEY_FILTER_SUBSTRING, value, str))
    if any(char in text for char in "\r\n"):
        raise ConfigError(
            f"{KEY_FILTER_SUBSTRING}: значение должно быть "
            "одной строкой без перевода строки",
        )
    return text
