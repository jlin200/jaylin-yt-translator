"""J-LIN Studio PyInstaller --onefile entry script (프로젝트 루트).

PyInstaller가 entry script를 패키지 외부 모듈로 처리 → `from .` 상대 import 회피.
실제 로직은 `src.gui.app.run_app()`에 위임.
"""
from __future__ import annotations

import sys

from src.gui.app import run_app

sys.exit(run_app())
