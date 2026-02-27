"""Helpers for resolving parameter options."""

from __future__ import annotations

from typing import Any


def normalize_dropdown_options(raw_options) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for option in raw_options or []:
        if isinstance(option, dict):
            value = option.get("value")
            label = option.get("label", value)
            normalized.append({"label": label, "value": value})
        else:
            normalized.append({"label": option, "value": option})
    return normalized


def resolve_dropdown_options(spec, values: dict[str, Any]) -> list[dict[str, Any]]:
    options = spec.options
    if callable(options):
        try:
            options = options(dict(values), spec)
        except TypeError:
            # Backward-compatible callable shape: options(values)
            options = options(dict(values))
    normalized = normalize_dropdown_options(options)
    if not normalized:
        normalized = [{"label": "(no options)", "value": ""}]
    return normalized

