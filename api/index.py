"""Vercel entry point: the REST API as a serverless function.

The built review app is static files on Vercel's CDN, so only /api/* reaches this function.
"""

import sys
from pathlib import Path

# The package lives under src/, which Vercel doesn't put on the path by itself.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from paper_trail.api.app import app  # noqa: E402

__all__ = ["app"]
