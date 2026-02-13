"""Streamlit entrypoint for the minimal provider example."""

from renderflow.streamlit_renderer import run_renderer


def main():
    # Resolve provider through entrypoint name; no app_definition.py required.
    run_renderer("minimal-provider")


if __name__ == "__main__":
    main()
