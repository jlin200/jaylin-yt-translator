"""OAuth 2.0 Installed App Flow + token.json 관리 (SPEC-UPLOAD-001 T3, REQ-01~03).

호텔 마스터키 비유:
    - credentials.json  = 호텔 신분증 (앱이 누구인지)
    - 사용자 동의       = 프론트에서 마스터키 발급 허락
    - token.json        = 임시 마스터키 (access + refresh)
    - access_token      = 객실 키카드 (1시간) — API 호출 시 첨부
    - refresh_token     = 프론트 출입증 (장기) — 만료된 객실키 갱신용

함수:
    get_credentials() : 토큰 캐시 + 자동 갱신 + 신규 인증 (브라우저 열림)
    delete_token()    : 401 핸들러용
"""
from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .errors import AuthError

SCOPES = ["https://www.googleapis.com/auth/youtube"]
"""REQ-01: 단일 youtube scope (업로드 + localizations + 메타 수정 모두 가능)."""

# 프로젝트 루트 기준 (cli.main()이 cwd=프로젝트 루트로 호출됨 가정)
DEFAULT_CREDENTIALS_PATH = Path("credentials.json")
DEFAULT_TOKEN_PATH = Path("token.json")


def get_credentials(
    credentials_path: Path = DEFAULT_CREDENTIALS_PATH,
    token_path: Path = DEFAULT_TOKEN_PATH,
) -> Credentials:
    """OAuth 자격증명 가져오기 (토큰 캐시 + 자동 갱신).

    흐름 (REQ-02, REQ-03):
        1) token.json 있으면 로드 → valid면 그대로 반환
        2) expired + refresh_token 있으면 자동 갱신 → token.json 갱신 저장
        3) 그 외 (없거나 refresh 실패) → InstalledAppFlow (브라우저 자동 열림) → 저장

    Raises:
        AuthError: credentials.json 누락, refresh_token 만료(refresh 실패).
    """
    creds: Credentials | None = None

    # 1) 캐시 토큰 로드 시도
    if token_path.is_file():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except (ValueError, KeyError) as e:
            # token.json 손상 / 형식 오류 → 무시하고 신규 인증으로
            print(f"[auth] token.json 로드 실패 ({e}) — 신규 인증 진행")
            creds = None

    # 2) 유효한 토큰이면 즉시 반환
    if creds and creds.valid:
        return creds

    # 3) 만료 + refresh_token 있으면 자동 갱신
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds, token_path)
            return creds
        except Exception as e:
            # refresh_token 만료 / 취소 등
            raise AuthError(
                f"토큰 갱신 실패: {e}\n"
                f"해결: token.json 삭제 후 다시 실행하세요 ({token_path.resolve()})"
            ) from e

    # 4) 신규 인증 (브라우저 자동 열림)
    if not credentials_path.is_file():
        raise AuthError(
            f"credentials.json이 없습니다: {credentials_path.resolve()}\n"
            "해결:\n"
            "  1) Google Cloud Console (console.cloud.google.com) 접속\n"
            "  2) API 및 서비스 → 사용자 인증 정보\n"
            "  3) OAuth 2.0 클라이언트 ID 만들기 → 애플리케이션 유형: 데스크톱 앱\n"
            "  4) JSON 다운로드 후 프로젝트 루트에 credentials.json으로 저장"
        )

    print("[auth] 브라우저로 OAuth 인증을 진행합니다...")
    print("[auth] (Plimate 채널 소유 계정으로 로그인 + 동의해 주세요)")
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(creds, token_path)
    print(f"[auth] 인증 완료. 토큰 저장 → {token_path.resolve()}")
    return creds


def delete_token(token_path: Path = DEFAULT_TOKEN_PATH) -> bool:
    """token.json 삭제 (401 에러 핸들러용).

    Returns:
        True = 삭제됨, False = 원래 없었음.
    """
    if token_path.is_file():
        token_path.unlink()
        return True
    return False


def _save_token(creds: Credentials, token_path: Path) -> None:
    """token.json 저장 (UTF-8). SEC-02: 토큰 내용은 stdout에 출력 안 함."""
    token_path.write_text(creds.to_json(), encoding="utf-8")
