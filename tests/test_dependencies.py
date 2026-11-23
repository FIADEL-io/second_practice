import unittest

from bootstrap import ROOT
from depgraph.cargo_manifest import CargoError, parse_manifest
from depgraph.config import load_config
from depgraph.dependencies import load_direct_dependencies

ROOT_MANIFEST = """
[workspace]
members = [
  "serde",
  "missing",
]

[workspace.dependencies]
proc-macro2 = "1.0"
"""

SERDE_MANIFEST = """
[package]
name = "serde"
version = "1.0.0"

[dependencies]
serde_derive = { version = "1", optional = true, package = "serde_derive" }
itoa = "1.0"
renamed = { package = "real_name", version = "2.0" }
path_only = { path = "../path_only" }

[dev-dependencies]
tempfile = "3"
"""

SINGLE_MANIFEST = """
[package]
name = "only"
version = "0.1.0"

[dependencies]
left = "1"
"""


class DependencyTests(unittest.TestCase):

    def test_reads_workspace_member_not_dev_dependencies(self) -> None:
        config = self._config()
        dependencies = load_direct_dependencies(
            config,
            fetch=self._fetch,
        )
        self.assertEqual(
            dependencies,
            [
                ("itoa", "1.0"),
                ("path_only", ""),
                ("real_name", "2.0"),
                ("serde_derive", "1"),
            ],
        )

    def test_reads_single_package_manifest(self) -> None:
        config = self._config()
        config = _renamed(config, "only")

        def fetch(url: str) -> str:
            if url.endswith("/Cargo.toml") and "/only/" not in url:
                return SINGLE_MANIFEST
            raise CargoError("лишний запрос")

        dependencies = load_direct_dependencies(config, fetch=fetch)
        self.assertEqual(dependencies, [("left", "1")])

    def test_reports_missing_package(self) -> None:
        config = _renamed(self._config(), "absent")
        with self.assertRaises(CargoError) as caught:
            load_direct_dependencies(config, fetch=self._fetch)
        self.assertIn("absent", str(caught.exception))

    def test_rejects_non_github_url(self) -> None:
        config = load_config(str(ROOT / "config.yaml"))
        values = config.as_pairs()
        self.assertIn(("package_name", "serde"), values)
        with self.assertRaises(CargoError):
            load_direct_dependencies(
                _renamed(config, "serde", "https://gitlab.com/org/repo"),
                fetch=self._fetch,
            )

    def test_ignores_comments_in_manifest(self) -> None:
        manifest = parse_manifest(
            '[package]\nname = "demo" # имя\n'
            '[dependencies]\nfoo = "1" # версия\n',
        )
        self.assertEqual(manifest["package"], {"name": "demo"})

    def _config(self):
        return _renamed(
            load_config(str(ROOT / "config.yaml")),
            "serde",
        )

    def _fetch(self, url: str) -> str:
        if url.endswith("/missing/Cargo.toml"):
            from depgraph.cargo_manifest import ManifestNotFound
            raise ManifestNotFound(url)
        if url.endswith("/serde/Cargo.toml"):
            return SERDE_MANIFEST
        root_names = ("/main/Cargo.toml", "/master/Cargo.toml")
        if url.endswith(root_names):
            return ROOT_MANIFEST
        raise CargoError(url)


def _renamed(config, package_name: str, repository: str | None = None):
    return type(config)(
        package_name=package_name,
        repository=config.repository if repository is None else repository,
        test_repository_mode=False,
        graph_image_name=config.graph_image_name,
        filter_substring=config.filter_substring,
    )


if __name__ == "__main__":
    unittest.main()
