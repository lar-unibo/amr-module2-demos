"""
Shared pieces of the demo sessions.
===================================

`Session` is the state of one open demo page, kept in Python (in the browser,
through Pyodide). Its public `act_<name>` methods are the actions the page
can request; each returns the new state, a dict of JSON-friendly values.
"""
from __future__ import annotations

import numpy as np


class Session:
    """One open demo page. Subclasses implement `state` and `act_*` actions."""

    def dispatch(self, action: str, payload: dict):
        method = getattr(self, f"act_{action}", None)
        if method is None:
            raise KeyError(f"unknown action: {action}")
        return method(**payload)

    def state(self) -> dict:
        raise NotImplementedError


def to_jsonable(value):
    """numpy arrays and scalars -> JSON types (non-finite numbers -> None)."""
    if isinstance(value, np.ndarray):
        array = np.round(value.astype(float), 7)
        if not np.all(np.isfinite(array)):
            array = array.astype(object)
            array[~np.isfinite(value.astype(float))] = None
        return array.tolist()
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.integer, np.bool_)):
        return value.item()
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    return value
