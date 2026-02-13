"""Simple plot workflow."""

from __future__ import annotations

import plotly.graph_objects as go

from renderflow.workflow import Workflow

workflow = Workflow(
    name="Series Plot",
    description="Minimal workflow that returns text, table, and one plot.",
)

workflow.params = {
    "base_value": {
        "type": "number",
        "label": "Base Value",
        "default": 10,
        "min": -1000,
        "max": 1000,
        "step": 1,
    },
    "points": {
        "type": "number",
        "label": "Number of Points",
        "default": 6,
        "min": 2,
        "max": 30,
        "step": 1,
    },
    "scale": {
        "type": "number",
        "label": "Scale",
        "default": 1.5,
        "min": 0.1,
        "max": 10.0,
        "step": 0.1,
    },
}


def run_workflow(metadata=None, **kwargs):
    wf = workflow.clear()
    metadata = metadata or {}

    points = int(metadata.get("points", 6))
    scale = float(metadata.get("scale", 1.5))
    base_value = float(metadata.get("base_value", 10))

    x_vals = list(range(points))
    y_vals = [base_value + (idx * scale) for idx in x_vals]

    fig = go.Figure(data=[go.Scatter(x=x_vals, y=y_vals, mode="lines+markers", name="series")])
    fig.update_layout(title="Sample Series", xaxis_title="Index", yaxis_title="Value")

    wf.add_text(f"Generated {points} points with base={base_value} and scale={scale}.")
    wf.add_table(
        "Series Data",
        {
            "x": x_vals,
            "y": y_vals,
        },
    )
    wf.add_plot(fig, title="Series Figure", figure_id="series_figure", save=True)
    return wf.build()
