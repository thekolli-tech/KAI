"""SSE frames for public run events.

The model runtime yields text chunks. This module only serializes events
that the engine has already made public.
"""

import json

from kai_engine.events import RunEvent


def encode_run_event(event: RunEvent) -> str:
    """Encode one event as a single SSE frame."""

    payload = event.model_dump(mode="json", exclude_none=True)
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return f"event: {event.type.value}\ndata: {data}\n\n"
