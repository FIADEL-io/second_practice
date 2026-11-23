from __future__ import annotations

import re

from depgraph.graph import GraphError

PACKAGE = re.compile(r"^[A-Z]+$")


def parse_letter_graph(text: str) -> dict[str, tuple[str, ...]]:
    graph: dict[str, tuple[str, ...]] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line == "":
            continue
        _add_line(graph, line)
    if not graph:
        raise GraphError("в тестовом файле нет пакетов")
    return graph


def _add_line(graph: dict[str, tuple[str, ...]], line: str) -> None:
    if ":" not in line:
        raise GraphError(f"нет двоеточия в строке: {line}")
    left, right = line.split(":", 1)
    name = left.strip()
    _check_name(name)
    if name in graph:
        raise GraphError(f"пакет {name} указан дважды")
    deps: list[str] = []
    for item in right.split():
        _check_name(item)
        if item not in deps:
            deps.append(item)
    graph[name] = tuple(deps)


def _check_name(name: str) -> None:
    if PACKAGE.fullmatch(name) is None:
        raise GraphError(
            f"имя {name} должно состоять из больших латинских букв",
        )
