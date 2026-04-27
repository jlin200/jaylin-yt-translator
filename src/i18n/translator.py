"""Gemini API 번역 호출 — 단일 배치 + 지수 백오프 + 응답 검증.

이 모듈은 **한 번의 API 호출**만 책임. 누락 언어 재시도(REQ-09)는 pipeline.py에서.

핵심 요소:
    - GenerativeModel("gemini-2.5-flash") + JSON schema 응답 강제
    - ResourceExhausted/Timeout/ServiceUnavailable 시 지수 백오프 3회
    - 응답 검증: 요청 외 언어 제거, 길이 제한 트렁케이트
    - TranslationResult NamedTuple로 결과 + 메타(토큰/비용/경고) 반환
"""
from __future__ import annotations

import json
import os
import time
from typing import NamedTuple

import google.generativeai as genai
from google.api_core.exceptions import (
    DeadlineExceeded,
    ResourceExhausted,
    ServiceUnavailable,
)

from .prompt import build_prompt


# gemini-2.5-flash 가격 (2026-04 공식 기준)
_PRICE_IN_PER_MTOK = 0.075   # $/1M input tokens
_PRICE_OUT_PER_MTOK = 0.30   # $/1M output tokens
_MODEL_NAME = "gemini-2.5-flash"

# YouTube 한도
_TITLE_MAX = 100
_DESCRIPTION_MAX = 5000


class TranslationError(RuntimeError):
    """Gemini 호출 실패 또는 응답 파싱 실패."""


class MissingApiKeyError(Exception):
    """GEMINI_API_KEY 환경변수 누락."""

    def __init__(self) -> None:
        super().__init__(
            "GEMINI_API_KEY 환경변수가 설정되지 않았습니다.\n"
            "설정: .env 파일에 GEMINI_API_KEY=<키> 추가 후 재실행."
        )


class TranslationResult(NamedTuple):
    """translate_batch의 반환값. 불변 스냅샷."""
    translations: dict[str, dict[str, str]]   # {lang: {title, description}}
    missing_langs: list[str]                  # 요청했으나 응답에 없는 언어
    warnings: list[str]                       # 트렁케이트 등 경고
    tokens_in: int
    tokens_out: int
    cost_usd: float


def _ensure_api_key() -> None:
    if not os.environ.get("GEMINI_API_KEY"):
        raise MissingApiKeyError()


def _build_schema(target_langs: list[str]) -> dict:
    """Gemini response_schema 구조. 각 언어가 {title, description} 객체."""
    return {
        "type": "object",
        "properties": {
            lang: {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["title", "description"],
            }
            for lang in target_langs
        },
    }


def _call_with_retry(model, prompt: str, schema: dict):
    """지수 백오프 3회 재시도. 1s → 2s → 4s."""
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            return model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                },
            )
        except (ResourceExhausted, DeadlineExceeded, ServiceUnavailable) as e:
            last_exc = e
            if attempt < 2:
                time.sleep(2 ** attempt)  # 1s, 2s
    raise TranslationError(
        f"Gemini API 3회 재시도 후 실패: {type(last_exc).__name__}"
    ) from last_exc


def _validate_and_truncate(
    translations: dict, requested: list[str],
) -> tuple[dict, list[str], list[str]]:
    """요청 외 언어 제거 + 길이 제한 트렁케이트. (수정된 dict, 누락 언어, 경고 목록) 반환."""
    warnings: list[str] = []
    requested_set = set(requested)
    received_set = set(translations.keys())
    missing = sorted(requested_set - received_set)

    # 요청하지 않은 언어 제거 (스키마 강제로도 혹시 모름)
    for lang in list(translations.keys()):
        if lang not in requested_set:
            del translations[lang]

    # 길이 검증 + 트렁케이트
    for lang, entry in translations.items():
        title = entry.get("title", "")
        desc = entry.get("description", "")
        if len(title) > _TITLE_MAX:
            warnings.append(
                f"[{lang}] title truncated: {len(title)} → {_TITLE_MAX} chars"
            )
            entry["title"] = title[:_TITLE_MAX]
        if len(desc) > _DESCRIPTION_MAX:
            warnings.append(
                f"[{lang}] description truncated: "
                f"{len(desc)} → {_DESCRIPTION_MAX} chars"
            )
            entry["description"] = desc[:_DESCRIPTION_MAX]

    return translations, missing, warnings


def translate_batch(
    source_title: str,
    source_description: str,
    target_langs: list[str],
) -> TranslationResult:
    """한 번의 Gemini 호출로 target_langs 전체 번역.

    Raises:
        MissingApiKeyError: GEMINI_API_KEY 없음.
        TranslationError: 3회 재시도 후 실패 또는 JSON 파싱 실패.
    """
    _ensure_api_key()
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(_MODEL_NAME)

    prompt = build_prompt(source_title, source_description, target_langs)
    schema = _build_schema(target_langs)

    response = _call_with_retry(model, prompt, schema)

    # JSON 파싱
    try:
        translations = json.loads(response.text)
    except (json.JSONDecodeError, AttributeError) as e:
        raise TranslationError(
            f"Gemini 응답 JSON 파싱 실패: {str(e)[:200]}"
        ) from e

    # 검증 + 트렁케이트 (빈 결과 raise는 호출자 소관 — pipeline에서 판정)
    translations, missing, warnings = _validate_and_truncate(
        translations, target_langs
    )

    # 토큰 사용량 추출 (Gemini SDK가 제공)
    usage = getattr(response, "usage_metadata", None)
    tokens_in = getattr(usage, "prompt_token_count", 0) if usage else 0
    tokens_out = getattr(usage, "candidates_token_count", 0) if usage else 0
    cost = (
        tokens_in * _PRICE_IN_PER_MTOK
        + tokens_out * _PRICE_OUT_PER_MTOK
    ) / 1_000_000

    return TranslationResult(
        translations=translations,
        missing_langs=missing,
        warnings=warnings,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
    )
