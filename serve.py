"""
Build the site and serve it locally (standard library only, works offline).
==========================================================================

    python serve.py                 build site/ and open http://127.0.0.1:8765/
    python serve.py --port 9000     another port
    python serve.py --no-browser    do not open a browser window
    python serve.py --no-build      serve site/ as it is

The demos run their Python code in the browser (Pyodide), so this is a plain
static file server, the same as GitHub Pages.
"""
from __future__ import annotations

import argparse
import functools
import mimetypes
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
from build_site import SITE, build  # noqa: E402

# Correct types make the browser compile the WebAssembly while it downloads.
mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("font/woff2", ".woff2")


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      ".wasm": "application/wasm", ".mjs": "text/javascript", ".js": "text/javascript"}

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")        # always revalidate while developing
        super().end_headers()

    def log_message(self, *args):                            # keep the terminal quiet
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    if not args.no_build:
        build()
    handler = functools.partial(Handler, directory=str(SITE))
    for port in (args.port, 0):                              # 0: any free port
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), handler)
            break
        except OSError:
            continue
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Serving {SITE} at {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
