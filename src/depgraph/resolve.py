from __future__ import annotations

import json
from collections.abc import Callable

from depgraph.config import AppConfig
from depgraph.dependencies import http_get
from depgraph.graph import Graph, GraphError, build_graph
from depgraph.letter_graph import parse_letter_graph

Reader = Callable[[str], str]

CRATES_API = "https://crates.io/api/v1/crates"
NORMAL_KIND = "normal"


def build_test_graph(config: AppConfig) -> Graph:
    with open(config.repository, encoding="utf-8") as handle:
        text = handle.read()
    described = parse_letter_graph(text)
    if config.package_name not in described:
        raise GraphError(
            f"пакет {config.package_name} не описан в тестовом файле",
        )

    def neighbors(node: str) -> list[str]:
        return list(described.get(node, ()))

    return build_graph(
        config.package_name,
        neighbors,
        config.filter_substring,
    )


def build_cargo_graph(
    config: AppConfig,
    direct: list[tuple[str, str]],
    fetch: Reader | None = None,
) -> Graph:
    reader = http_get if fetch is None else fetch
    requirements = {name: version for name, version in direct}

    def neighbors(node: str) -> list[str]:
        if node == config.package_name:
            return [name for name, _version in direct]
        pairs = crate_dependencies(
            node,
            requirements.get(node, ""),
            reader,
        )
        for name, requirement in pairs:
            requirements.setdefault(name, requirement)
        return [name for name, _requirement in pairs]

    return build_graph(
        config.package_name,
        neighbors,
        config.filter_substring,
    )


def crate_dependencies(
    name: str,
    requirement: str,
    fetch: Reader,
) -> list[tuple[str, str]]:
    version = _resolve(name, requirement, fetch)
    url = f"{CRATES_API}/{name}/{version}/dependencies"
    payload = _read_json(fetch(url))
    items = payload.get("dependencies")
    if not isinstance(items, list):
        return []
    found: list[tuple[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("kind") not in (NORMAL_KIND, None):
            continue
        crate = item.get("crate_id")
        if not isinstance(crate, str):
            continue
        req = item.get("req")
        if not isinstance(req, str):
            req = ""
        found.append((crate, req))
    return found


def _resolve(name: str, requirement: str, fetch: Reader) -> str:
    exact = _exact_version(requirement)
    if exact != "":
        return exact
    url = f"{CRATES_API}/{name}"
    payload = _read_json(fetch(url))
    crate = payload.get("crate")
    if not isinstance(crate, dict):
        raise GraphError(f"crates.io не знает пакет {name}")
    version = crate.get("max_stable_version")
    if not isinstance(version, str) or version == "":
        version = crate.get("newest_version")
    if not isinstance(version, str) or version == "":
        raise GraphError(f"у пакета {name} нет стабильной версии")
    return version


def _exact_version(requirement: str) -> str:
    text = requirement.strip()
    if not text.startswith("="):
        return ""
    version = text[1:].strip()
    if version == "" or not version[0].isdigit():
        return ""
    return version


def _read_json(text: object) -> dict[str, object]:
    if not isinstance(text, str):
        raise GraphError("crates.io вернул не текст")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise GraphError("crates.io вернул не JSON") from error
    if not isinstance(payload, dict):
        raise GraphError("crates.io вернул не объект JSON")
    return payload
