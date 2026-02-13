"""Streamlit entrypoint for the minimal provider example."""

from __future__ import annotations

import sys
from pathlib import Path

# When this app is launched from the renderflow monorepo, prefer local renderflow
# over any older site-packages install.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from renderflow.streamlit_renderer import run_renderer


def main():
    # Module name avoids requiring entrypoint installation in hosted runtimes.
    run_renderer("minimal_provider")


if __name__ == "__main__":
    main()
