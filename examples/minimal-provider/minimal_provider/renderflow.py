"""Provider contract for the minimal example package."""

from __future__ import annotations

from renderflow.autodefine import auto_build_app_spec

APP_NAME = "Minimal Provider"
WORKFLOWS_PACKAGE = "minimal_provider.workflows"

INIT_PARAMS = [
    {
        "key": "name",
        "label": "Name",
        "type": "text",
        "default": "World",
        "help": "Name used by workflows.",
    },
    {
        "key": "base_value",
        "label": "Base Value",
        "type": "number",
        "default": 10,
        "help": "Default numeric value for workflows.",
    },
]


def initialize(params):
    return {
        "name": params.get("name", "World"),
        "base_value": params.get("base_value", 10),
    }


def get_app_spec():
    return auto_build_app_spec("minimal_provider")
