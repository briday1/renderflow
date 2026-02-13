from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from renderflow import cli
from renderflow.contracts import AppSpec, ParamSpec, WorkflowSpec
from renderflow.results import save_figures


class DummyFigure:
    def write_html(self, path, include_plotlyjs="cdn", full_html=True):
        Path(path).write_text("<html></html>", encoding="utf-8")

    def write_image(self, path, format):
        Path(path).write_bytes(b"image-bytes")

    def to_plotly_json(self):
        return {"data": [], "layout": {}}


def _make_appspec():
    def _run(context, params):
        return {"results": [{"type": "plot", "figure": DummyFigure(), "id": "fig1"}]}

    return AppSpec(
        app_name="dummy",
        initializers=[],
        workflows=[WorkflowSpec(id="wf", name="wf", description="", params=[], run=_run)],
    )


def _fake_report_renderer(results, output_path, title):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"<html><title>{title}</title></html>", encoding="utf-8")
    return path


def test_save_figures_single_format_html(tmp_path):
    results = {"results": [{"type": "plot", "figure": DummyFigure(), "id": "fig1"}]}
    saved = save_figures(results, output_dir=tmp_path, image_format="html")
    assert [path.name for path in saved] == ["fig1.html"]
    assert (tmp_path / "fig1.html").exists()


def test_save_figures_multiple_formats_comma_separated(tmp_path):
    results = {"results": [{"type": "plot", "figure": DummyFigure(), "id": "fig1"}]}
    saved = save_figures(results, output_dir=tmp_path, image_format="html,json")
    assert sorted(path.name for path in saved) == ["fig1.html", "fig1.json"]


def test_execute_combined_report_and_single_figure_format(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "load_app_spec", lambda provider: _make_appspec())
    monkeypatch.setattr(cli, "render_results_to_html", _fake_report_renderer)

    report = tmp_path / "output" / "report.html"
    fig_dir = tmp_path / "output" / "figures"
    args = Namespace(
        provider="dummy",
        workflow="wf",
        init=[],
        param=[],
        html=str(report),
        save_figures_dir=str(fig_dir),
        figure_format=["html"],
        output="none",
    )
    cli._cmd_execute(args)

    assert report.exists()
    assert (fig_dir / "fig1.html").exists()


def test_execute_combined_report_and_multi_figure_formats(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "load_app_spec", lambda provider: _make_appspec())
    monkeypatch.setattr(cli, "render_results_to_html", _fake_report_renderer)

    report = tmp_path / "output" / "report.html"
    fig_dir = tmp_path / "output" / "figures"
    args = Namespace(
        provider="dummy",
        workflow="wf",
        init=[],
        param=[],
        html=str(report),
        save_figures_dir=str(fig_dir),
        figure_format=["html", "json"],
        output="none",
    )
    cli._cmd_execute(args)

    assert report.exists()
    assert (fig_dir / "fig1.html").exists()
    assert (fig_dir / "fig1.json").exists()


def test_cli_invalid_figure_format(monkeypatch):
    monkeypatch.setattr(cli, "load_app_spec", lambda provider: _make_appspec())
    with pytest.raises(SystemExit):
        cli.main(
            [
                "execute",
                "--provider",
                "dummy",
                "--workflow",
                "wf",
                "--save-figures-dir",
                "out",
                "--figure-format",
                "badformat",
                "--output",
                "none",
            ]
        )


def test_execute_invalid_workflow_results_shape(monkeypatch):
    def _run(context, params):
        return {"bad": "shape"}

    app = AppSpec(
        app_name="dummy",
        initializers=[],
        workflows=[WorkflowSpec(id="wf", name="wf", description="", params=[], run=_run)],
    )
    monkeypatch.setattr(cli, "load_app_spec", lambda provider: app)

    with pytest.raises(SystemExit):
        cli.main(["execute", "--provider", "dummy", "--workflow", "wf", "--output", "terminal"])


def test_execute_init_alias_maps_to_workflow_params(monkeypatch):
    def _run(context, params):
        return {"results": [{"type": "text", "content": [str(params.get("x", ""))]}]}

    app = AppSpec(
        app_name="dummy",
        initializers=[],
        workflows=[
            WorkflowSpec(
                id="wf",
                name="wf",
                description="",
                params=[ParamSpec(key="x", label="x", type="text", default="")],
                run=_run,
            )
        ],
    )
    monkeypatch.setattr(cli, "load_app_spec", lambda provider: app)

    # --init is now a deprecated alias for --param
    cli.main(["execute", "--provider", "dummy", "--workflow", "wf", "--init", "x=hello", "--output", "none"])
