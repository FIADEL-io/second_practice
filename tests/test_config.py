"""Проверки загрузки и отклонения YAML-конфигурации."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from depgraph.config import ConfigError, load_config
from depgraph.constants import (
    KEY_FILTER_SUBSTRING,
    KEY_GRAPH_IMAGE_NAME,
    KEY_PACKAGE_NAME,
    KEY_REPOSITORY,
    KEY_TEST_REPOSITORY_MODE,
    MAX_FILENAME_LENGTH,
    MAX_PACKAGE_NAME_LENGTH,
    PNG_EXTENSION,
    REQUIRED_KEYS,
)

VALID = {
    KEY_PACKAGE_NAME: "serde",
    KEY_REPOSITORY: "https://github.com/serde-rs/serde",
    KEY_TEST_REPOSITORY_MODE: False,
    KEY_GRAPH_IMAGE_NAME: "serde.png",
    KEY_FILTER_SUBSTRING: "",
}

WRONG_TYPES = {
    KEY_PACKAGE_NAME: 1,
    KEY_REPOSITORY: 1,
    KEY_TEST_REPOSITORY_MODE: "false",
    KEY_GRAPH_IMAGE_NAME: 1,
    KEY_FILTER_SUBSTRING: 1,
}


class ConfigTests(unittest.TestCase):
    """Загрузка корректных файлов и ошибки по каждому параметру."""

    def write_config(self, data: dict[str, object]) -> str:
        """Сохранить словарь во временный YAML-файл."""
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = os.path.join(folder.name, "config.yaml")
        with open(path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(
                data,
                handle,
                allow_unicode=True,
                sort_keys=False,
            )
        return path

    def write_with_repo(self, data: dict[str, object]) -> str:
        """Сохранить конфиг и файл тестового репозитория рядом."""
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        repo_path = os.path.join(folder.name, "repo.txt")
        with open(repo_path, "w", encoding="utf-8") as handle:
            handle.write("A\n")
        config_path = os.path.join(folder.name, "config.yaml")
        with open(config_path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(
                data,
                handle,
                allow_unicode=True,
                sort_keys=False,
            )
        return config_path

    def reject(self, data: dict[str, object]) -> str:
        """Вернуть текст ошибки для временной конфигурации."""
        path = self.write_config(data)
        with self.assertRaises(ConfigError) as caught:
            load_config(path)
        return str(caught.exception)

    def test_loads_remote_repository(self) -> None:
        """URL принимается, когда тестовый режим выключен."""
        config = load_config(self.write_config(VALID))
        self.assertEqual(config.package_name, "serde")
        self.assertFalse(config.test_repository_mode)
        self.assertEqual(
            config.repository,
            "https://github.com/serde-rs/serde",
        )
        self.assertEqual(config.graph_image_name, "serde.png")
        self.assertEqual(config.filter_substring, "")

    def test_loads_shipped_configs(self) -> None:
        """Примеры из репозитория проходят проверку."""
        remote = load_config(str(_ROOT / "config.yaml"))
        self.assertEqual(remote.package_name, "serde")
        tested = load_config(
            str(_ROOT / "examples" / "test_repository.yaml"),
        )
        self.assertTrue(tested.test_repository_mode)
        self.assertTrue(os.path.isfile(tested.repository))

    def test_resolves_test_repository_near_config(self) -> None:
        """Относительный путь считается от каталога YAML-файла."""
        data = dict(VALID)
        data[KEY_REPOSITORY] = "repo.txt"
        data[KEY_TEST_REPOSITORY_MODE] = True
        data[KEY_PACKAGE_NAME] = "A"
        config = load_config(self.write_with_repo(data))
        self.assertTrue(config.repository.endswith("repo.txt"))
        self.assertTrue(os.path.isfile(config.repository))

    def test_rejects_every_missing_parameter(self) -> None:
        """Каждый обязательный параметр должен присутствовать."""
        for key in REQUIRED_KEYS:
            data = dict(VALID)
            del data[key]
            with self.subTest(key=key):
                self.assertIn(key, self.reject(data))

    def test_rejects_wrong_type_of_every_parameter(self) -> None:
        """У каждого параметра проверяется тип значения."""
        for key, wrong in WRONG_TYPES.items():
            data = dict(VALID)
            data[key] = wrong
            with self.subTest(key=key):
                self.assertIn(key, self.reject(data))

    def test_rejects_empty_package_name(self) -> None:
        """Пустое имя пакета недопустимо."""
        data = dict(VALID)
        data[KEY_PACKAGE_NAME] = "   "
        self.assertIn(KEY_PACKAGE_NAME, self.reject(data))

    def test_rejects_package_name_outside_cargo_rules(self) -> None:
        """Имя пакета подчиняется правилам Cargo."""
        data = dict(VALID)
        data[KEY_PACKAGE_NAME] = "serde json"
        self.assertIn(KEY_PACKAGE_NAME, self.reject(data))

    def test_enforces_package_name_length(self) -> None:
        """Имя длиннее предела Cargo отклоняется."""
        data = dict(VALID)
        data[KEY_PACKAGE_NAME] = "a" * MAX_PACKAGE_NAME_LENGTH
        load_config(self.write_config(data))
        data[KEY_PACKAGE_NAME] += "b"
        self.assertIn(KEY_PACKAGE_NAME, self.reject(data))

    def test_rejects_remote_repository_errors(self) -> None:
        """В обычном режиме repository — это http(s) URL."""
        cases = ("", "crates.io/serde", "ftp://example.com/pkg", "https://")
        for location in cases:
            data = dict(VALID)
            data[KEY_REPOSITORY] = location
            with self.subTest(location=location):
                self.assertIn(KEY_REPOSITORY, self.reject(data))

    def test_rejects_spaces_in_url(self) -> None:
        """Пробел в URL — ошибка параметра repository."""
        data = dict(VALID)
        data[KEY_REPOSITORY] = "https://example.com/my repo"
        self.assertIn(KEY_REPOSITORY, self.reject(data))

    def test_rejects_path_when_remote_mode(self) -> None:
        """Путь к файлу не заменяет URL вне тестового режима."""
        data = dict(VALID)
        data[KEY_REPOSITORY] = "repo.txt"
        self.assertIn(KEY_REPOSITORY, self.reject(data))

    def test_rejects_missing_test_file(self) -> None:
        """В тестовом режиме файл репозитория должен существовать."""
        data = dict(VALID)
        data[KEY_TEST_REPOSITORY_MODE] = True
        data[KEY_REPOSITORY] = "missing.txt"
        self.assertIn(KEY_REPOSITORY, self.reject(data))

    def test_rejects_url_in_test_mode(self) -> None:
        """В тестовом режиме URL не принимается."""
        data = dict(VALID)
        data[KEY_TEST_REPOSITORY_MODE] = True
        self.assertIn(KEY_REPOSITORY, self.reject(data))

    def test_rejects_bad_image_names(self) -> None:
        """Имя картинки — один PNG-файл без каталога."""
        names = ("", "serde.svg", "out/serde.png", "граф.png")
        for name in names:
            data = dict(VALID)
            data[KEY_GRAPH_IMAGE_NAME] = name
            with self.subTest(name=name):
                self.assertIn(KEY_GRAPH_IMAGE_NAME, self.reject(data))

    def test_enforces_image_name_length(self) -> None:
        """Слишком длинное имя файла изображения отклоняется."""
        stem_length = MAX_FILENAME_LENGTH - len(PNG_EXTENSION)
        data = dict(VALID)
        data[KEY_GRAPH_IMAGE_NAME] = "a" * stem_length + PNG_EXTENSION
        load_config(self.write_config(data))
        data[KEY_GRAPH_IMAGE_NAME] = "a" + data[KEY_GRAPH_IMAGE_NAME]
        self.assertIn(KEY_GRAPH_IMAGE_NAME, self.reject(data))

    def test_allows_empty_filter(self) -> None:
        """Пустая подстрока означает отсутствие фильтрации."""
        config = load_config(self.write_config(VALID))
        self.assertEqual(config.filter_substring, "")

    def test_rejects_multiline_filter(self) -> None:
        """Подстрока фильтрации должна печататься одной строкой."""
        data = dict(VALID)
        data[KEY_FILTER_SUBSTRING] = "foo\nbar"
        self.assertIn(KEY_FILTER_SUBSTRING, self.reject(data))

    def test_rejects_unknown_parameter(self) -> None:
        """Лишний параметр не молча игнорируется."""
        data = dict(VALID)
        data["depth"] = 1
        self.assertIn("depth", self.reject(data))

    def test_rejects_non_mapping_document(self) -> None:
        """Корень YAML должен быть словарём параметров."""
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = os.path.join(folder.name, "config.yaml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("- serde\n")
        with self.assertRaises(ConfigError):
            load_config(path)

    def test_rejects_broken_yaml(self) -> None:
        """Синтаксическая ошибка YAML сообщается явно."""
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = os.path.join(folder.name, "config.yaml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("package_name: [\n")
        with self.assertRaises(ConfigError) as caught:
            load_config(path)
        self.assertIn("YAML", str(caught.exception))

    def test_rejects_missing_config_file(self) -> None:
        """Отсутствующий файл конфигурации — ошибка."""
        with self.assertRaises(ConfigError) as caught:
            load_config(os.path.join("missing", "config.yaml"))
        self.assertIn("не найден", str(caught.exception))

    def test_rejects_directory_as_config(self) -> None:
        """Каталог нельзя передать вместо файла конфигурации."""
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        with self.assertRaises(ConfigError):
            load_config(folder.name)

    def test_error_examples_are_rejected(self) -> None:
        """Каждый файл в examples/errors завершается ошибкой."""
        folder = _ROOT / "examples" / "errors"
        paths = sorted(folder.glob("*.yaml"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(path=path.name):
                with self.assertRaises(ConfigError):
                    load_config(str(path))


if __name__ == "__main__":
    unittest.main()
