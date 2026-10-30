"""api + review ui in one process: `uvicorn paper_trail.ui.main:app`

one worker only: nicegui keeps page state in-process over a websocket. slow work already
runs in the job worker, so that's fine
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from nicegui import ui

from ..api.app import create_app
from ..infrastructure.settings import load
from . import pages  # noqa: F401  registers the @ui.page routes


def session_secret(review_key: str) -> str:
    # signs the per-browser storage cookie. derived so prod needs no new env var,
    # dev (no key) gets a fresh one per boot and you just log in again
    if not review_key:
        return secrets.token_hex(32)
    return hmac.new(review_key.encode(), b"paper-trail ui session", hashlib.sha256).hexdigest()


app = create_app()
ui.run_with(app, title="Paper Trail", storage_secret=session_secret(load().review_key),
            show_welcome_message=False)
