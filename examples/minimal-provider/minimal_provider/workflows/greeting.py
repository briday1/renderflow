"""Simple text/table workflow."""

from __future__ import annotations

from renderflow.workflow import Workflow

workflow = Workflow(
    name="Greeting",
    description="Minimal text + table output example.",
)

workflow.params = {
    "name": {
        "type": "text",
        "label": "Name",
        "default": "World",
    },
    "excited": {
        "type": "checkbox",
        "label": "Excited",
        "default": False,
        "help": "Add exclamation marks to the greeting.",
    },
    "repeat": {
        "type": "number",
        "label": "Repeat Count",
        "default": 2,
        "min": 1,
        "max": 10,
        "step": 1,
    },
}


def run_workflow(metadata=None, **kwargs):
    wf = workflow.clear()
    metadata = metadata or {}

    name = str(metadata.get("name", "World"))
    excited = bool(metadata.get("excited", False))
    repeat = int(metadata.get("repeat", 2))

    suffix = "!" if excited else "."
    lines = [f"Hello, {name}{suffix}" for _ in range(max(1, repeat))]
    wf.add_text(lines)
    wf.add_table(
        "Input Summary",
        {
            "key": ["name", "excited", "repeat"],
            "value": [name, excited, repeat],
        },
    )
    return wf.build()
