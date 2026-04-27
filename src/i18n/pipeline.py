"""플레이리스트 메타데이터 번역 파이프라인.

흐름:
    1) metadata.json 로드 + 해시 계산
    2) 캐시 유효하면 스킵 (force=False일 때)
    3) 언어 tier 로드 (source 제외한 targets)
    4) 1차 Gemini 호출
       - 응답 0개면 exit 4 (전체 실패)
    5) 누락 있으면 2차 자동 호출 (REQ-09)
       - 2차 API 실패 시 1차 결과만 유지
    6) 결과 병합 + 최종 누락 경고
    7) metadata_i18n.json 저장 (_source_hash + source + translations)
    8) 총 비용 출력
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .cache import compute_source_hash, is_cache_valid
from .prompt import load_languages
from .translator import (
    TranslationError,
    TranslationResult,
    _PRICE_IN_PER_MTOK,
    _PRICE_OUT_PER_MTOK,
    translate_batch,
)


def translate_playlist(
    folder: Path,
    tier: str = "all",
    force: bool = False,
) -> Path:
    """플레이리스트 폴더의 metadata.json → metadata_i18n.json 생성/갱신.

    Returns: metadata_i18n.json 절대 경로.
    Raises:
        FileNotFoundError: metadata.json 없음.
        TranslationError: 1차 응답에서 0개 번역 (전체 실패).
        MissingApiKeyError: GEMINI_API_KEY 없음 (translator에서 전파).
    """
    meta_path = folder / "metadata.json"
    i18n_path = folder / "metadata_i18n.json"

    if not meta_path.is_file():
        raise FileNotFoundError(
            f"metadata.json이 없습니다: {meta_path}\n"
            "원본 제목/설명을 다음 포맷으로 저장하세요:\n"
            '  {"title": "...", "description": "..."}'
        )

    # 원본 로드
    source = json.loads(meta_path.read_text(encoding="utf-8"))
    src_title: str = source["title"]
    src_desc: str = source["description"]

    # --- 캐시 체크 ---
    source_hash = compute_source_hash(meta_path)
    if not force and is_cache_valid(i18n_path, source_hash):
        print(f"[i18n] 캐시 적중 ({i18n_path.name}) — 스킵")
        return i18n_path

    # --- 언어 로드 (source 제외) ---
    source_lang, targets = load_languages(tier)
    if source_lang in targets:
        targets = [t for t in targets if t != source_lang]

    print(
        f"[i18n] tier={tier}: {len(targets)}개 언어 번역 중... "
        f"(모델: gemini-2.5-flash)"
    )

    # --- 1차 호출 ---
    result1: TranslationResult = translate_batch(src_title, src_desc, targets)
    translations = dict(result1.translations)
    warnings = list(result1.warnings)
    tokens_in = result1.tokens_in
    tokens_out = result1.tokens_out

    # 전체 실패 판정
    if not translations:
        raise TranslationError("1차 응답에서 번역 결과 0개 (전체 실패)")

    # --- 2차 자동 재시도 (REQ-09) ---
    final_missing: list[str] = []
    if result1.missing_langs:
        print(
            f"[i18n] 1차 결과 {len(translations)}/{len(targets)}개, "
            f"누락 {len(result1.missing_langs)}개 → 2차 자동 재시도..."
        )
        try:
            result2 = translate_batch(
                src_title, src_desc, result1.missing_langs
            )
            translations.update(result2.translations)
            warnings.extend(result2.warnings)
            tokens_in += result2.tokens_in
            tokens_out += result2.tokens_out
            final_missing = result2.missing_langs
        except TranslationError as e:
            # 2차 API 자체가 실패 (3회 백오프 소진): 1차 결과만 유지
            print(f"  ⚠ 2차 재시도 실패: {e}", file=sys.stderr)
            final_missing = result1.missing_langs

    # --- 최종 상태 경고 ---
    for w in warnings:
        print(f"  ⚠ {w}", file=sys.stderr)
    if final_missing:
        print(
            f"  ⚠ 최종 누락된 언어 ({len(final_missing)}): "
            f"{', '.join(final_missing)}",
            file=sys.stderr,
        )

    # --- 저장 (YouTube localizations 포맷 + 메타) ---
    output = {
        "_source_hash": source_hash,
        source_lang: {"title": src_title, "description": src_desc},
        **translations,
    }
    i18n_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # --- 총 비용 (1+2차 누적) ---
    total_cost = (
        tokens_in * _PRICE_IN_PER_MTOK
        + tokens_out * _PRICE_OUT_PER_MTOK
    ) / 1_000_000

    print(
        f"[i18n] 완료: {len(translations)}개 언어 저장. "
        f"tokens: {tokens_in:,} in / {tokens_out:,} out "
        f"= ${total_cost:.4f}"
    )
    return i18n_path
