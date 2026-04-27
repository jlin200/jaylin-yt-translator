"""`python -m src.i18n ...` 진입점.

Windows cp949 stdout 회피 + .env 자동 로드(GEMINI_API_KEY용).
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# .env 로드 (GEMINI_API_KEY 자동 주입)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv 없으면 os.environ에 이미 있어야 함

from .cli import main

sys.exit(main())
