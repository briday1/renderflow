"""Shared result rendering/export helpers."""

from __future__ import annotations

import base64
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from plotly.offline import get_plotlyjs_version

VALID_FIGURE_FORMATS = ("html", "json", "png", "jpg", "jpeg", "svg", "pdf")
VALID_RESULT_TYPES = ("text", "table", "plot", "code")


class InvalidFigureFormatError(ValueError):
    """Raised when figure format arguments are invalid."""


class InvalidWorkflowResultsError(TypeError):
    """Raised when a workflow returns an invalid result payload."""


def validate_results_contract(results: dict[str, Any] | None) -> None:
    if results is None:
        raise InvalidWorkflowResultsError("Workflow returned None; expected a dict result payload.")
    if not isinstance(results, dict):
        raise InvalidWorkflowResultsError(
            f"Workflow must return a dict result payload, got {type(results).__name__}."
        )

    has_modern = "results" in results
    has_legacy = any(key in results for key in ("text", "tables", "plots"))
    if not has_modern and not has_legacy and results:
        keys = ", ".join(sorted(results.keys()))
        raise InvalidWorkflowResultsError(
            "Workflow result dict must contain 'results' or legacy keys ('text', 'tables', 'plots'). "
            f"Received keys: {keys}"
        )

    if not has_modern:
        return

    items = results.get("results")
    if items is None:
        return
    if not isinstance(items, list):
        raise InvalidWorkflowResultsError(
            f"'results' must be a list of result items, got {type(items).__name__}."
        )

    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise InvalidWorkflowResultsError(
                f"Result item #{idx} must be a dict, got {type(item).__name__}."
            )
        item_type = item.get("type")
        if item_type not in VALID_RESULT_TYPES:
            raise InvalidWorkflowResultsError(
                f"Result item #{idx} has invalid type {item_type!r}. "
                f"Allowed: {', '.join(VALID_RESULT_TYPES)}"
            )
        if item_type == "plot" and "figure" not in item:
            raise InvalidWorkflowResultsError(
                f"Result item #{idx} has type 'plot' but is missing required key 'figure'."
            )


def normalize_results(results: dict[str, Any] | None) -> list[dict[str, Any]]:
    validate_results_contract(results)
    if not results:
        return []
    if "results" in results:
        return list(results["results"] or [])

    items: list[dict[str, Any]] = []
    for text in results.get("text", []):
        items.append({"type": "text", "content": text})
    for table in results.get("tables", []):
        items.append({"type": "table", "title": table.get("title", "Table"), "data": table.get("data", {})})
    for idx, fig in enumerate(results.get("plots", []), start=1):
        items.append({"type": "plot", "figure": fig, "id": f"figure_{idx}"})
    return items


