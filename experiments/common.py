"""Shared experiment helpers: device, seeding, result files."""

from __future__ import annotations

import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

RESULTS = ROOT / "experiments" / "results"
SEED = 17


def device() -> str:
    """Plain torch device selection — same code runs local and on Vast."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def gpu_name() -> str | None:
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
    except ImportError:
        pass
    return None


def seed_everything() -> None:
    random.seed(SEED)
    try:
        import torch
        torch.manual_seed(SEED)
    except ImportError:
        pass


class Timer:
    def __enter__(self):
        self.t0 = time.time()
        return self

    @property
    def seconds(self) -> float:
        return round(time.time() - self.t0, 1)

    def __exit__(self, *exc):
        pass


def save_result(name: str, payload: dict) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment": name,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "device": device(),
        "gpu": gpu_name(),
        "seed": SEED,
        **payload,
    }
    out = RESULTS / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"saved -> {out}")
    return out
