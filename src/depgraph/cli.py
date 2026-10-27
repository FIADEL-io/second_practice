from __future__ import annotations

import argparse
import sys

from depgraph.config import AppConfig, ConfigError, load_config
from depgraph.constants import EXIT_CONFIG, EXIT_OK


def main(argv: list[str] | None = None) -> int:
    _use_utf8()
    args = _parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"ошибка конфигурации: {error}", file=sys.stderr)
        return EXIT_CONFIG
    print(format_parameters(config))
    return EXIT_OK


def format_parameters(config: AppConfig) -> str:
    lines = [f"{key}: {value}" for key, value in config.as_pairs()]
    return "\n".join(lines)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
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


def _use_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            continue
