"""업로드 결과 캐시 + 중복 방지 (SPEC-UPLOAD-001 T6, REQ-12, SEC-03).

`<폴더>/upload_result.json`:
    {
        "video_id": "...",
        "uploaded_at": "2026-04-27T13:42:11+09:00",
        "privacy_status": "private",
        "quota_used": 1650,
        "thumbnail_uploaded": true
    }

SEC-03: 민감 정보(token, secret) 미포함.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .errors import UserCancelled

KST = timezone(timedelta(hours=9))
CACHE_FILENAME = "upload_result.json"


def cache_path(folder: Path) -> Path:
    return folder / CACHE_FILENAME


def read_cache(folder: Path) -> dict | None:
    """캐시 읽기. 없거나 손상이면 None."""
    p = cache_path(folder)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_cache(
    folder: Path,
    *,
    video_id: str,
    privacy_status: str,
    quota_used: int,
    thumbnail_uploaded: bool,
) -> None:
    """업로드 결과 저장 (atomic write)."""
    data = {
        "video_id": video_id,
        "uploaded_at": datetime.now(KST).isoformat(timespec="seconds"),
        "privacy_status": privacy_status,
        "quota_used": quota_used,
        "thumbnail_uploaded": thumbnail_uploaded,
    }
    p = cache_path(folder)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def prompt_force_reupload(cache: dict) -> None:
    """y/N 확인 (REQ-12). N/그 외 입력이면 UserCancelled raise."""
    studio_url = f"https://studio.youtube.com/video/{cache['video_id']}/edit"
    print(
        f"이미 업로드된 영상입니다.\n"
        f"  videoId: {cache['video_id']}\n"
        f"  업로드 시간: {cache.get('uploaded_at', '(미기록)')}\n"
        f"  스튜디오: {studio_url}"
    )
    answer = input("정말 다시 올리시겠어요? [y/N] ").strip().lower()
    if answer not in ("y", "yes"):
        raise UserCancelled("취소되었습니다.")
