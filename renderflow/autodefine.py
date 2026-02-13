"""Automatic provider definition from workflow modules."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from dataclasses import asdict, is_dataclass
from typing import Any, Callable

from renderflow.contracts import AppSpec, InitializerSpec, ParamSpec, WorkflowSpec


def _param_specs_from_mapping(params: dict[str, Any] | None) -> list[ParamSpec]:
    specs: list[ParamSpec] = []
    for key, cfg in (params or {}).items():
        if isinstance(cfg, ParamSpec):
            specs.append(cfg)
            continue
        cfg = cfg or {}
        specs.append(
            ParamSpec(
                key=key,
                label=cfg.get("label", key),
                type=cfg.get("type", "text"),
                default=cfg.get("default"),
                min=cfg.get("min"),
                max=cfg.get("max"),
                step=cfg.get("step"),
                options=cfg.get("options", []),
                help=cfg.get("help", ""),
            )
        )
    return specs


def _coerce_param_specs(value: Any) -> list[ParamSpec]:
    if value is None:
        return []
    if isinstance(value, dict):
        return _param_specs_from_mapping(value)
    specs: list[ParamSpec] = []
    for item in value:
        if isinstance(item, ParamSpec):
            specs.append(item)
        elif isinstance(item, dict):
            specs.append(ParamSpec(**item))
    return specs


def _infer_params_from_signature(func: Callable[..., Any]) -> list[ParamSpec]:
    reserved = {"signal_data", "metadata", "context", "kwargs", "args", "self"}
    specs: list[ParamSpec] = []
    for name, param in inspect.signature(func).parameters.items():
        if name in reserved or param.kind in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}:
            continue
        default = None if param.default is inspect.Parameter.empty else param.default
        param_type = "text"
        if isinstance(default, bool):
            param_type = "checkbox"
        elif isinstance(default, (int, float)):
            param_type = "number"
        specs.append(ParamSpec(key=name, label=name.replace("_", " ").title(), type=param_type, default=default))
    return specs


def _invoke_workflow(func: Callable[..., dict[str, Any]], context: dict[str, Any], params: dict[str, Any]):
    if not isinstance(context, dict):
        raise TypeError(f"Workflow context must be a dict, got {type(context).__name__}")
    if not isinstance(params, dict):
        raise TypeError(f"Workflow params must be a dict, got {type(params).__name__}")

    sig = inspect.signature(func)
    kwargs: dict[str, Any] = {}
    merged_metadata: dict[str, Any] = {}
    base_metadata = context.get("metadata")
    if isinstance(base_metadata, dict):
        merged_metadata.update(base_metadata)
    for key, value in context.items():
        if key != "metadata":
            merged_metadata[key] = value
    merged_metadata.update(params)

    if "signal_data" in sig.parameters and "signal_data" in context:
        kwargs["signal_data"] = context["signal_data"]
    if "metadata" in sig.parameters:
        kwargs["metadata"] = merged_metadata
    if "context" in sig.parameters:
        kwargs["context"] = context

    for key, value in params.items():
        if key in sig.parameters and key not in kwargs:
            kwargs[key] = value

    result = func(**kwargs)
    if not isinstance(result, dict):
        raise TypeError(
            f"Workflow '{func.__module__}.{func.__name__}' must return a dict, got {type(result).__name__}"
        )
    return result


def _discover_workflows(provider_name: str, package_name: str) -> list[WorkflowSpec]:
    pkg = importlib.import_module(package_name)
    specs: list[WorkflowSpec] = []
    for module_info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda m: m.name):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package_name}.{module_info.name}")
        run_workflow = getattr(module, "run_workflow", None)
        if not callable(run_workflow):
            continue

        workflow_obj = getattr(module, "workflow", None)
        wf_id = module_info.name
        wf_name = getattr(workflow_obj, "name", None) or getattr(module, "WORKFLOW_NAME", wf_id)
        wf_desc = getattr(workflow_obj, "description", None) or getattr(module, "WORKFLOW_DESCRIPTION", "")
        raw_params = getattr(workflow_obj, "params", None)
        if raw_params is None:
            raw_params = getattr(module, "PARAMS", None)
        if raw_params is None:
            param_specs = _infer_params_from_signature(run_workflow)
        else:
            param_specs = _coerce_param_specs(raw_params)

        def _make_run(func):
            def _run(context: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
                return _invoke_workflow(func, context, params)

            return _run

        specs.append(
            WorkflowSpec(
                id=wf_id,
                name=wf_name,
                description=wf_desc,
                params=param_specs,
                run=_make_run(run_workflow),
            )
        )
    if not specs:
        raise RuntimeError(f"No workflow modules with run_workflow() found under {package_name}")
    return specs


def _dict_to_app_spec(raw: dict[str, Any]) -> AppSpec:
    if {"app_name", "initializers", "workflows"} - set(raw.keys()):
        raise TypeError("Dictionary provider spec missing one of: app_name, initializers, workflows")
    initializers: list[InitializerSpec] = []
    for item in raw["initializers"]:
        if isinstance(item, InitializerSpec):
            initializers.append(item)
        else:
            initializers.append(
                InitializerSpec(
                    id=item["id"],
                    name=item["name"],
                    description=item.get("description", ""),
                    params=_coerce_param_specs(item.get("params")),
                    initialize=item["initialize"],
                )
            )

    workflows: list[WorkflowSpec] = []
    for item in raw["workflows"]:
        if isinstance(item, WorkflowSpec):
            workflows.append(item)
        else:
            workflows.append(
                WorkflowSpec(
                    id=item["id"],
                    name=item["name"],
                    description=item.get("description", ""),
                    params=_coerce_param_specs(item.get("params")),
                    run=item["run"],
                )
            )
    return AppSpec(app_name=raw["app_name"], initializers=initializers, workflows=workflows)


def coerce_to_app_spec(obj: Any, provider_name: str | None = None) -> AppSpec:
    if callable(obj) and not isinstance(obj, type):
        obj = obj()
    if isinstance(obj, AppSpec):
        return obj
    if is_dataclass(obj):
        return _dict_to_app_spec(asdict(obj))
    if isinstance(obj, dict):
        return _dict_to_app_spec(obj)
    raise TypeError(f"Unsupported provider definition object for {provider_name or 'provider'}: {type(obj)}")


def auto_build_app_spec(provider_name: str) -> AppSpec:
    provider_pkg = importlib.import_module(provider_name)

    cfg_module = None
    try:
        cfg_module = importlib.import_module(f"{provider_name}.renderflow")
    except ModuleNotFoundError:
        cfg_module = None

    app_name = getattr(cfg_module, "APP_NAME", None) or getattr(provider_pkg, "APP_NAME", None) or provider_name
    workflow_package = (
        getattr(cfg_module, "WORKFLOWS_PACKAGE", None) or getattr(provider_pkg, "WORKFLOWS_PACKAGE", None)
    )
    if not workflow_package:
        workflow_package = f"{provider_name}.workflows"

    initializers: list[InitializerSpec] = []
    init_func = getattr(cfg_module, "initialize", None) or getattr(provider_pkg, "initialize", None)
    init_params = getattr(cfg_module, "INIT_PARAMS", None) or getattr(provider_pkg, "INIT_PARAMS", None)
    if callable(init_func):
        initializers.append(
            InitializerSpec(
                id="default_initializer",
                name="Initialization",
                description="Provider initialization context",
                params=_coerce_param_specs(init_params),
                initialize=init_func,
            )
        )

    return AppSpec(
        app_name=app_name,
        initializers=initializers,
        workflows=_discover_workflows(provider_name, workflow_package),
    )
