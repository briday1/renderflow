"""Backward-compatible module for the Streamlit renderer entrypoint."""

from renderflow.cli import main
from renderflow.streamlit_renderer import launch_streamlit_renderer, run_renderer

__all__ = ["launch_streamlit_renderer", "main", "run_renderer"]
