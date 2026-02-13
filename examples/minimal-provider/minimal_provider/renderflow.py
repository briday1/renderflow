"""Provider contract for the minimal example package."""

from __future__ import annotations

from renderflow.autodefine import auto_build_app_spec

APP_NAME = "Minimal Provider"
WORKFLOWS_PACKAGE = "minimal_provider.workflows"


def get_app_spec():
    return auto_build_app_spec("minimal_provider")
