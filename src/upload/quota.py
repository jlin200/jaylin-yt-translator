"""일일 쿼터 추적 (SPEC-UPLOAD-001 T6, REQ-11).

YouTube Data API: 10,000 units/일/프로젝트. videos.insert=1600, thumbnails.set=50.
한 영상 = 1,650 units → 일일 6개 한계.

리셋 기준: 본 모듈은 KST 자정 기준으로 단순화 (실제 Google은 PT 자정 ≈ 17:00 KST).
보수적: KST 자정이 PT보다 늦으니 우리 추적이 더 빠르게 리셋되지 않음 → 안전.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .errors import QuotaError

DAILY_LIMIT = 10_000
KST = timezone(timedelta(hours=9))


def _today_key() -> str:
    """KST 기준 오늘 날짜 (YYYY-MM-DD)."""
    return datetime.now(KST).strftime("%Y-%m-%d")


def get_used_today(quota_path: Path) -> int:
    """오늘 누적 사용량."""
    if not quota_path.is_file():
        return 0
    try:
        data = json.loads(quota_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    return int(data.get(_today_key(), 0))


def get_remaining(quota_path: Path) -> int:
    """오늘 남은 쿼터 (10,000 - 사용량)."""
    return DAILY_LIMIT - get_used_today(quota_path)


def record_usage(quota_path: Path, units: int) -> None:
    """오늘 키에 누적 (atomic write)."""
    data: dict = {}
    if quota_path.is_file():
        try:
            data = json.loads(quota_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    today = _today_key()
    data[today] = int(data.get(today, 0)) + units

    tmp = quota_path.with_suffix(quota_path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(quota_path)


def check_or_die(quota_path: Path, needed: int) -> None:
    """잔여 < needed 시 QuotaError raise (REQ-11)."""
    remaining = get_remaining(quota_path)
    if remaining < needed:
        raise QuotaError(
            f"오늘 사용 가능한 쿼터: {remaining:,} units\n"
            f"업로드에 필요한 쿼터: {needed:,} units\n"
            "해결: 자정(00:00 PT, ~17:00 KST) 이후 다시 시도하거나 "
            "--no-thumbnail (1,600 units만 사용)을 사용하세요."
        )
