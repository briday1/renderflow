from __future__ import annotations

import pytest

from renderflow import cli
from renderflow.autodefine import _param_specs_from_mapping
from renderflow.contracts import AppSpec, ParamSpec, WorkflowSpec


def _make_provider_app() -> AppSpec:
    return AppSpec(
        app_name="CRSD Inspector",
        initializers=[],
        workflows=[
            WorkflowSpec(
                id="signal_analysis",
                name="Signal Analysis",
                description="Analyze one CRSD file.",
                params=[
                    ParamSpec(
                        key="crsd_file",
                        label="CRSD File",
                        type="text",
                        default="sample.crsd",
                        help="Path to the CRSD file.",
                    ),
                    ParamSpec(
                        key="window_size",
                        label="Window Size",
                        type="number",
                        default=1024,
                        help="FFT window size.",
                    ),
                ],
                run=lambda context, params: {"results": []},
            )
        ],
    )


def test_param_mapping_accepts_description_alias():
    specs = _param_specs_from_mapping(
        {
            "alpha": {
                "type": "number",
                "default": 1,
                "description": "Alpha value",
            }
        }
    )
    assert specs[0].help == "Alpha value"


def test_provider_help_lists_workflows(monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_app_spec", lambda provider: _make_provider_app())
    with pytest.raises(SystemExit):
        cli.provider_main("crsd-inspector", argv=["-h"])
    output = capsys.readouterr().out
    assert "Available workflows:" in output
    assert "- signal_analysis: Signal Analysis" in output


def test_workflow_help_shows_only_workflow_params(monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_app_spec", lambda provider: _make_provider_app())
    with pytest.raises(SystemExit):
        cli.provider_main("crsd-inspector", argv=["signal_analysis", "-h"])
    output = capsys.readouterr().out
    assert "Workflow parameters:" in output
    assert "crsd_file: default='sample.crsd' - Path to the CRSD file." in output
    assert "window_size: default=1024 - FFT window size." in output


def test_workflow_command_forwards_to_execute(monkeypatch):
    forwarded_calls: list[list[str]] = []

    def _fake_main(argv=None):
        forwarded_calls.append(list(argv or []))
        return 0

    monkeypatch.setattr(cli, "main", _fake_main)
    monkeypatch.setattr(
        cli,
        "load_app_spec",
        lambda provider: _make_provider_app(),
    )

    cli.provider_main(
        "crsd-inspector",
        argv=[
            "signal_analysis",
            "--param",
            "crsd_file=data.crsd",
            "--output",
            "none",
        ],
    )
    assert forwarded_calls == [
        [
            "execute",
            "--provider",
            "crsd-inspector",
            "--workflow",
            "signal_analysis",
            "--output",
            "none",
            "--param",
            "crsd_file=data.crsd",
        ]
    ]


def test_main_autodetects_provider_from_program_name(monkeypatch):
    calls: list[tuple[str, list[str], str | None]] = []

    def _fake_provider_main(provider_name, argv=None, prog_name=None, description=None):
        calls.append((provider_name, list(argv or []), prog_name))
        return 0

    monkeypatch.setattr(cli, "provider_main", _fake_provider_main)
    monkeypatch.setattr(cli, "list_provider_names", lambda: ["crsd-inspector"])
    monkeypatch.setattr(cli.sys, "argv", ["crsd-inspector", "list"])

    exit_code = cli.main()

    assert exit_code == 0
    assert calls == [("crsd-inspector", ["list"], "crsd-inspector")]
