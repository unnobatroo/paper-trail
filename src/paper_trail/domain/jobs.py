"""a job is data (kind + json payload), not a closure, so any worker can run it"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

Handler = Callable[[dict, Callable[[str], None]], Any]

IN_FLIGHT = ("queued", "running")


@dataclass
class Job:
    id: str
    kind: str
    payload: dict = field(default_factory=dict)
    status: str = "queued"  # queued | running | done | failed
    progress: str = ""
    result: Any = None
    error: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat())


def dedupe_key(kind: str, payload: dict) -> str:
    """"same work" id, a double submit attaches to the job already running"""
    raw = json.dumps(payload or {}, sort_keys=True)
    return f"{kind}:{hashlib.sha256(raw.encode()).hexdigest()[:24]}"
