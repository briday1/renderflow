from __future__ import annotations

from renderflow.contracts import ParamSpec
from renderflow.param_options import resolve_dropdown_options


def test_resolve_dropdown_options_with_static_scalar_list():
    spec = ParamSpec(key="x", label="X", type="dropdown", options=["a", "b"])
    resolved = resolve_dropdown_options(spec, {})
    assert resolved == [
        {"label": "a", "value": "a"},
        {"label": "b", "value": "b"},
    ]


def test_resolve_dropdown_options_with_callable_options():
    def _options(values, spec):
        directory = values.get("directory", "")
        if directory == "examples":
            return [
                {"label": "File A", "value": "a.crsd"},
                {"label": "File B", "value": "b.crsd"},
            ]
        return []

    spec = ParamSpec(key="file", label="File", type="dropdown", options=_options)

    resolved = resolve_dropdown_options(spec, {"directory": "examples"})
    assert resolved == [
        {"label": "File A", "value": "a.crsd"},
        {"label": "File B", "value": "b.crsd"},
    ]

    fallback = resolve_dropdown_options(spec, {"directory": "empty"})
    assert fallback == [{"label": "(no options)", "value": ""}]
