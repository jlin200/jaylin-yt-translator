"""i18n 모듈 CLI 진입점.

사용:
    python -m src.i18n <폴더>                     # tier all(50)
    python -m src.i18n <폴더> --tier 1            # tier 1만 (6개)
    python -m src.i18n <폴더> --force             # 캐시 무시 강제 재번역

Exit code:
    0 = 성공 (부분 성공 포함)
    1 = GEMINI_API_KEY 누락
    2 = 입력 문제 (폴더 없음, metadata.json 없음)
    4 = Gemini 전체 실패 (1차 0개 또는 JSON 파싱 실패)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import translate_playlist
from .translator import MissingApiKeyError, TranslationError


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.i18n")
    p.add_argument("folder", help="플레이리스트 폴더 (metadata.json 포함)")
    p.add_argument(
        "--tier",
        choices=["1", "2", "3", "all"],
        default="all",
        help="번역할 언어 tier (1=6개 Plimate 핵심, 2=21개, 3/all=50개)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="캐시 무시하고 강제 재번역",
    )
    args = p.parse_args(argv)

    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        print(f"폴더가 아닙니다: {folder}", file=sys.stderr)
        return 2

    try:
        i18n_path = translate_playlist(
            folder,
            tier=args.tier,
            force=args.force,
        )
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2
    except MissingApiKeyError as e:
        print(str(e), file=sys.stderr)
        return 1
    except TranslationError as e:
        print(f"번역 실패: {e}", file=sys.stderr)
        return 4

    print(str(i18n_path))
    return 0
