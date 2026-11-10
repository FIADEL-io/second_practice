from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable
from urllib.parse import urlparse

from depgraph.cargo_manifest import (
    CargoError,
    ManifestNotFound,
    direct_dependencies,
    package_name,
    parse_manifest,
    workspace_members,
)
from depgraph.config import AppConfig
from depgraph.constants import GITHUB_BRANCHES, HTTP_NOT_FOUND, HTTP_TIMEOUT

Reader = Callable[[str], str]


def load_direct_dependencies(
    config: AppConfig,
    fetch: Reader | None = None,
) -> list[tuple[str, str]]:
    reader = http_get if fetch is None else fetch
    root_text = _download(config.repository, "Cargo.toml", reader)
    root = parse_manifest(root_text)
    if package_name(root) == config.package_name:
        return direct_dependencies(root)
    for member in workspace_members(root):
        relative = f"{member}/Cargo.toml"
        try:
            text = _download(config.repository, relative, reader)
        except ManifestNotFound:
            continue
        manifest = parse_manifest(text)
        if package_name(manifest) == config.package_name:
            return direct_dependencies(manifest)
    raise CargoError(
        f"в репозитории нет пакета {config.package_name}",
    )


def format_dependencies(dependencies: list[tuple[str, str]]) -> str:
    lines: list[str] = []
    for name, version in dependencies:
        if version == "":
            lines.append(name)
        else:
            lines.append(f"{name} {version}")
    return "\n".join(lines)


def http_get(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "depgraph"},
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=HTTP_TIMEOUT,
        ) as response:
            payload = response.read()
    except urllib.error.HTTPError as error:
        if error.code == HTTP_NOT_FOUND:
            raise ManifestNotFound(url) from error
        raise CargoError(
            f"не удалось скачать манифест: {error.code}",
        ) from error
    except urllib.error.URLError as error:
        raise CargoError(
            f"не удалось скачать манифест: {error.reason}",
        ) from error
    return payload.decode("utf-8")


def _download(repository: str, relative: str, fetch: Reader) -> str:
    urls = _manifest_urls(repository, relative)
    for url in urls:
        try:
            return fetch(url)
        except ManifestNotFound:
            continue
    raise ManifestNotFound(relative)


def _manifest_urls(repository: str, relative: str) -> list[str]:
    owner, repo = _github_repo(repository)
    urls: list[str] = []
    for branch in GITHUB_BRANCHES:
        base = "https://raw.githubusercontent.com"
        urls.append(f"{base}/{owner}/{repo}/{branch}/{relative}")
    return urls


def _github_repo(repository: str) -> tuple[str, str]:
    parsed = urlparse(repository)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[len("www."):]
    if host != "github.com":
        raise CargoError(
            "этап 2 читает Cargo.toml только из репозитория GitHub",
        )
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise CargoError("в URL репозитория нет владельца и имени")
    repo = parts[1]
    if repo.endswith(".git"):
        repo = repo[: -len(".git")]
    return parts[0], repo
