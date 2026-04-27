"""T3 수동 검증 — OAuth flow 실전 호출.

실행:
    python -m tests.smoke_auth

첫 실행: 브라우저 열림 → 동의 → token.json 생성
두 번째: 즉시 valid 반환 (브라우저 안 열림)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# .env 로드 (안 쓰지만 일관성)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.upload.auth import DEFAULT_TOKEN_PATH, get_credentials


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    token_existed = DEFAULT_TOKEN_PATH.is_file()
    print(f"[smoke] token.json 존재 여부 (실행 전): {token_existed}")

    creds = get_credentials()

    print(f"[smoke] creds.valid: {creds.valid}")
    print(f"[smoke] creds.expired: {creds.expired}")
    print(f"[smoke] creds.has_refresh_token: {creds.refresh_token is not None}")
    print(f"[smoke] creds.scopes: {creds.scopes}")

    # SEC-02: access_token / refresh_token 자체는 출력 안 함. 길이만 확인.
    if creds.token:
        print(f"[smoke] access_token length: {len(creds.token)} chars (값은 미출력)")

    # token.json 내용 검증 (민감 정보 미출력)
    if DEFAULT_TOKEN_PATH.is_file():
        data = json.loads(DEFAULT_TOKEN_PATH.read_text(encoding="utf-8"))
        keys = sorted(data.keys())
        print(f"[smoke] token.json 키 목록: {keys}")
        # token.json에는 token, refresh_token, scopes, client_id 등 들어감 — 정상

    print("[smoke] ✅ OAuth 인증 완료. 두 번째 실행 시 브라우저 안 열림 검증해 보세요.")


if __name__ == "__main__":
    main()
