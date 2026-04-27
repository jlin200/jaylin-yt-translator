"""`python -m src.upload ...` 진입점.

Windows cp949 stdout 회피 + .env 자동 로드.
실제 흐름은 cli.main()에서.
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# .env 로드 (i18n과 공유. 향후 확장용 — 현재 OAuth는 credentials.json/token.json 사용)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .cli import main

sys.exit(main())
