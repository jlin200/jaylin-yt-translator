"""GUI 백그라운드 워커 — URL 기반 다국어 메타데이터 갱신.

흐름:
    1. URL/ID 검증 + videoId 추출
    2. i18n.translate_batch (1차 + 누락 시 2차 재시도)
    3. auth.get_credentials() — APPDATA 경로 명시
    4. api.build_service() + api.update_localizations() (videos.update)
    5. quota.record_usage(50)

QThread + Signal/Slot 패턴 — UI 멈춤 방지.
"""
from __future__ import annotations

import json

from googleapiclient.errors import HttpError
from PySide6.QtCore import QObject, Signal

from src.i18n.prompt import load_languages
from src.i18n.translator import MissingApiKeyError, TranslationError, translate_batch
from src.upload import api, auth, quota
from src.upload.errors import AuthError, with_retry

from . import paths
from .error_dialog import (
    ErrorCategory,
    classify_auth_error,
    classify_gemini_error,
    classify_http_status,
)

QUOTA_UPDATE = 50


class UpdateWorker(QObject):
    """videos.update 워커.

    Signals:
        progress(int)        : 0~100 진행률
        stage(str)           : 현재 단계 텍스트 (status badge)
        log(str)             : 작업 로그 영역 한 줄 추가
        done(dict)           : 완료 결과 ({video_id, languages, tokens_in, tokens_out, studio_url, watch_url})
        error(str, str)      : (카테고리, 원본 메시지) — main_window가 친절한 다이얼로그로 변환
    """

    progress = Signal(int)
    stage = Signal(str)
    log = Signal(str)
    done = Signal(dict)
    error = Signal(str, str)

    def __init__(
        self,
        url_or_id: str,
        title_ko: str,
        description_ko: str,
        tier: str,
    ) -> None:
        super().__init__()
        self.url_or_id = url_or_id
        self.title_ko = title_ko
        self.description_ko = description_ko
        self.tier = tier

    def run(self) -> None:
        try:
            # ---- 1) videoId 추출 ----
            self.stage.emit("입력 검증 중")
            self.progress.emit(5)
            video_id = api.extract_video_id(self.url_or_id)
            if not video_id:
                self.error.emit(
                    ErrorCategory.INPUT,
                    "유효하지 않은 유튜브 URL 또는 영상 ID입니다.\n"
                    "예: https://youtube.com/watch?v=ABC1234567 또는 11자 영상 ID."
                )
                return
            self.log.emit(f"✓ videoId 추출: {video_id}")

            # ---- 2) 언어 tier 로드 ----
            source_lang, targets = load_languages(self.tier)
            if source_lang in targets:
                targets = [t for t in targets if t != source_lang]
            self.log.emit(f"✓ 번역 대상: {len(targets)}개 언어")

            # ---- 3) 번역 (1차) ----
            self.stage.emit(f"번역 중 (0/{len(targets)})")
            self.progress.emit(15)
            try:
                result1 = translate_batch(
                    self.title_ko, self.description_ko, targets
                )
            except MissingApiKeyError as e:
                self.error.emit(ErrorCategory.GEMINI_API, str(e))
                return
            except TranslationError as e:
                self.error.emit(classify_gemini_error(str(e)), f"번역 실패: {e}")
                return
            except Exception as e:
                # Gemini SDK 예외 (InvalidArgument 등) — TranslationError로 감싸지지 않음
                msg = f"{type(e).__name__}: {e}"
                self.error.emit(
                    classify_gemini_error(msg), f"번역 호출 실패: {msg}"
                )
                return

            translations = dict(result1.translations)
            tokens_in = result1.tokens_in
            tokens_out = result1.tokens_out
            self.log.emit(
                f"✓ 1차 번역 완료: {len(translations)}/{len(targets)} 언어"
            )
            self.progress.emit(50)

            # ---- 4) 누락 자동 재시도 (i18n REQ-09) ----
            if result1.missing_langs:
                self.stage.emit(f"누락 {len(result1.missing_langs)}개 재시도")
                try:
                    result2 = translate_batch(
                        self.title_ko, self.description_ko, result1.missing_langs
                    )
                    translations.update(result2.translations)
                    tokens_in += result2.tokens_in
                    tokens_out += result2.tokens_out
                    self.log.emit(
                        f"✓ 2차 재시도 완료 ({len(result2.translations)}개 추가)"
                    )
                except Exception as e:
                    self.log.emit(
                        f"⚠ 2차 재시도 실패 ({type(e).__name__}) — 1차 결과만 유지"
                    )
            self.progress.emit(70)

            # ---- 5) 페이로드 빌드 ----
            snippet = {
                "title": self.title_ko,
                "description": self.description_ko,
                "categoryId": "10",                # Music
                "defaultLanguage": "ko",
                "defaultAudioLanguage": "ko",
            }
            localizations = {
                **translations,
                "ko": {
                    "title": self.title_ko,
                    "description": self.description_ko,
                },
            }

            # ---- 6) OAuth + service ----
            self.stage.emit("YouTube 인증 중")
            creds_path = paths.credentials_path()
            tok_path = paths.token_path()
            try:
                creds = auth.get_credentials(
                    credentials_path=creds_path,
                    token_path=tok_path,
                )
            except AuthError as e:
                self.error.emit(classify_auth_error(str(e)), str(e))
                return
            except Exception as e:
                msg = f"OAuth 인증 흐름 실패: {e}"
                self.error.emit(classify_auth_error(msg), msg)
                return

            service = api.build_service(creds)
            self.progress.emit(85)
            self.log.emit("✓ YouTube 인증 완료")

            # ---- 7) videos.update ----
            self.stage.emit("YouTube 메타데이터 업데이트 중")
            try:
                with_retry(
                    lambda: api.update_localizations(
                        service, video_id, snippet, localizations
                    ),
                    max_attempts=3,
                )
            except HttpError as e:
                category, msg = _classify_youtube_http_error(e)
                if category == ErrorCategory.AUTH_INVALID:
                    auth.delete_token(token_path=tok_path)
                self.error.emit(category, msg)
                return

            quota.record_usage(paths.quota_log_path(), QUOTA_UPDATE)
            self.progress.emit(100)
            self.log.emit(
                f"✓ videos.update 성공 ({len(localizations)}개 언어 등록)"
            )

            # ---- 8) 완료 ----
            self.done.emit({
                "video_id": video_id,
                "languages": sorted(localizations.keys()),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "studio_url": f"https://studio.youtube.com/video/{video_id}/edit",
                "watch_url": f"https://www.youtube.com/watch?v={video_id}",
            })

        except Exception as e:
            msg = f"예상치 못한 오류: {type(e).__name__}: {e}"
            gemini_cat = classify_gemini_error(msg)
            if gemini_cat == ErrorCategory.GEMINI_API_KEY_INVALID:
                cat = gemini_cat
            elif _is_network_error(e):
                cat = ErrorCategory.NETWORK
            else:
                cat = ErrorCategory.UNKNOWN
            self.error.emit(cat, msg)


def _classify_youtube_http_error(e: HttpError) -> tuple[str, str]:
    """YouTube API HttpError → (카테고리, 사용자용 메시지)."""
    status = e.resp.status
    try:
        content = json.loads(e.content) if e.content else {}
        error_obj = content.get("error", {})
        errors_list = error_obj.get("errors", [{}])
        reason = errors_list[0].get("reason", "")
        message = error_obj.get("message", "")
    except (ValueError, KeyError, IndexError):
        reason = ""
        message = ""

    category = classify_http_status(status, reason)
    detail = (
        f"HTTP {status} · reason={reason or '(미상)'}\n"
        f"{message or str(e)}"
    )
    return category, detail


def _is_network_error(e: BaseException) -> bool:
    """OSError/ConnectionError 등 네트워크 계열인지 추정."""
    if isinstance(e, (ConnectionError, TimeoutError)):
        return True
    name = type(e).__name__.lower()
    if "connection" in name or "timeout" in name or "dns" in name:
        return True
    msg = str(e).lower()
    keywords = ("getaddrinfo", "name resolution", "name or service",
                "network is unreachable", "connection refused",
                "max retries exceeded", "ssl")
    return any(k in msg for k in keywords)
