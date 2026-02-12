"""CLI for running generic provider-backed renderflow apps."""

from __future__ import annotations

import argparse
from typing import Sequence

from renderflow.discovery import list_provider_names
from renderflow.streamlit_renderer import launch_streamlit_renderer


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Renderflow workflow app runner")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="Run Streamlit for a provider")
    run.add_argument("--provider", required=True, help="Provider name registered in renderflow.providers")

    sub.add_parser("list-providers", help="List installed providers")

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


def main(argv: Sequence[str] | None = None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "list-providers":
        for name in list_provider_names():
            print(name)
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

    launch_streamlit_renderer(provider)
