"""
Entry points called by the page (web/js/lib/pyworker.js), through Pyodide.
==========================================================================

    start(demo_id, options_json)        -> JSON {"session": token, "state": ...}
    call(token, action, payload_json)   -> JSON state

Errors come back as JSON {"error": message}, so the page can report them.
The same functions run under plain Python, which the tests use.
"""
from __future__ import annotations

import importlib
import json
import secrets
import traceback
from collections import OrderedDict

from .catalog import DEMOS
from .common import to_jsonable

MAX_SESSIONS = 16
_SESSIONS: OrderedDict = OrderedDict()


def _session_class(demo_id: str):
    path = DEMOS[demo_id]["session"]
    module, name = path.split(":")
    return getattr(importlib.import_module(f"sessions.{module}"), name)


def _error(error: Exception) -> str:
    traceback.print_exc()
    return json.dumps({"error": f"{type(error).__name__}: {error}"})


def start(demo_id: str, options_json: str = "{}") -> str:
    try:
        session = _session_class(demo_id)(**json.loads(options_json or "{}"))
        token = secrets.token_urlsafe(9)
        _SESSIONS[token] = session
        while len(_SESSIONS) > MAX_SESSIONS:
            _SESSIONS.popitem(last=False)
        return json.dumps({"session": token, "state": to_jsonable(session.state())})
    except Exception as error:                      # reported to the page
        return _error(error)


def call(token: str, action: str, payload_json: str = "{}") -> str:
    try:
        session = _SESSIONS[token]
        _SESSIONS.move_to_end(token)
        return json.dumps(to_jsonable(session.dispatch(action, json.loads(payload_json or "{}"))))
    except KeyError as error:
        if token not in _SESSIONS:
            return json.dumps({"error": "session expired: reload the page"})
        return _error(error)
    except Exception as error:                      # reported to the page
        return _error(error)
