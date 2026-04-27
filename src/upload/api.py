"""YouTube Data API v3 호출 (SPEC-UPLOAD-001 T4, REQ-04, REQ-08~10).

함수:
    build_service(creds)       : discovery 기반 service 객체
    upload_video(...)          : videos.insert + resumable + 진행률 콜백 → videoId
    set_thumbnail(...)         : thumbnails.set (영상 insert 후 호출)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# REQ-08: 50MB chunk. 작으면 오버헤드↑, 크면 메모리/재개 단위↑.
DEFAULT_CHUNKSIZE = 50 * 1024 * 1024


def build_service(creds: Credentials):
    """YouTube v3 service 객체 생성.

    googleapiclient.discovery.build()는 API 메타데이터를 자동 로드해서
    service.videos().insert(...) 같은 메서드 체이닝을 가능하게 함.
    cache_discovery=False: 디스크 캐시 안 함 (Python 3.14에서 oauth2client 의존 경고 회피).
    """
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_video(
    service,
    body: dict,
    video_path: Path,
    on_progress: Callable[[int], None] | None = None,
    chunksize: int = DEFAULT_CHUNKSIZE,
) -> str:
    """videos.insert resumable upload (REQ-04, REQ-08, REQ-09).

    Args:
        service       : build_service() 반환값
        body          : payload.build_body() 반환값
        video_path    : .mp4 절대경로
        on_progress   : 진행률 콜백 (0~100 정수). None이면 무음.
        chunksize     : 청크 크기 (기본 50MB)

    Returns:
        videoId (11자 영숫자).

    Raises:
        googleapiclient.errors.HttpError: API 에러 — cli.main()에서 분류.
    """
    media = MediaFileUpload(
        str(video_path),
        chunksize=chunksize,
        resumable=True,
        mimetype="video/*",
    )
    request = service.videos().insert(
        part="snippet,status,localizations",
        body=body,
        media_body=media,
    )

    # 청크 단위 루프. response is None인 동안 계속 next_chunk() 호출.
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status and on_progress is not None:
            on_progress(int(status.progress() * 100))

    if on_progress is not None:
        on_progress(100)  # 마지막 청크 후 100% 보장

    return response["id"]


def set_thumbnail(service, video_id: str, thumbnail_path: Path) -> None:
    """thumbnails.set (REQ-10). 영상 insert 후 별도 호출 필수.

    Raises:
        googleapiclient.errors.HttpError: cli.main()에서 부분 실패로 처리 (REQ-17).
    """
    media = MediaFileUpload(str(thumbnail_path))
    service.thumbnails().set(videoId=video_id, media_body=media).execute()


# ===== URL 기반 메타데이터 갱신 (GUI 워크플로우) =====

_VIDEO_ID_FROM_URL = re.compile(
    r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})"
)
_VIDEO_ID_BARE = re.compile(r"^([A-Za-z0-9_-]{11})$")


def extract_video_id(text: str) -> str | None:
    """URL 또는 11자 ID에서 videoId 추출.

    매칭 패턴:
        https://youtube.com/watch?v=XXX
        https://www.youtube.com/watch?v=XXX
        https://youtu.be/XXX
        https://youtube.com/shorts/XXX
        XXX (11자 단독)

    Returns:
        videoId (11자) 또는 None (매칭 실패).
    """
    text = (text or "").strip()
    if not text:
        return None
    m = _VIDEO_ID_BARE.match(text)
    if m:
        return m.group(1)
    m = _VIDEO_ID_FROM_URL.search(text)
    if m:
        return m.group(1)
    return None


def update_localizations(
    service,
    video_id: str,
    snippet: dict,
    localizations: dict,
) -> None:
    """videos.update — snippet + localizations 갱신 (영상 자체 미수정).

    Args:
        service       : build_service() 반환값
        video_id      : 11자 videoId
        snippet       : title/description/categoryId/defaultLanguage 포함 dict (categoryId 필수)
        localizations : {"en": {"title", "description"}, ...}

    쿼터: 50 units.

    Raises:
        googleapiclient.errors.HttpError
    """
    body = {
        "id": video_id,
        "snippet": snippet,
        "localizations": localizations,
    }
    service.videos().update(
        part="snippet,localizations",
        body=body,
    ).execute()
