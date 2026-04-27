"""T2 수동 검증 — plan.md의 4가지 케이스.

실행: python -m tests.smoke_payload
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# 모듈 import용
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.upload.errors import InputError
from src.upload.payload import build_body, discover_inputs


def _make_normal_folder(td: Path) -> Path:
    """정상 폴더 (mp4 1개 + metadata + i18n + thumbnail.png)."""
    (td / "metadata.json").write_text(
        json.dumps({"title": "오늘은 괜찮은 하루", "description": "본문", "tags": ["lofi"]},
                   ensure_ascii=False),
        encoding="utf-8",
    )
    (td / "metadata_i18n.json").write_text(
        json.dumps({
            "_source_hash": "sha256:abc",
            "ko": {"title": "오늘은 괜찮은 하루", "description": "본문"},
            "en": {"title": "It's Okay Today", "description": "Body"},
            "ja": {"title": "今日は大丈夫", "description": "本文"},
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    (td / "video1.mp4").write_text("")
    (td / "thumbnail.png").write_text("")
    return td


def case1_normal():
    print("\n=== Case 1: 정상 폴더 ===")
    with tempfile.TemporaryDirectory() as td:
        folder = _make_normal_folder(Path(td))
        inputs = discover_inputs(folder)
        body = build_body(inputs.metadata, inputs.i18n, "private")
        print(f"  video: {inputs.video.name}")
        print(f"  thumbnail: {inputs.thumbnail.name if inputs.thumbnail else None}")
        print(f"  localizations keys: {sorted(body['localizations'].keys())}")
        print(f"  snippet.title: {body['snippet']['title']}")
        print(f"  snippet.tags: {body['snippet']['tags']}")
        print(f"  snippet.defaultLanguage: {body['snippet']['defaultLanguage']}")
        print(f"  status.privacyStatus: {body['status']['privacyStatus']}")
        print(f"  '_source_hash' filtered out: {'_source_hash' not in body['localizations']}")
        print("  ✅ PASS" if (
            inputs.thumbnail and inputs.thumbnail.name == "thumbnail.png"
            and "_source_hash" not in body["localizations"]
            and set(body["localizations"].keys()) == {"ko", "en", "ja"}
            and body["snippet"]["categoryId"] == "10"
            and body["status"]["selfDeclaredMadeForKids"] is False
        ) else "  ❌ FAIL")


def case2_metadata_missing():
    print("\n=== Case 2: metadata.json 누락 ===")
    with tempfile.TemporaryDirectory() as td:
        folder = Path(td)
        (folder / "video1.mp4").write_text("")
        try:
            discover_inputs(folder)
            print("  ❌ FAIL: 예외 없음")
        except InputError as e:
            msg = str(e)
            ok = "metadata.json이 없습니다" in msg and "해결" in msg
            print(f"  message preview: {msg.splitlines()[0]}")
            print("  ✅ PASS" if ok else "  ❌ FAIL: 메시지 형식")


def case3_two_videos():
    print("\n=== Case 3: 영상 파일 2개 ===")
    with tempfile.TemporaryDirectory() as td:
        folder = _make_normal_folder(Path(td))
        (folder / "video2.mp4").write_text("")
        try:
            discover_inputs(folder)
            print("  ❌ FAIL: 예외 없음")
        except InputError as e:
            msg = str(e)
            ok = "2개 발견" in msg and "video1.mp4" in msg and "video2.mp4" in msg
            print(f"  message preview: {msg.splitlines()[0]}")
            print("  ✅ PASS" if ok else "  ❌ FAIL")


def case4_no_thumbnail():
    print("\n=== Case 4: 썸네일 없음 (자동 탐지 실패) ===")
    with tempfile.TemporaryDirectory() as td:
        folder = _make_normal_folder(Path(td))
        (folder / "thumbnail.png").unlink()  # 썸네일 제거
        inputs = discover_inputs(folder)
        print(f"  thumbnail: {inputs.thumbnail}")
        print("  ✅ PASS" if inputs.thumbnail is None else "  ❌ FAIL")


def case5_i18n_missing_ko():
    print("\n=== Case 5: metadata_i18n.json에 'ko' 키 없음 ===")
    with tempfile.TemporaryDirectory() as td:
        folder = _make_normal_folder(Path(td))
        (folder / "metadata_i18n.json").write_text(
            json.dumps({"_source_hash": "x", "en": {"title": "x", "description": "x"}}),
            encoding="utf-8",
        )
        try:
            discover_inputs(folder)
            print("  ❌ FAIL: 예외 없음")
        except InputError as e:
            msg = str(e)
            ok = "'ko' 키가 없습니다" in msg
            print(f"  message preview: {msg.splitlines()[0]}")
            print("  ✅ PASS" if ok else "  ❌ FAIL")


def case6_dry_run_payload():
    print("\n=== Case 6: --no-thumbnail + privacy unlisted (페이로드 검증) ===")
    with tempfile.TemporaryDirectory() as td:
        folder = _make_normal_folder(Path(td))
        inputs = discover_inputs(folder, no_thumbnail=True)
        body = build_body(inputs.metadata, inputs.i18n, "unlisted")
        print(f"  thumbnail (no_thumbnail=True): {inputs.thumbnail}")
        print(f"  status.privacyStatus: {body['status']['privacyStatus']}")
        ok = inputs.thumbnail is None and body["status"]["privacyStatus"] == "unlisted"
        print("  ✅ PASS" if ok else "  ❌ FAIL")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    case1_normal()
    case2_metadata_missing()
    case3_two_videos()
    case4_no_thumbnail()
    case5_i18n_missing_ko()
    case6_dry_run_payload()
