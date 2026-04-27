"""J-LIN Studio GUI 진입 로직 (공유 모듈).

호출 경로 2개:
    1) `python -m src.gui` → `__main__.py` → `run_app()`
    2) PyInstaller .exe → `gui_main.py` (프로젝트 루트) → `run_app()`

PyInstaller --onefile entry script는 패키지 외부에 있어야 상대 import가 깨지지 않음.
모든 GUI 부팅 로직을 이 모듈에 모음.
"""
from __future__ import annotations

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from .paths import appdata_dir, env_path, resource_path


def _load_env() -> None:
    """APPDATA → 프로젝트 루트 폴백 순서로 .env 로드."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    user_env = env_path()
    if user_env.is_file():
        load_dotenv(user_env, override=True)
    else:
        dev_env = resource_path(".env")
        if dev_env.is_file():
            load_dotenv(dev_env)


_load_env()

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from . import style  # noqa: E402
from .main_window import MainWindow  # noqa: E402
from .wizard import SetupWizard, needs_setup  # noqa: E402


def run_app() -> int:
    """GUI 부팅 — QApplication + 마법사 분기 + 메인 윈도우."""
    app = QApplication(sys.argv)
    app.setApplicationName("jaylin-yt-translator")
    app.setOrganizationName("jaylin-yt-translator")
    app.setStyleSheet(style.STYLESHEET)

    appdata_dir()  # %APPDATA%/jaylin-yt-translator/ 자동 생성

    force = os.environ.get("JLIN_FORCE_WIZARD") == "1"
    if force or needs_setup():
        dialog = SetupWizard()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return 0
        _load_env()  # 마법사가 새 .env 작성 → 환경변수 다시 로드

    window = MainWindow()
    window.show()
    return app.exec()
