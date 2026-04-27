"""입력 폴더 검증 + YouTube videos.insert body 빌드 (SPEC-UPLOAD-001 T2).

흐름:
    discover_inputs(folder, ...) → Inputs(영상/메타/i18n/썸네일)
    build_body(metadata, i18n, privacy_status) → snippet+status+localizations dict
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

from .errors import InputError


class Inputs(NamedTuple):
    """discover_inputs() 반환 컨테이너 (불변)."""
    video: Path
    metadata: dict           # metadata.json 파싱 결과
    i18n: dict               # metadata_i18n.json 파싱 결과 (_source_hash 포함)
    thumbnail: Path | None   # None = 자동 탐지 실패 또는 --no-thumbnail


def discover_inputs(
    folder: Path,
    video_override: Path | None = None,
    thumbnail_override: Path | None = None,
    no_thumbnail: bool = False,
) -> Inputs:
    """폴더에서 영상/메타데이터/썸네일 자동 탐지 + 검증 (REQ-04, T2).

    Raises:
        InputError: 폴더/메타 파일 누락, .mp4 N개, override 경로 불량, JSON 파싱 실패.
    """
    if not folder.is_dir():
        raise InputError(
            f"폴더가 아닙니다: {folder}\n"
            "해결: metadata.json + metadata_i18n.json + .mp4 1개가 들어 있는 폴더 경로를 지정하세요."
        )

    # --- 영상 (REQ-04) ---
    if video_override is not None:
        video = video_override.expanduser().resolve()
        if not video.is_file():
            raise InputError(
                f"--video 파일이 없습니다: {video}\n"
                "해결: 정확한 .mp4 경로를 지정하세요."
            )
    else:
        mp4s = sorted(folder.glob("*.mp4"))
        if len(mp4s) == 0:
            raise InputError(
                f"영상 파일이 없습니다.\n"
                f"폴더: {folder}\n"
                "해결: 폴더에 .mp4를 두거나 --video <path>로 명시하세요."
            )
        if len(mp4s) > 1:
            names = ", ".join(p.name for p in mp4s)
            raise InputError(
                f"영상 파일이 {len(mp4s)}개 발견되었습니다: {names}\n"
                f"폴더: {folder}\n"
                "해결: .mp4 1개만 두거나 --video <path>로 명시하세요."
            )
        video = mp4s[0]

    # --- 메타데이터 (REQ-05) ---
    meta_path = folder / "metadata.json"
    if not meta_path.is_file():
        raise InputError(
            f"metadata.json이 없습니다: {meta_path}\n"
            "해결: 다음 포맷으로 저장하세요:\n"
            '  {"title": "한국어 제목", "description": "한국어 설명", "tags": []}\n'
            "  (tags는 옵션)"
        )

    i18n_path = folder / "metadata_i18n.json"
    if not i18n_path.is_file():
        raise InputError(
            f"metadata_i18n.json이 없습니다: {i18n_path}\n"
            "해결: SPEC-I18N-001을 먼저 실행하세요:\n"
            f"  python -m src.i18n {folder}"
        )

    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise InputError(
            f"metadata.json JSON 파싱 실패: {meta_path}\n"
            f"오류: {e}\n"
            "해결: JSON 형식이 올바른지 확인하세요."
        )

    try:
        i18n = json.loads(i18n_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise InputError(
            f"metadata_i18n.json JSON 파싱 실패: {i18n_path}\n"
            f"오류: {e}"
        )

    # 최소 검증: ko 키 + title/description (REQ-05)
    if "ko" not in i18n:
        raise InputError(
            f"metadata_i18n.json에 'ko' 키가 없습니다: {i18n_path}\n"
            "해결: SPEC-I18N-001을 다시 실행하세요 (한국어가 source여야 함)."
        )
    ko_block = i18n["ko"]
    if not isinstance(ko_block, dict) or "title" not in ko_block or "description" not in ko_block:
        raise InputError(
            f"metadata_i18n.json의 'ko' 항목이 올바르지 않습니다.\n"
            f'기대: {{"title": "...", "description": "..."}}\n'
            f"현재: {ko_block!r}"
        )

    # --- 썸네일 (REQ-10) ---
    thumbnail: Path | None
    if no_thumbnail:
        thumbnail = None
    elif thumbnail_override is not None:
        thumbnail = thumbnail_override.expanduser().resolve()
        if not thumbnail.is_file():
            raise InputError(
                f"--thumbnail 파일이 없습니다: {thumbnail}\n"
                "해결: 정확한 썸네일 경로를 지정하거나 --no-thumbnail로 스킵하세요."
            )
    else:
        png = folder / "thumbnail.png"
        jpg = folder / "thumbnail.jpg"
        if png.is_file():
            thumbnail = png
        elif jpg.is_file():
            thumbnail = jpg
        else:
            thumbnail = None  # 자동 탐지 실패 — 경고는 cli.main()에서

    return Inputs(video=video, metadata=metadata, i18n=i18n, thumbnail=thumbnail)


def build_body(
    metadata: dict,
    i18n: dict,
    privacy_status: str,
) -> dict:
    """videos.insert body 조립 (REQ-05, REQ-06, REQ-07).

    Args:
        metadata: metadata.json 파싱 결과 ('tags' 옵션).
        i18n: metadata_i18n.json 파싱 결과 ('_' prefix 키 포함, 자동 필터링됨).
        privacy_status: "private" | "unlisted" | "public".

    Returns:
        videos.insert(part="snippet,status,localizations", body=...)에 그대로 전달 가능.
    """
    ko = i18n["ko"]

    # localizations: '_' prefix 키 제외 (REQ-06). ko 포함 (defaultLanguage와 중복 무해).
    localizations = {k: v for k, v in i18n.items() if not k.startswith("_")}

    return {
        "snippet": {
            "title": ko["title"],
            "description": ko["description"],
            "tags": metadata.get("tags", []),       # REQ-05: 옵션, 없으면 빈 리스트
            "categoryId": "10",                      # Music 고정 (REQ-05)
            "defaultLanguage": "ko",
            "defaultAudioLanguage": "ko",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,        # 음악 채널 가정
        },
        "localizations": localizations,
    }
