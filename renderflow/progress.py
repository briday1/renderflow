"""Progress and timing helpers for workflow execution."""

from __future__ import annotations

import time
import traceback
from typing import Any, Callable


def emit_progress(metadata: dict[str, Any] | None, step: str, status: str, detail: str = "") -> None:
    """Emit a progress event if the metadata includes a progress callback."""
    if metadata is None:
        return
    callback = metadata.get("_progress_callback")
    if callable(callback):
        callback(step=step, status=status, detail=detail)


def wrap_with_timing(
    fn: Callable[[dict[str, Any]], Any],
    label: str,
    description: str,
    metadata: dict[str, Any] | None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Wrap a node-like function with timing and progress callbacks.

    The wrapper:
    - emits `running/done/failed` progress events
    - adds `_timing` in seconds to the output mapping
    - returns a structured error mapping on failure
    """

    def wrapper(inputs: dict[str, Any]) -> dict[str, Any]:
        emit_progress(metadata, label, "running", description)
        start_time = time.perf_counter()
        try:
            output = fn(inputs)
            elapsed_s = time.perf_counter() - start_time
            if not isinstance(output, dict):
                output = {"result": output}
            output["_timing"] = elapsed_s
            emit_progress(metadata, label, "done", description)
            return output
        except Exception as exc:  # pragma: no cover - passthrough behavior
            elapsed_s = time.perf_counter() - start_time
            emit_progress(metadata, label, "failed", description)
            return {
                "_timing": elapsed_s,
                "_node_error": f"ERROR in {label}: {str(exc)}",
                "_node_error_traceback": traceback.format_exc(),
                "_node_failed": True,
            }

    return wrapper

