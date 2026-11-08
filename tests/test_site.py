"""The static site builds, and every demo has its page files and its Python sources."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_site import build  # noqa: E402


class Site(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.site = build(Path(cls.tmp.name) / "site")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_demo_has_its_files(self):
        data = json.loads((self.site / "catalog.json").read_text())
        for lecture in data["lectures"]:
            for demo in lecture["demos"]:
                for path in (f"lessons/{demo['id']}.html", f"js/demos/{demo['id']}.js"):
                    self.assertTrue((self.site / path).is_file(), msg=path)

    def test_python_sources_are_listed_and_copied(self):
        files = json.loads((self.site / "py" / "manifest.json").read_text())["files"]
        expected = sorted(p.relative_to(ROOT).as_posix() for pkg in ("course", "sessions") for p in (ROOT / pkg).rglob("*.py"))
        self.assertEqual(sorted(files), expected)
        for file in files:
            self.assertTrue((self.site / "py" / file).is_file(), msg=file)

    def test_pyodide_runtime_and_packages_are_vendored(self):
        vendor = self.site / "vendor" / "pyodide"
        for name in ("pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "LICENSE"):
            self.assertTrue((vendor / name).is_file(), msg=name)
        lock = json.loads((vendor / "pyodide-lock.json").read_text())
        self.assertIn("numpy", lock["packages"])
        for package in lock["packages"].values():
            self.assertTrue((vendor / package["file_name"]).is_file(), msg=package["file_name"])

    def test_pages_publishing_files(self):
        self.assertTrue((self.site / ".nojekyll").is_file())
        for page in ("index.html", "demo.html"):
            self.assertTrue((self.site / page).is_file())


if __name__ == "__main__":
    unittest.main()
