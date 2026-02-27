"""Contracts used by workflow providers and generic renderers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ParamSpec:
    """Declarative parameter definition for init/workflow UIs."""

    key: str
    label: str
    type: str = "text"
    default: Any = None
    min: float | None = None
    max: float | None = None
    step: float | None = None
    # `options` may be:
    # - list[dict]: static dropdown options
    # - callable(values, spec) -> list[dict] | list[Any]: dynamic options
    options: Any = field(default_factory=list)
    help: str = ""


@dataclass
class InitializerSpec:
    """Definition of a context initialization API for a provider."""

    id: str
    name: str
    description: str
    params: list[ParamSpec]
    initialize: Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class WorkflowSpec:
    """Definition of a workflow with parameters and execution function."""

    id: str
    name: str
    description: str
    params: list[ParamSpec]
    run: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


@dataclass
class AppSpec:
    """Full provider definition consumed by generic renderers."""

    app_name: str
    initializers: list[InitializerSpec]
    workflows: list[WorkflowSpec]
