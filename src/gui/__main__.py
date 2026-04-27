"""`python -m src.gui` 진입점 — 개발 환경용.

실제 부팅 로직은 `app.run_app()`에 있음 (PyInstaller .exe와 공유).
"""
from __future__ import annotations

import sys

from .app import run_app

sys.exit(run_app())
