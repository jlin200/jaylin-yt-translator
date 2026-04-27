"""SPEC-UPLOAD-001 커스텀 예외 + HTTP 에러 분류 + 백오프 (T1+T5).

REQ-19 exit code 매핑 (cli.main() 최상단 try/except에서 변환):
    AuthError       → 1  (credentials.json 없음, refresh 실패, 401)
    InputError      → 2  (폴더/파일 누락, 영상 N개, metadata 포맷 오류)
    UserCancelled   → 3  (--force-reupload y/N에서 N)
    QuotaError      → 5  (사전 잔여 부족 또는 403 quotaExceeded)
    UploadError     → 6  (5xx 백오프 후 실패, 그 외 4xx, 일반 실패)
"""
from __future__ import annotations

import json as _json
import time
from typing import Callable, TypeVar

from googleapiclient.errors import HttpError


# ===== 예외 계층 (T1) =====

class UploadError(Exception):
    """기본 업로드 실패. exit 6."""


class AuthError(UploadError):
    """OAuth 인증 실패. exit 1."""


class InputError(UploadError):
    """입력 검증 실패. exit 2."""


class UserCancelled(UploadError):
    """사용자가 y/N 프롬프트에서 거부. exit 3."""


class QuotaError(UploadError):
    """일일 쿼터 부족 또는 quotaExceeded. exit 5."""


# ===== HTTP 에러 분류 + 백오프 (T5, REQ-13~16) =====

T = TypeVar("T")


def with_retry(fn: Callable[[], T], max_attempts: int = 3) -> T:
    """5xx 에러만 지수 백오프 재시도. 4xx는 즉시 raise (REQ-15).

    Sleep: 1초 → 2초 → 4초 (attempt=0,1,2).
    """
    for attempt in range(max_attempts):
        try:
            return fn()
        except HttpError as e:
            status = e.resp.status
            if 500 <= status < 600 and attempt < max_attempts - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError("with_retry: unreachable")  # 타입 체커 만족용


def classify_http_error(e: HttpError) -> tuple[type[UploadError], str]:
    """HttpError → (예외 클래스, 친절한 메시지). cli.main()에서 raise.

    Returns:
        (AuthError | QuotaError | UploadError, 사용자용 메시지)
    """
    status = e.resp.status
    try:
        content = _json.loads(e.content) if e.content else {}
        error_obj = content.get("error", {})
        errors_list = error_obj.get("errors", [{}])
        reason = errors_list[0].get("reason", "")
        message = error_obj.get("message", "")
    except (ValueError, KeyError, IndexError):
        reason = ""
        message = ""

    if status == 401:
        return AuthError, (
            f"OAuth 토큰이 무효합니다 (HTTP 401).\n"
            f"reason: {reason or '(미상)'}\n"
            "해결: token.json 삭제 후 다시 실행하세요."
        )
    if status == 403 and reason in ("quotaExceeded", "uploadLimitExceeded"):
        return QuotaError, (
            f"YouTube API 쿼터 초과 (HTTP 403, reason={reason}).\n"
            "해결: 자정(00:00 PT, ~17:00 KST) 이후 다시 시도하세요."
        )
    if status == 403:
        return UploadError, (
            f"권한 부족 (HTTP 403).\n"
            f"reason: {reason}\n"
            f"메시지: {message or str(e)}\n"
            "해결: OAuth scope(youtube)이 충분한지, 채널 소유자로 로그인했는지 확인하세요."
        )
    if 500 <= status < 600:
        return UploadError, (
            f"서버 일시 오류 (HTTP {status}). 백오프 3회 모두 실패.\n"
            f"메시지: {message or str(e)}\n"
            "해결: 잠시 후 다시 시도하세요."
        )
    return UploadError, (
        f"API 호출 실패 (HTTP {status}).\n"
        f"reason: {reason}\n"
        f"메시지: {message or str(e)}"
    )
