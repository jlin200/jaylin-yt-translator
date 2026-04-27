"""GUI 사용자 데이터 경로 + PyInstaller _MEIPASS 헬퍼 (SPEC-GUI-001 T1, GUI-04, GUI-08).

`%APPDATA%/jaylin-yt-translator/` 자동 생성 + 사용자 키/토큰 위치 제공.
PyInstaller --onefile 환경에서 번들된 리소스(languages.json) 접근도 처리.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "jaylin-yt-translator"


def appdata_dir() -> Path:
    """`%APPDATA%/jaylin-yt-translator/` 반환 + 자동 생성.

    Windows: C:\\Users\\<user>\\AppData\\Roaming\\jaylin-yt-translator\\
    그 외 (테스트/리눅스): ~/.jaylin-yt-translator/
    """
    base = os.environ.get("APPDATA")
    if base:
        d = Path(base) / APP_NAME
    else:
        d = Path.home() / f".{APP_NAME}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def credentials_path() -> Path:
    return appdata_dir() / "credentials.json"


def token_path() -> Path:
    return appdata_dir() / "token.json"


def env_path() -> Path:
    return appdata_dir() / ".env"


def quota_log_path() -> Path:
    return appdata_dir() / ".quota_log.json"


def resource_path(relative: str) -> Path:
    """PyInstaller --onefile 번들 리소스의 런타임 절대 경로.

    개발 환경: 프로젝트 루트 기준 (src/gui/paths.py → 3단계 위)
    .exe 환경: `sys._MEIPASS` (임시 압축 풀린 폴더)

    Args:
        relative: 프로젝트 루트 기준 상대 경로 (예: "src/i18n/languages.json")
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).resolve().parent.parent.parent / relative


def appdata_dir_display() -> str:
    """GUI 표시용 경로 문자열 (사용자 디렉토리는 변수로)."""
    return str(appdata_dir())
