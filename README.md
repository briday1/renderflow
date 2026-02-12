# renderflow

Generic workflow runtime + Streamlit renderer for provider plugins.

## Run

```bash
renderflow run --provider crsd-inspector
```

## List Installed Providers

```bash
renderflow list-providers
```

Providers register with entry points:

```toml
[project.entry-points."renderflow.providers"]
my-provider = "my_provider_package.app_definition:get_app_spec"
```
