"""Командная строка этапа 1: вывод проверенных параметров."""

from __future__ import annotations

import argparse
import sys

from depgraph.config import AppConfig, ConfigError, load_config
from depgraph.constants import EXIT_CONFIG, EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Загрузить конфигурацию и напечатать её параметры.

    Сообщение об ошибке конфигурации пишется в stderr.
    """
    _configure_stdio()
    args = _parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"ошибка конфигурации: {error}", file=sys.stderr)
        return EXIT_CONFIG
    print(format_parameters(config))
    return EXIT_OK


def format_parameters(config: AppConfig) -> str:
    """Собрать параметры в строки «ключ: значение»."""
    lines = [f"{key}: {value}" for key, value in config.as_pairs()]
    return "\n".join(lines)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Разобрать аргументы командной строки."""
    parser = argparse.ArgumentParser(
        prog="depgraph",
        description=(
            "Визуализация графа зависимостей Cargo. "
            "Этап 1 выводит параметры из YAML."
        ),
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Путь к YAML-файлу с параметрами.",
    )
    return parser.parse_args(argv)


def _configure_stdio() -> None:
    """Печатать сообщения в UTF-8, если поток это позволяет."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            continue
