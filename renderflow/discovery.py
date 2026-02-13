"""Discovery helpers for provider plugins."""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import entry_points

from renderflow.autodefine import auto_build_app_spec, coerce_to_app_spec
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
        return coerce_to_app_spec(obj, provider_name=provider_name)

    try:
        module = import_module(f"{provider_name}.app_definition")
        if hasattr(module, "get_app_spec"):
            return coerce_to_app_spec(module.get_app_spec, provider_name=provider_name)
        raise AttributeError(f"{provider_name}.app_definition is missing get_app_spec()")
    except ModuleNotFoundError as exc:
        if exc.name != f"{provider_name}.app_definition":
            raise

    return auto_build_app_spec(provider_name)
