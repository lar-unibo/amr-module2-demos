"""
Build the static site into site/ (standard library only).
=========================================================

    python tools/build_site.py

The site is web/ plus the Python sources that run in the browser:

    site/                  copy of web/ (pages, scripts, styles, KaTeX, Pyodide)
    site/py/course/...     the course package
    site/py/sessions/...   the demo sessions
    site/py/manifest.json  the list of Python files, read by js/lib/pyworker.js
    site/catalog.json      course, lectures, and demos (read by the menu)

site/ is a build output (not committed); GitHub Actions builds and deploys it.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PACKAGES = ["course", "sessions"]


def build(target: Path = SITE) -> Path:
    sys.path.insert(0, str(ROOT))
    from sessions.catalog import catalog          # the catalog module imports no numpy

    if not (ROOT / "web" / "vendor" / "pyodide" / "pyodide.mjs").exists():
        raise SystemExit("Pyodide is missing: run  python tools/fetch_pyodide.py")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(ROOT / "web", target)
    files = []
    for package in PACKAGES:
        for source in sorted((ROOT / package).rglob("*.py")):
            relative = source.relative_to(ROOT).as_posix()
            destination = target / "py" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            files.append(relative)
    (target / "py" / "manifest.json").write_text(json.dumps({"files": files}, indent=1))
    (target / "catalog.json").write_text(json.dumps(catalog(), indent=1, ensure_ascii=False))
    (target / ".nojekyll").write_text("")          # serve files as they are on GitHub Pages
    return target


if __name__ == "__main__":
    out = build()
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"built {out.relative_to(ROOT)}/ ({size / 1e6:.1f} MB)")
