import contextlib
import io
import unittest

from bootstrap import ROOT
from depgraph.cli import main
from depgraph.constants import EXIT_CONFIG, EXIT_OK, REQUIRED_KEYS


class CliTests(unittest.TestCase):

    def test_prints_parameters_as_key_value(self) -> None:
        stdout = io.StringIO()
        path = str(ROOT / "config.yaml")
        with contextlib.redirect_stdout(stdout):
            code = main(["--config", path])
        lines = stdout.getvalue().splitlines()
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(len(lines), len(REQUIRED_KEYS))
        self.assertIn("package_name: serde", lines)
        self.assertIn("test_repository_mode: false", lines)
        self.assertIn("graph_image_name: serde.png", lines)
        self.assertIn("filter_substring: ", lines)

    def test_prints_resolved_test_repository(self) -> None:
        stdout = io.StringIO()
        path = str(ROOT / "examples" / "test_repository.yaml")
        with contextlib.redirect_stdout(stdout):
            code = main(["--config", path])
        text = stdout.getvalue()
        self.assertEqual(code, EXIT_OK)
        self.assertIn("package_name: A", text)
        self.assertIn("test_repository_mode: true", text)
        self.assertIn("graph.txt", text)

    def test_config_error_goes_to_stderr(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        path = str(ROOT / "examples" / "errors" / "bad_url.yaml")
        with contextlib.redirect_stdout(stdout):
            with contextlib.redirect_stderr(stderr):
                code = main(["--config", path])
        self.assertEqual(code, EXIT_CONFIG)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("ошибка конфигурации", stderr.getvalue())
        self.assertIn("repository", stderr.getvalue())

    def test_missing_file_is_config_error(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = main(["--config", "no-such-config.yaml"])
        self.assertEqual(code, EXIT_CONFIG)
        self.assertIn("не найден", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
