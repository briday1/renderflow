"""Generic Streamlit renderer for AppSpec providers."""

from __future__ import annotations

import html
import os
import sys
import time
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from renderflow.discovery import load_app_spec
from renderflow.results import InvalidWorkflowResultsError, normalize_results, save_figures


def _render_param_inputs(prefix: str, params) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for spec in params:
        key = f"{prefix}_{spec.key}"
        if spec.type == "dropdown":
            options = [opt.get("value") for opt in spec.options]
            labels_map = {opt.get("value"): opt.get("label", opt.get("value")) for opt in spec.options}
            default_idx = options.index(spec.default) if spec.default in options else 0
            val = st.sidebar.selectbox(
                spec.label,
                options=options,
                index=default_idx if options else 0,
                format_func=lambda x: labels_map.get(x, x),
                key=key,
                help=spec.help or None,
            )
        elif spec.type == "number":
            val = st.sidebar.number_input(
                spec.label,
                value=float(spec.default) if spec.default is not None else 0.0,
                min_value=float(spec.min) if spec.min is not None else None,
                max_value=float(spec.max) if spec.max is not None else None,
                step=float(spec.step) if spec.step is not None else None,
                key=key,
                help=spec.help or None,
            )
        elif spec.type == "checkbox":
            val = st.sidebar.checkbox(
                spec.label,
                value=bool(spec.default) if spec.default is not None else False,
                key=key,
                help=spec.help or None,
            )
        else:
            val = st.sidebar.text_input(
                spec.label,
                value=str(spec.default) if spec.default is not None else "",
                key=key,
                help=spec.help or None,
            )
        values[spec.key] = val
    return values


def _render_results(results: dict[str, Any]):
    try:
        items = normalize_results(results)
    except InvalidWorkflowResultsError as exc:
        st.error(f"Invalid workflow result payload: {exc}")
        return
    if not items:
        st.info("No results returned.")
        return

    for item in items:
        if item["type"] == "text":
            for text in item.get("content", []):
                st.markdown(text)
        elif item["type"] == "table":
            st.markdown(f"**{item.get('title', 'Table')}**")
            data = item.get("data", {})
            if isinstance(data, dict):
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            else:
                st.dataframe(data, use_container_width=True)
        elif item["type"] == "plot":
            st.plotly_chart(item.get("figure"), use_container_width=True)
        elif item["type"] == "code":
            code_lines = item.get("content", [])
            if isinstance(code_lines, str):
                code_lines = [code_lines]
            st.code("\n".join(str(line) for line in code_lines), language=item.get("language", "text"))


def _render_figure_export_ui(results: dict[str, Any]):
    st.sidebar.markdown("---")
    st.sidebar.subheader("Figure Export")
    export_enabled = st.sidebar.checkbox("Enable Figure Export", value=False)
    if not export_enabled:
        return
    output_dir = st.sidebar.text_input("Output Directory", value="output/figures")
    fmt = st.sidebar.selectbox("Figure Format", options=["html", "json", "png", "svg"], index=0)
    if st.sidebar.button("Save Figures", use_container_width=True):
        try:
            saved = save_figures(results, output_dir=output_dir, image_format=fmt)
            if saved:
                st.sidebar.success(f"Saved {len(saved)} figure(s) to {output_dir}")
            else:
                st.sidebar.info("No figures to save.")
        except Exception as exc:
            st.sidebar.error(f"Figure export failed: {exc}")