def _to_builtin_json(value: Any) -> Any:
    # Support Plotly's binary array JSON payloads.
    if isinstance(value, dict) and "dtype" in value and "bdata" in value:
        try:
            arr = np.frombuffer(base64.b64decode(value["bdata"]), dtype=np.dtype(value["dtype"]))
            shape = value.get("shape")
            if shape:
                if isinstance(shape, str):
                    dims = tuple(int(part.strip()) for part in shape.split(",") if part.strip())
                    if dims:
                        arr = arr.reshape(dims)
                elif isinstance(shape, (list, tuple)):
                    arr = arr.reshape(tuple(int(dim) for dim in shape))
            return arr.tolist()
        except Exception:
            pass
    if isinstance(value, dict):
        return {k: _to_builtin_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_builtin_json(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _figure_name(item: dict[str, Any], idx: int) -> str:
    raw = item.get("id") or item.get("title") or f"figure_{idx}"
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(raw))
    return safe.strip("_") or f"figure_{idx}"


def normalize_figure_formats(image_format: str | list[str] | tuple[str, ...] | None) -> list[str]:
    raw_formats: list[str]
    if image_format is None:
        raw_formats = []
    elif isinstance(image_format, str):
        raw_formats = [image_format]
    else:
        raw_formats = [str(fmt) for fmt in image_format]

    normalized: list[str] = []
    for token in raw_formats:
        for fmt in token.split(","):
            value = fmt.strip().lower()
            if not value:
                continue
            if value not in VALID_FIGURE_FORMATS:
                raise InvalidFigureFormatError(
                    f"Invalid figure format '{value}'. Allowed: {', '.join(VALID_FIGURE_FORMATS)}"
                )
            if value not in normalized:
                normalized.append(value)

    if not normalized:
        return ["html"]
    return normalized


def save_figures(
    results: dict[str, Any] | None,
    output_dir: str | Path,
    image_format: str | list[str] | tuple[str, ...] | None = "html",
) -> list[Path]:
    items = normalize_results(results)
    formats = normalize_figure_formats(image_format)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    saved: list[Path] = []
    fig_index = 0
    for item in items:
        if item.get("type") != "plot":
            continue
        if item.get("save", True) is False:
            continue
        figure = item.get("figure")
        if figure is None:
            continue
        fig_index += 1
        name = _figure_name(item, fig_index)
        for fmt in formats:
            if fmt == "json":
                path = out / f"{name}.json"
                payload = _to_builtin_json(figure.to_plotly_json())
                path.write_text(json.dumps(payload), encoding="utf-8")
            elif fmt in {"png", "jpg", "jpeg", "svg", "pdf"}:
                ext = "jpg" if fmt == "jpeg" else fmt
                path = out / f"{name}.{ext}"
                figure.write_image(str(path), format=ext)
            else:
                path = out / f"{name}.html"
                figure.write_html(str(path), include_plotlyjs="cdn", full_html=True)
            saved.append(path)
    return saved


def render_results_to_html(
    results: dict[str, Any] | None,
    output_path: str | Path,
    title: str = "Workflow Report",
) -> Path:
    items = normalize_results(results)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    html_parts = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        f"    <title>{html.escape(title)}</title>",
        "    <meta charset='utf-8'>",
        f"    <script src='https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js'></script>",
        "    <style>",
        "        body { font-family: system-ui, sans-serif; max-width: 1200px; margin: 0 auto; padding: 1.5rem; }",
        "        .section { margin: 1rem 0; padding: 1rem; border: 1px solid #ddd; border-radius: 6px; }",
        "        .section h2 { margin-top: 0; }",
        "        table { width: 100%; border-collapse: collapse; }",
        "        th, td { border-bottom: 1px solid #ddd; text-align: left; padding: 0.45rem; }",
        "        pre { background: #f6f8fa; padding: 0.75rem; border-radius: 6px; overflow-x: auto; }",
        "    </style>",
        "</head>",
        "<body>",
        f"    <h1>{html.escape(title)}</h1>",
        f"    <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
    ]

    plot_counter = 0
    for item in items:
        item_type = item.get("type")
        if item_type == "text":
            html_parts.append("    <div class='section'>")
            content = item.get("content", [])
            if isinstance(content, str):
                content = [content]
            for line in content:
                html_parts.append(f"        <p>{line}</p>")
            html_parts.append("    </div>")
        elif item_type == "table":
            html_parts.append("    <div class='section'>")
            html_parts.append(f"        <h2>{html.escape(str(item.get('title', 'Table')))}</h2>")
            data = item.get("data", {}) or {}
            headers = list(data.keys()) if isinstance(data, dict) else []
            html_parts.append("        <table>")
            if headers:
                html_parts.append("            <tr>")
                for header in headers:
                    html_parts.append(f"                <th>{html.escape(str(header))}</th>")
                html_parts.append("            </tr>")
                rows = len(data[headers[0]]) if headers else 0
                for row_idx in range(rows):
                    html_parts.append("            <tr>")
                    for header in headers:
                        value = data[header][row_idx]
                        html_parts.append(f"                <td>{html.escape(str(value))}</td>")
                    html_parts.append("            </tr>")
            html_parts.append("        </table>")
            html_parts.append("    </div>")
        elif item_type == "code":
            language = item.get("language", "text")
            html_parts.append("    <div class='section'>")
            html_parts.append(f"        <h2>Code ({html.escape(str(language))})</h2>")
            content = item.get("content", [])
            if isinstance(content, str):
                content = [content]
            html_parts.append(f"        <pre>{html.escape(chr(10).join(str(c) for c in content))}</pre>")
            html_parts.append("    </div>")
        elif item_type == "plot":
            figure = item.get("figure")
            if figure is None:
                continue
            plot_counter += 1
            div_id = f"plot-{plot_counter}"
            payload = _to_builtin_json(figure.to_plotly_json())
            plot_json = json.dumps(payload)
            html_parts.append("    <div class='section'>")
            if item.get("title"):
                html_parts.append(f"        <h2>{html.escape(str(item['title']))}</h2>")
            html_parts.append(f"        <div id='{div_id}'></div>")
            html_parts.append("        <script>")
            html_parts.append(f"            var plotData = {plot_json};")
            html_parts.append(
                f"            Plotly.newPlot('{div_id}', plotData.data, plotData.layout, {{responsive: true}});"
            )
            html_parts.append("        </script>")
            html_parts.append("    </div>")

    html_parts.extend(["</body>", "</html>"])
    output_path.write_text("\n".join(html_parts), encoding="utf-8")
    return output_path
