"""번역 결과 캐싱 — metadata.json의 SHA-256 해시 기반 재번역 스킵.

흐름:
    1) 번역 직전: metadata.json의 바이트 SHA-256 계산 → "sha256:abc..." 문자열
    2) metadata_i18n.json 저장 시 최상위 "_source_hash" 필드에 기록
    3) 재실행 시: 현재 metadata.json 해시 vs i18n 파일 _source_hash 비교
       - 일치: API 호출 스킵 (캐시 적중)
       - 불일치 또는 파일 없음: 재번역
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def compute_source_hash(metadata_path: Path) -> str:
    """파일 바이트를 SHA-256으로 해싱. 포맷: "sha256:<64자 16진수>".

    바이트 단위 해싱이라 JSON 인코딩/공백 차이까지 반영. 의도적 설계 —
    원본 파일 수정은 재번역 트리거여야 함.
    """
    raw = metadata_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    return f"sha256:{digest}"


def is_cache_valid(i18n_path: Path, expected_hash: str) -> bool:
    """metadata_i18n.json이 존재하고 _source_hash가 expected와 일치하면 True.

    다음 경우 False:
        - 파일 없음
        - JSON 파싱 실패 (손상)
        - _source_hash 필드 누락 또는 불일치
    """
    if not i18n_path.is_file():
        return False
    try:
        cached = json.loads(i18n_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return cached.get("_source_hash") == expected_hash