def _make_progress_callback(status_panel):
    with status_panel:
        progress_window = st.empty()
    completed_entries = []
    progress_state = {"active_entry": None}
    step_start_times = {}

    def render_progress_window():
        active_entry = progress_state["active_entry"]
        lines = completed_entries + ([active_entry] if active_entry else [])
        # Keep latest updates visible without relying on iframe auto-scroll behavior.
        lines = list(reversed(lines))
        html_lines = []
        for line in lines:
            if line.startswith("__RUNNING__::"):
                running_text = html.escape(line.replace("__RUNNING__::", "", 1))
                html_lines.append("<li><span class='wr-live-spinner'></span>" f"{running_text}</li>")
            else:
                html_lines.append(f"<li>{html.escape(line)}</li>")
        html_payload = (
            "<style>"
            "body{margin:0;padding:0;color:#111;background:transparent;}"
            "@media (prefers-color-scheme: dark){body{color:#f2f5fa;}}"
            ".wr-live-scroll{height:12rem;max-height:12rem;overflow-y:auto;padding-right:0.3rem;"
            "color:inherit;background:transparent;}"
            ".wr-live-list{margin:0.25rem 0 0.25rem 1.1rem;padding:0;}"
            ".wr-live-list li{margin:0.2rem 0;list-style:disc;color:inherit;}"
            ".wr-live-spinner{display:inline-block;width:0.85rem;height:0.85rem;"
            "margin-right:0.45rem;border:2px solid currentColor;border-top-color:transparent;"
            "border-radius:50%;vertical-align:-0.1rem;animation:wrspin 0.8s linear infinite;}"
            "@keyframes wrspin{to{transform:rotate(360deg);}}"
            "</style>"
            "<div style='font-size:0.8rem;opacity:0.8;margin:0 0 0.2rem 0;'>Latest first</div>"
            f"<div id='wr-live-scroll' class='wr-live-scroll'><ul class='wr-live-list'>{''.join(html_lines)}</ul></div>"
        )
        with progress_window.container():
            components.html(html_payload, height=210, scrolling=False)

    def progress_callback(step, status, detail=""):
        line = f"{step}"
        if detail:
            line += f" - {detail}"
        if status == "running":
            step_start_times[step] = time.perf_counter()
            progress_state["active_entry"] = f"__RUNNING__::{line}"
            status_panel.update(label=f"Executing: {step}...", state="running", expanded=True)
        elif status == "done":
            started = step_start_times.get(step)
            if started is not None:
                elapsed = time.perf_counter() - started
                completed_entries.append(f"OK {line} ({elapsed:.3f}s)")
            else:
                completed_entries.append(f"OK {line}")
            progress_state["active_entry"] = None
        elif status == "failed":
            completed_entries.append(f"FAILED {line}")
            progress_state["active_entry"] = None
        render_progress_window()

    return progress_callback


def run_renderer(provider: str):
    st.set_page_config(page_title="Workflow Renderer", layout="wide")
    st.title("Workflow Renderer")
    st.caption(f"Provider: `{provider}`")

    try:
        app_spec = load_app_spec(provider)
    except Exception as exc:
        st.error(f"Failed to load app definition for provider {provider}: {exc}")
        st.stop()

    st.sidebar.header(app_spec.app_name)

    if "last_results" not in st.session_state:
        st.session_state.last_results = None

    context: dict[str, Any] = {}

    if not app_spec.workflows:
        st.warning("No workflows discovered.")
        return

    st.sidebar.markdown("---")
    workflow_ids = [w.id for w in app_spec.workflows]
    workflow_map = {w.id: w for w in app_spec.workflows}
    if len(workflow_ids) > 1:
        selected_id = st.sidebar.selectbox(
            "Workflow",
            options=workflow_ids,
            format_func=lambda x: workflow_map[x].name,
        )
    else:
        selected_id = workflow_ids[0]
        st.sidebar.subheader(workflow_map[selected_id].name)
    wf = workflow_map[selected_id]
    if wf.description:
        st.sidebar.caption(wf.description)

    st.sidebar.subheader("Workflow Parameters")
    wf_values = _render_param_inputs(f"wf_{wf.id}", wf.params)
    run_clicked = st.sidebar.button("Execute Workflow", use_container_width=True)

    if run_clicked:
        status_panel = st.status("Executing workflow...", state="running", expanded=True)
        callback = _make_progress_callback(status_panel)
        wf_values["_progress_callback"] = callback
        try:
            st.session_state.last_results = wf.run(context, wf_values)
            status_panel.update(label="Workflow complete", state="complete")
        except Exception as exc:
            status_panel.update(label=f"Workflow failed: {exc}", state="error")
            st.session_state.last_results = {
                "results": [{"type": "text", "content": [f"FAILED Workflow failed: {exc}"]}]
            }

    if st.session_state.last_results is not None:
        _render_results(st.session_state.last_results)
        _render_figure_export_ui(st.session_state.last_results)
    else:
        if len(workflow_ids) > 1:
            st.info("Choose a workflow and click Execute Workflow.")
        else:
            st.info("Click Execute Workflow.")


def launch_streamlit_renderer(provider: str):
    """Launch the generic Streamlit renderer for a specific provider."""
    os.environ["RENDERFLOW_PROVIDER"] = provider
    import streamlit.web.cli as stcli

    sys.argv = ["streamlit", "run", __file__]
    sys.exit(stcli.main())


if __name__ == "__main__":
    run_renderer(os.environ.get("RENDERFLOW_PROVIDER", ""))
