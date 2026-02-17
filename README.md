# renderflow

Workflow runtime and rendering API for:
- Streamlit UI
- CLI execution
- HTML report export
- Individual figure export

## Core Idea

`renderflow` owns the interface contract and rendering behavior.
Provider packages should mostly define workflows (`run_workflow` + params), not custom UI/CLI plumbing.

## Demo App

Live Streamlit demo:

https://demo-for-renderflow.streamlit.app/

## CLI

List installed providers:

```bash
renderflow list-providers
```

List provider workflows:

```bash
renderflow list-workflows --provider crsd-inspector
```

Show interpreted workflow parameters:

```bash
renderflow show-params --provider crsd-inspector --workflow signal_analysis
```

Provider-scoped CLI (no provider `cli.py` needed):

```toml
[project.scripts]
crsd-inspector = "renderflow.cli:main"
```

With that entrypoint:
- `crsd-inspector -h` shows available workflows.
- `crsd-inspector range_doppler_processing -h` shows only that workflow's parameters/defaults/help.

Execute a workflow in terminal mode:

```bash
renderflow execute \
  --provider crsd-inspector \
  --workflow signal_analysis \
  --param crsd_directory=examples \
  --param prf_hz=1000 \
  --output terminal
```

Execute and export both:
- one combined report file (`--html`)
- per-figure files (`--save-figures-dir` + `--figure-format`)

```bash
renderflow execute \
  --provider crsd-inspector \
  --workflow signal_analysis \
  --param crsd_directory=examples \
  --html output/report.html \
  --save-figures-dir output/figures \
  --figure-format html
```

Add per-figure JSON in the same run:

```bash
renderflow execute \
  --provider crsd-inspector \
  --workflow signal_analysis \
  --param crsd_directory=examples \
  --html output/report.html \
  --save-figures-dir output/figures \
  --figure-format html \
  --figure-format json
```

Export multiple figure formats in a single run:

```bash
renderflow execute \
  --provider crsd-inspector \
  --workflow signal_analysis \
  --param crsd_directory=examples \
  --save-figures-dir output/figures \
  --figure-format html \
  --figure-format json
```

Comma-separated format lists are also accepted:

```bash
renderflow execute \
  --provider crsd-inspector \
  --workflow signal_analysis \
  --param crsd_directory=examples \
  --html output/report.html \
  --save-figures-dir output/figures \
  --figure-format html,json
```

If `--figure-format` is omitted, per-figure export defaults to `html`.
Image formats (`png`, `jpg`, `jpeg`, `svg`, `pdf`) require Kaleido. `renderflow` includes `kaleido` as a dependency.

Launch Streamlit:

```bash
renderflow run --provider crsd-inspector
```

## Shell Completion

Tab completion is supported via `argcomplete` for both:
- `renderflow ...`
- provider-scoped commands (for example `crsd-inspector ...`)

Activate in Bash for current shell:

```bash
eval "$(register-python-argcomplete renderflow)"
eval "$(register-python-argcomplete crsd-inspector)"
```

After activation, workflow subcommands and options complete with `Tab`.

## Workflow Result Contract

Use `renderflow.workflow.Workflow` inside provider workflows:

```python
from renderflow.workflow import Workflow

workflow = Workflow(name="My Workflow", description="...")
workflow.params = {
    "threshold": {
        "type": "number",
        "default": 0.5,
        "label": "Threshold",
        "description": "Minimum score to keep",
    },
}

workflow.add_text("Summary text")
workflow.add_table("Metrics", {"name": ["a"], "value": [1]})
workflow.add_plot(fig, title="Spectrum", figure_id="spectrum", save=True)
workflow.add_code("print('debug')", language="python")
return workflow.build()
```

`add_plot(..., save=False)` marks a plot as not exportable when using figure-save operations.

Minimum return contract from `run_workflow(...)`:
- must return a `dict`
- either:
  - modern shape: `{"results": [ ... ]}`
  - legacy shape: `{"text": [...], "tables": [...], "plots": [...]}`
- for modern shape, each item in `results` must be a dict with:
  - `type` in `text | table | plot | code`
  - if `type == "plot"`, item must include `figure`

## Provider Contract Options

### 1) Explicit `AppSpec` (fully explicit)

Entry point:

```toml
[project.entry-points."renderflow.providers"]
my-provider = "my_provider.app_definition:get_app_spec"
```

`get_app_spec()` returns `renderflow.contracts.AppSpec`.

### 2) Auto-Defined Provider (minimal)

If no `app_definition` exists, `renderflow` auto-builds from:
- `<provider>.workflows.*` modules with `run_workflow(...)`
- optional `<provider>.renderflow` module:
  - `APP_NAME = "..."`
  - `WORKFLOWS_PACKAGE = "provider.custom_workflows"` (optional)
  - optional custom metadata constants for provider setup

Workflow parameters are pulled from:
1. `workflow.params` if a `workflow` object exists in the module
2. `PARAMS` module global
3. inferred function signature defaults

This lets packages like `crsd-inspector` keep only workflow definitions and optional init logic, while `renderflow` handles CLI + Streamlit parameter interpretation and rendering.
