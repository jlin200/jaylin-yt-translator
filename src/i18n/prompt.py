"""Gemini 프롬프트 템플릿 + 언어 목록 로더.

languages.json에서 tier 구조를 읽어 target 언어 리스트 계산.
8개 번역 규칙이 명시된 프롬프트 템플릿 상수 + build_prompt() 빌더.
"""
from __future__ import annotations

import json
from pathlib import Path


_LANG_FILE = Path(__file__).parent / "languages.json"


def load_languages(tier: str) -> tuple[str, list[str]]:
    """`tier`에 해당하는 BCP-47 target 언어 리스트 + source language code 반환.

    tier 값:
        "1" → tier 1만 (6개)
        "2" → tier 1+2 누적 (21개)
        "3" → tier 1+2+3 누적 (50개)
        "all" → tier 3과 동일 (50개)

    Returns:
        (source_lang, target_langs). source_lang은 languages.json의 "source" 값 (예: "ko").
        target_langs는 source와 중복되지 않음 (호출자는 별도 원본 저장).

    Raises:
        ValueError: 알 수 없는 tier 값.
    """
    data = json.loads(_LANG_FILE.read_text(encoding="utf-8"))
    source: str = data["source"]
    tiers: dict[str, list[str]] = data["tiers"]

    if tier == "all":
        # tier 3까지 전부 누적과 동일
        langs: list[str] = []
        for t in ("1", "2", "3"):
            langs.extend(tiers[t])
        return source, langs

    if tier not in ("1", "2", "3"):
        raise ValueError(f"알 수 없는 tier: {tier}. 가능: 1, 2, 3, all")

    # 상위 tier는 하위 tier 포함 (tier 2 요청 시 tier 1 + 2 누적)
    langs: list[str] = []
    for t in ("1", "2", "3"):
        langs.extend(tiers[t])
        if t == tier:
            return source, langs
    return source, langs  # unreachable (tier "1"/"2"/"3" 중 하나는 match됨)


# ──────────────────────────────────────────────────────
# 프롬프트 템플릿 (8개 번역 규칙 명시)
# 규칙 8(Tone matching)은 Plimate 채널의 "따뜻/편안" 감성 유지를 위해 필수.
# ──────────────────────────────────────────────────────
PROMPT_TEMPLATE = """You are a professional YouTube content translator specializing in music playlist metadata.

Source language: Korean (ko)
Target languages: {languages_csv}

Translation rules:
1. Title: ≤100 characters per language (YouTube hard limit).
2. Description: ≤5000 characters per language.

3. CRITICAL — PRESERVE LINE BREAKS:
   The source description uses literal newline characters (\\n).
   You MUST keep the EXACT same line break structure in every translation.
   Do not merge lines, do not insert extra blank lines, do not flatten paragraphs.
   The line count of each translated description must match the source line count.

4. CRITICAL — PRESERVE NON-KOREAN SEGMENTS VERBATIM:
   The source may contain Korean mixed with English/numbers/symbols.
   Translate ONLY the Korean portions. The following segments must appear EXACTLY as in the source — do not translate, transliterate, paraphrase, or modify them in any way:
   - Time codes / track timestamps: "00:00", "1:23:45", "00:00 - Track Title", "[01:23] Song Name"
   - English song / track / album / artist names (e.g., "Sunset Boulevard", "Dreamy Cafe Vibes", "Café del Mar")
   - URLs (https://..., http://..., domain.com/path)
   - Hashtags: #cafe, #LoFi (translate the surrounding sentence, but the hashtag tokens themselves stay verbatim)
   - Email addresses
   - Code snippets, command names, file paths, version numbers
   - Numeric IDs and standalone numbers
   - Emojis (🎵, 🎶, 📌, etc.) — keep position and order intact
   When in doubt about a non-Korean segment, KEEP IT VERBATIM rather than translating.

5. Use idiomatic, native-speaker phrasing per locale for the Korean parts (not literal translation).
6. For music/playlist terms, use commonly searched terminology in that language.
7. Tone: match the source emotional register (warm, encouraging, casual).

Source title:
{source_title}

Source description:
{source_description}

Return a JSON object where each key is a target language code (BCP-47) and the value is:
{{"title": "...", "description": "..."}}

Include ALL requested target languages. Do not add languages not in the list.
Do not include the source Korean in the response (it is preserved separately by the caller).
"""


def build_prompt(source_title: str, source_description: str,
                 targets: list[str]) -> str:
    """프롬프트 상수에 실제 값 주입해서 완성된 프롬프트 문자열 반환."""
    return PROMPT_TEMPLATE.format(
        languages_csv=", ".join(targets),
        source_title=source_title,
        source_description=source_description,
    )
