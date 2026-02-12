"""Discovery helpers for provider plugins."""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import entry_points

from renderflow.contracts import AppSpec

PROVIDER_GROUP = "renderflow.providers"


def list_provider_names() -> list[str]:
    """Return installed provider names registered under renderflow.providers."""
    eps = entry_points()
    if hasattr(eps, "select"):
        selected = eps.select(group=PROVIDER_GROUP)  # type: ignore[attr-defined]
    else:
        selected = eps.get(PROVIDER_GROUP, [])  # type: ignore[call-arg]
    return sorted(ep.name for ep in selected)


def load_app_spec(provider_name: str) -> AppSpec:
    """
    Load provider app definition by name.

    Resolution order:
    1) Entry-point group `renderflow.providers`
    2) Backward compatible module import `<provider_name>.app_definition:get_app_spec`
    """
    eps = entry_points()
    if hasattr(eps, "select"):
        selected = eps.select(group=PROVIDER_GROUP, name=provider_name)  # type: ignore[attr-defined]
    else:
        selected = [ep for ep in eps.get(PROVIDER_GROUP, []) if ep.name == provider_name]  # type: ignore[call-arg]

    for ep in selected:
        obj = ep.load()
        spec = obj() if callable(obj) else obj
        if not isinstance(spec, AppSpec):
            raise TypeError("Provider entry point must return renderflow.contracts.AppSpec")
        return spec

    module = import_module(f"{provider_name}.app_definition")
    if not hasattr(module, "get_app_spec"):
        raise AttributeError(f"{provider_name}.app_definition is missing get_app_spec()")
    spec = module.get_app_spec()
    if not isinstance(spec, AppSpec):
        raise TypeError("get_app_spec() must return renderflow.contracts.AppSpec")
    return spec
