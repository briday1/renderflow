"""CLI for running generic provider-backed renderflow apps."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from renderflow.discovery import list_provider_names, load_app_spec
from renderflow.results import (
    InvalidFigureFormatError,
    InvalidWorkflowResultsError,
    VALID_FIGURE_FORMATS,
    normalize_figure_formats,
    normalize_results,
    render_results_to_html,
    save_figures,
)


def _parse_kv(values: list[str] | None) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in values or []:
        if "=" not in item:
            raise ValueError(f"Expected key=value argument, got: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid key in argument: {item}")
        parsed[key] = value
    return parsed


def _cast_value(raw: str, spec_type: str) -> Any:
    if spec_type == "checkbox":
        return raw.strip().lower() in {"1", "true", "yes", "y", "on"}
    if spec_type == "number":
        text = raw.strip()
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            return int(text)
        return float(text)
    return raw


def _cast_param_map(raw: dict[str, str], specs) -> dict[str, Any]:
    typed: dict[str, Any] = {}
    by_key = {spec.key: spec for spec in specs}
    for key, value in raw.items():
        spec = by_key.get(key)
        if spec is None:
            typed[key] = value
        else:
            typed[key] = _cast_value(value, spec.type)
    for spec in specs:
        if spec.key not in typed and spec.default is not None:
            typed[spec.key] = spec.default
    return typed


def _print_results_terminal(results: dict[str, Any]):
    items = normalize_results(results)
    if not items:
        print("No results returned.")
        return
    for idx, item in enumerate(items, start=1):
        item_type = item.get("type")
        if item_type == "text":
            content = item.get("content", [])
            if isinstance(content, str):
                content = [content]
            for line in content:
                print(line)
        elif item_type == "table":
            title = item.get("title", f"Table {idx}")
            print(f"\n{title}")
            print("-" * len(str(title)))
            data = item.get("data", {})
            if isinstance(data, dict):
                print(pd.DataFrame(data).to_string(index=False))
            else:
                print(pd.DataFrame(data).to_string(index=False))
        elif item_type == "plot":
            name = item.get("id") or item.get("title") or f"figure_{idx}"
            print(f"[plot] {name}")
        elif item_type == "code":
            language = item.get("language", "text")
            print(f"\n[code:{language}]")
            content = item.get("content", [])
            if isinstance(content, str):
                content = [content]
            print("\n".join(str(line) for line in content))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Renderflow workflow app runner")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="Run Streamlit for a provider")
    run.add_argument("--provider", required=True, help="Provider name registered in renderflow.providers")

    sub.add_parser("list-providers", help="List installed providers")

    list_workflows = sub.add_parser("list-workflows", help="List workflows for a provider")
    list_workflows.add_argument("--provider", required=True)

    show_params = sub.add_parser("show-params", help="Show initializer/workflow parameters")
    show_params.add_argument("--provider", required=True)
    show_params.add_argument("--workflow", required=True)

    execute = sub.add_parser("execute", help="Execute one workflow from CLI")
    execute.add_argument("--provider", required=True)
    execute.add_argument("--workflow", required=True)
    execute.add_argument(
        "--init",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Deprecated alias for --param (repeatable).",
    )
    execute.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Workflow parameter value (repeatable).",
    )
    execute.add_argument("--html", help="Optional output path for one combined workflow HTML report.")
    execute.add_argument(
        "--save-figures-dir",
        help="Optional directory to save individual figure files.",
    )
    execute.add_argument(
        "--figure-format",
        action="append",
        default=None,
        metavar="FORMAT[,FORMAT]",
        help=(
            "Figure format for --save-figures-dir. Repeatable and comma-separated values are supported. "
            f"Allowed: {', '.join(VALID_FIGURE_FORMATS)}. Default: html."
        ),
    )
    execute.add_argument(
        "--output",
        choices=["terminal", "json", "none"],
        default="terminal",
        help="How to emit results to stdout.",
    )

    parser.add_argument(
        "--provider",
        help="Compatibility flag: when provided without subcommand, behaves like 'run --provider ...'",
    )
    parser.add_argument(
        "--target-package",
        dest="target_package",
        help="Backward compatibility alias for --provider",
    )
    return parser


def _print_specs(specs):
    for spec in specs:
        default = f" default={spec.default!r}" if spec.default is not None else ""
        help_text = f" - {spec.help}" if spec.help else ""
        print(f"- {spec.key} ({spec.type}){default}{help_text}")


def _cmd_list_workflows(provider: str):
    app = load_app_spec(provider)
    for wf in app.workflows:
        print(f"{wf.id}\t{wf.name}")


def _cmd_show_params(provider: str, workflow_id: str):
    app = load_app_spec(provider)
    wf_map = {wf.id: wf for wf in app.workflows}
    if workflow_id not in wf_map:
        raise ValueError(f"Unknown workflow '{workflow_id}'. Available: {', '.join(sorted(wf_map.keys()))}")
    wf = wf_map[workflow_id]
    print(f"Provider: {provider}")
    print(f"Workflow: {wf.id} ({wf.name})")
    print("\nWorkflow parameters:")
    _print_specs(wf.params)


def _cmd_execute(args):
    app = load_app_spec(args.provider)
    wf_map = {wf.id: wf for wf in app.workflows}
    if args.workflow not in wf_map:
        raise ValueError(f"Unknown workflow '{args.workflow}'. Available: {', '.join(sorted(wf_map.keys()))}")
    wf = wf_map[args.workflow]

    raw_init = _parse_kv(args.init)
    raw_wf = _parse_kv(args.param)
    merged_raw = dict(raw_init)
    merged_raw.update(raw_wf)

    context = {}
    wf_values = _cast_param_map(merged_raw, wf.params)
    results = wf.run(context, wf_values)

    if args.html:
        html_path = render_results_to_html(
            results,
            output_path=args.html,
            title=f"{app.app_name} - {wf.name}",
        )
        print(f"HTML report: {html_path}")

    if args.save_figures_dir:
        formats = normalize_figure_formats(args.figure_format)
        saved = save_figures(results, output_dir=args.save_figures_dir, image_format=formats)
        print(f"Saved {len(saved)} figure file(s) to {args.save_figures_dir}")

    if args.output == "terminal":
        _print_results_terminal(results)
    elif args.output == "json":
        print(json.dumps(results, default=str))


def _resolve_provider_from_prog(prog_name: str) -> str | None:
    normalized = prog_name.strip()
    if not normalized:
        return None
    canonical = normalized.lower().replace("_", "-")
    providers = list_provider_names()
    matches = [name for name in providers if name.lower().replace("_", "-") == canonical]
    if len(matches) == 1:
        return matches[0]
    return None


def main(argv: Sequence[str] | None = None):
    if argv is None:
        prog_stem = Path(sys.argv[0]).stem
        reserved_prog_names = {"renderflow", "workflow-renderer-streamlit"}
        provider_from_prog = _resolve_provider_from_prog(prog_stem)
        if provider_from_prog and prog_stem not in reserved_prog_names:
            return provider_main(
                provider_name=provider_from_prog,
                argv=sys.argv[1:],
                prog_name=prog_stem,
                description=f"{provider_from_prog} workflow CLI",
            )

    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "list-providers":
            for name in list_provider_names():
                print(name)
            return
        if args.command == "list-workflows":
            _cmd_list_workflows(args.provider)
            return
        if args.command == "show-params":
            _cmd_show_params(args.provider, args.workflow)
            return
        if args.command == "execute":
            _cmd_execute(args)
            return

        provider = None
        if args.command == "run":
            provider = args.provider
        elif args.provider:
            provider = args.provider
        elif args.target_package:
            provider = args.target_package

        if not provider:
            parser.error("a provider is required, use: renderflow run --provider <name>")

        from renderflow.streamlit_renderer import launch_streamlit_renderer

        launch_streamlit_renderer(provider)
    except (InvalidFigureFormatError, InvalidWorkflowResultsError) as exc:
        parser.error(str(exc))


def _format_param_help_line(spec) -> str:
    details: list[str] = [spec.type]
    if spec.default is not None:
        details.append(f"default={spec.default!r}")
    if spec.help:
        details.append(spec.help)
    return f"  - {spec.key}: " + " | ".join(details)


def _build_provider_help_epilog(provider_name: str) -> str:
    try:
        app = load_app_spec(provider_name)
    except Exception:
        return ""

    lines: list[str] = ["", "Workflows and parameters:"]
    for wf in app.workflows:
        lines.append(f"- {wf.id}: {wf.name}")
        if wf.description:
            lines.append(f"  {wf.description}")
        if not wf.params:
            lines.append("  (no parameters)")
            continue
        for spec in wf.params:
            lines.append(_format_param_help_line(spec))
    return "\n".join(lines)


def _build_provider_parser(prog: str, description: str, provider_name: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description=description,
        epilog=_build_provider_help_epilog(provider_name),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List available workflows")
    sub.add_parser("run", help="Launch Streamlit app")

    show_params = sub.add_parser("show-params", help="Show workflow parameter definitions")
    show_params.add_argument("--workflow", required=True, help="Workflow id")

    execute = sub.add_parser("execute", help="Execute a workflow")
    execute.add_argument("--workflow", required=True, help="Workflow id")
    execute.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Workflow parameter value (repeatable).",
    )
    execute.add_argument(
        "--init",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Deprecated alias for --param (repeatable).",
    )
    execute.add_argument("--html", help="Optional output path for one combined workflow HTML report.")
    execute.add_argument(
        "--save-figures-dir",
        help="Optional directory to save individual figure files.",
    )
    execute.add_argument(
        "--figure-format",
        action="append",
        default=None,
        metavar="FORMAT[,FORMAT]",
        help="Figure format for --save-figures-dir (repeatable).",
    )
    execute.add_argument(
        "--output",
        choices=["terminal", "json", "none"],
        default="terminal",
        help="How to emit results to stdout.",
    )
    return parser


def provider_main(
    provider_name: str,
    argv: Sequence[str] | None = None,
    prog_name: str | None = None,
    description: str | None = None,
):
    """
    Provider-scoped CLI wrapper.

    This keeps provider packages minimal while renderflow owns CLI behavior.
    """
    prog = prog_name or provider_name
    desc = description or f"{provider_name} CLI"
    parser = _build_provider_parser(prog=prog, description=desc, provider_name=provider_name)
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    parsed = parser.parse_args(raw_args)
    if not parsed.command:
        parser.print_help()
        return 0

    if parsed.command == "list":
        return main(["list-workflows", "--provider", provider_name])
    if parsed.command == "run":
        return main(["run", "--provider", provider_name])
    if parsed.command == "show-params":
        return main(
            [
                "show-params",
                "--provider",
                provider_name,
                "--workflow",
                parsed.workflow,
            ]
        )

    forwarded: list[str] = [
        "execute",
        "--provider",
        provider_name,
        "--workflow",
        parsed.workflow,
        "--output",
        parsed.output,
    ]
    for value in parsed.init or []:
        forwarded.extend(["--init", value])
    for value in parsed.param or []:
        forwarded.extend(["--param", value])
    if parsed.html:
        forwarded.extend(["--html", parsed.html])
    if parsed.save_figures_dir:
        forwarded.extend(["--save-figures-dir", parsed.save_figures_dir])
    for value in parsed.figure_format or []:
        forwarded.extend(["--figure-format", value])
    return main(forwarded)
