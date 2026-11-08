"""
Download a pinned Pyodide release into web/vendor/pyodide (standard library only).
==================================================================================

    python tools/fetch_pyodide.py

The site runs its Python code in the browser with Pyodide. To keep the site
working offline and independent of a CDN, the runtime files are stored in the
repository: the core files of the release, plus the wheels of the packages
listed in PACKAGES (and their dependencies). The lock file is pruned to those
packages, and every wheel is checked against the SHA-256 of the lock file.
Run it again after changing VERSION or PACKAGES.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import urllib.request
from pathlib import Path

VERSION = "314.0.7"                      # released 2026-09-14: Python 3.14, numpy 2.4.6
PACKAGES = ["numpy"]
BASE = f"https://cdn.jsdelivr.net/pyodide/v{VERSION}/full/"
CORE = ["pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip"]
LICENSE_URL = f"https://raw.githubusercontent.com/pyodide/pyodide/{VERSION}/LICENSE"

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "web" / "vendor" / "pyodide"


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def closure(lock: dict, names: list[str]) -> list[str]:
    """The requested packages and, recursively, their dependencies."""
    keep, todo = [], list(names)
    while todo:
        name = todo.pop()
        if name in keep:
            continue
        keep.append(name)
        todo.extend(lock["packages"][name].get("depends", []))
    return sorted(keep)


def main() -> int:
    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.mkdir(parents=True)
    for name in CORE:
        data = fetch(BASE + name)
        (TARGET / name).write_bytes(data)
        print(f"{name:24s} {len(data) / 1e6:6.2f} MB")

    lock = json.loads(fetch(BASE + "pyodide-lock.json"))
    keep = closure(lock, PACKAGES)
    for name in keep:
        entry = lock["packages"][name]
        data = fetch(BASE + entry["file_name"])
        digest = hashlib.sha256(data).hexdigest()
        if digest != entry["sha256"]:
            print(f"checksum mismatch for {entry['file_name']}", file=sys.stderr)
            return 1
        (TARGET / entry["file_name"]).write_bytes(data)
        print(f"{entry['file_name']:24.24s} {len(data) / 1e6:6.2f} MB  sha256 ok")
    lock["packages"] = {name: lock["packages"][name] for name in keep}
    (TARGET / "pyodide-lock.json").write_text(json.dumps(lock, indent=1))

    try:
        (TARGET / "LICENSE").write_bytes(fetch(LICENSE_URL))
    except OSError as error:                       # the release must still ship its licence
        print(f"could not download the Pyodide LICENSE ({error}); add it by hand", file=sys.stderr)
        return 1
    (TARGET / "VERSION").write_text(f"Pyodide {VERSION} ({BASE})\npackages: {', '.join(keep)}\n")
    total = sum(f.stat().st_size for f in TARGET.iterdir())
    print(f"total {total / 1e6:.1f} MB in {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
