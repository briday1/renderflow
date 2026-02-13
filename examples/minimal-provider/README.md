# Minimal Provider Example

This is a tiny provider package that demonstrates the `renderflow` API with:
- one initializer (`minimal_provider.renderflow:initialize`)
- two workflows under `minimal_provider.workflows`
- workflow params automatically discovered from `workflow.params`

## Install

From this repo root:

```bash
uv pip install -e .
uv pip install -e examples/minimal-provider
```

## Run

List providers:

```bash
renderflow list-providers
```

List example workflows:

```bash
renderflow list-workflows --provider minimal-provider
```

Show parameters:

```bash
renderflow show-params --provider minimal-provider --workflow greeting
```

Execute with terminal output:

```bash
renderflow execute \
  --provider minimal-provider \
  --workflow greeting \
  --init name=Ada \
  --param excited=true
```

Execute with combined report plus per-figure exports:

```bash
renderflow execute \
  --provider minimal-provider \
  --workflow series_plot \
  --init name=Ada \
  --param points=8 \
  --html output/minimal_report.html \
  --save-figures-dir output/minimal_figures \
  --figure-format html \
  --figure-format json
```

Run Streamlit:

```bash
renderflow run --provider minimal-provider
```

## API Summary

Provider package contract used here:
- `minimal_provider/renderflow.py`
  - `APP_NAME`
  - `WORKFLOWS_PACKAGE`
  - `INIT_PARAMS`
  - `initialize(params) -> dict`
- `minimal_provider/workflows/*.py`
  - `workflow = Workflow(name=..., description=...)`
  - `workflow.params = {...}`
  - `run_workflow(...) -> workflow.build()`

No custom CLI or custom renderer is needed in the provider.
