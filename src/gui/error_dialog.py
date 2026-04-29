"""친절한 에러 안내 다이얼로그.

각 카테고리별 한국어 안내 + 액션 버튼을 다크 테마로 표시.

흐름:
    upload_worker.error(category, message) → main_window가 ErrorDialog 표시
    → 사용자가 [환경 설정 다시 하기] 클릭 시 main_window 콜백으로 마법사 재실행
"""
from __future__ import annotations

import webbrowser
from collections.abc import Callable

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

GCP_CONSOLE_URL = "https://console.cloud.google.com"
GEMINI_AISTUDIO_URL = "https://aistudio.google.com/apikey"


class ErrorCategory:
    """문자열 식별자 — Qt Signal(str, str)로 전달 가능."""

    INPUT = "INPUT"
    NO_CREDENTIALS = "NO_CREDENTIALS"
    AUTH_INVALID = "AUTH_INVALID"
    PERMISSION_DENIED = "PERMISSION_DENIED"   # OAuth 단계: 테스트 사용자 등록 안 됨
    FORBIDDEN = "FORBIDDEN"                   # videos.update 단계: 계정 불일치 OR 비소유 영상
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    VIDEO_NOT_FOUND = "VIDEO_NOT_FOUND"
    GEMINI_API = "GEMINI_API"                          # 일반 Gemini 호출 실패 (재시도 후)
    GEMINI_API_KEY_INVALID = "GEMINI_API_KEY_INVALID"  # 400 API_KEY_INVALID / 만료
    NETWORK = "NETWORK"
    UNKNOWN = "UNKNOWN"


# (title, body_template, buttons)
# buttons: list of (label, action_key, role)
#   action_key: "wizard" | "console" | "close"
#   role: "primary" | None
_PRESETS: dict[str, tuple[str, str, list[tuple[str, str, str | None]]]] = {
    ErrorCategory.INPUT: (
        "⚠️ 입력 확인 필요",
        "{detail}",
        [("확인", "close", "primary")],
    ),
    ErrorCategory.NO_CREDENTIALS: (
        "🔑 인증 파일을 찾을 수 없어요",
        "환경 설정 마법사를 다시 진행해서 credentials.json 파일을 등록해주세요.\n\n"
        "— 상세 —\n{detail}",
        [
            ("환경 설정 다시 하기", "wizard", "primary"),
            ("닫기", "close", None),
        ],
    ),
    ErrorCategory.AUTH_INVALID: (
        "🔑 인증이 만료됐어요",
        "다시 로그인이 필요해요. 환경 설정에서 진행해주세요.\n\n"
        "— 상세 —\n{detail}",
        [
            ("환경 설정 다시 하기", "wizard", "primary"),
            ("닫기", "close", None),
        ],
    ),
    ErrorCategory.PERMISSION_DENIED: (
        "🔐 Google 권한 설정이 필요해요",
        "Google Cloud Console에서 본인 이메일을 '테스트 사용자'로 등록해야 해요!\n\n"
        "📋 해결 방법:\n"
        "  1. Google Cloud Console 접속\n"
        "  2. API 및 서비스 → OAuth 동의 화면\n"
        "  3. '테스트 사용자' 섹션 → '+ 사용자 추가'\n"
        "  4. 본인 Gmail 입력 → 저장\n"
        "  5. 앱에서 다시 시도!\n\n"
        "— 상세 —\n{detail}",
        [
            ("Google Cloud Console 열기", "console", "primary"),
            ("환경 설정 다시 하기", "wizard", None),
            ("닫기", "close", None),
        ],
    ),
    ErrorCategory.FORBIDDEN: (
        "🚫 권한이 부족해요",
        "두 가지 확인해주세요!\n\n"
        "1️⃣  Google 계정이 같은지?\n"
        "    Google Cloud에서 '테스트 사용자'로 등록한 계정과\n"
        "    앱에서 로그인한 계정이 같아야 해요!\n\n"
        "2️⃣  본인 영상인지?\n"
        "    입력한 영상이 본인 채널 영상인가요?\n"
        "    다른 사람 영상은 수정 못 해요!\n\n"
        "환경 설정에서 다시 인증해주세요.\n"
        "⚠️  본인 유튜브 채널 이메일로 로그인!\n\n"
        "— 상세 —\n{detail}",
        [
            ("환경 설정 다시 하기", "wizard", "primary"),
            ("Google Cloud Console 열기", "console", None),
            ("닫기", "close", None),
        ],
    ),
    ErrorCategory.QUOTA_EXCEEDED: (
        "📊 오늘 사용량 한도 초과",
        "오늘 YouTube 사용량 한도(10,000)를 다 썼어요.\n"
        "내일 다시 시도해주세요! (한국 시간 오후 4시 리셋)\n\n"
        "— 상세 —\n{detail}",
        [("확인", "close", "primary")],
    ),
    ErrorCategory.VIDEO_NOT_FOUND: (
        "🎥 영상을 찾을 수 없어요",
        "URL이 정확한지, 본인 채널 영상인지 확인해주세요.\n\n"
        "— 상세 —\n{detail}",
        [("확인", "close", "primary")],
    ),
    ErrorCategory.GEMINI_API: (
        "🤖 AI 번역 실패",
        "Gemini API 키를 다시 확인해주세요.\n"
        "(키 형식이 잘못됐거나 무료 한도가 초과됐을 수 있어요)\n\n"
        "— 상세 —\n{detail}",
        [
            ("환경 설정 다시 하기", "wizard", "primary"),
            ("닫기", "close", None),
        ],
    ),
    ErrorCategory.GEMINI_API_KEY_INVALID: (
        "🔑 Gemini API 키가 만료됐어요",
        "Gemini API 키가 만료됐거나 유효하지 않아요!\n\n"
        "📋 해결 방법:\n"
        "  1. Google AI Studio 접속\n"
        "     (aistudio.google.com/apikey)\n"
        "  2. 기존 키 삭제\n"
        "  3. 'Create API key' → 새 키 발급\n"
        "  4. 키 복사\n"
        "  5. 환경 설정에서 새 키로 변경!\n\n"
        "— 상세 —\n{detail}",
        [
            ("Google AI Studio 열기", "ai_studio", "primary"),
            ("환경 설정 다시 하기", "wizard", None),
            ("닫기", "close", None),
        ],
    ),
    ErrorCategory.NETWORK: (
        "🌐 인터넷 연결 확인",
        "인터넷 연결 후 다시 시도해주세요.\n\n"
        "— 상세 —\n{detail}",
        [("확인", "close", "primary")],
    ),
    ErrorCategory.UNKNOWN: (
        "⚠️ 오류가 발생했어요",
        "이 메시지를 캡처해서 제이린쌤에게 문의해주세요.\n\n"
        "— 상세 —\n{detail}",
        [("확인", "close", "primary")],
    ),
}


class ErrorDialog(QDialog):
    """카테고리 기반 친절한 에러 다이얼로그.

    Args:
        parent: 부모 위젯 (보통 MainWindow)
        category: ErrorCategory 상수
        detail: 원본 에러 메시지

    사용 후 ``self.requested_wizard`` 가 True면 호출자가 마법사를 다시 띄움.
    """

    def __init__(
        self,
        parent: QWidget | None,
        category: str,
        detail: str,
        modal: bool = True,
    ) -> None:
        super().__init__(parent)
        self.requested_wizard = False

        title, body_template, buttons = _PRESETS.get(
            category, _PRESETS[ErrorCategory.UNKNOWN]
        )
        body = body_template.format(detail=(detail or "(상세 정보 없음)").strip())

        self.setWindowTitle("J-LIN Studio")
        self.setModal(modal)
        self.setMinimumWidth(540)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(14)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("panelTitle")
        title_lbl.setWordWrap(True)
        root.addWidget(title_lbl)

        body_view = QTextEdit()
        body_view.setObjectName("logArea")
        body_view.setReadOnly(True)
        body_view.setPlainText(body)
        body_view.setMinimumHeight(200)
        root.addWidget(body_view)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        for label, action_key, role in buttons:
            btn = QPushButton(label)
            if role == "primary":
                btn.setProperty("role", "primary")
                btn.setMinimumHeight(40)
            btn.clicked.connect(
                lambda _checked=False, a=action_key: self._on_action(a)
            )
            btn_row.addWidget(btn)
        root.addLayout(btn_row)

    def _on_action(self, action_key: str) -> None:
        if action_key == "console":
            webbrowser.open(GCP_CONSOLE_URL)
            return
        if action_key == "ai_studio":
            webbrowser.open(GEMINI_AISTUDIO_URL)
            return
        if action_key == "wizard":
            self.requested_wizard = True
            self.accept()
            return
        self.reject()


# ===== 분류 헬퍼 =====

def classify_auth_error(message: str) -> str:
    """AuthError 메시지에서 카테고리 추정.

    PERMISSION_DENIED 패턴(테스트 사용자 미등록 / 사용자 동의 거부):
        - oauthlib AccessDeniedError → str()에 "(access_denied)" 포함
        - 일부 SDK는 공백 형태("access denied")로 직렬화
        - Google "이 앱은 차단됨" / "Access blocked" 페이지의 메시지
        - 한글 노출("테스트 사용자", "접근 차단")
        - "user denied" / "consent ... denied" 변형
    """
    if not message:
        return ErrorCategory.AUTH_INVALID
    m = message.lower()
    if "credentials.json" in m and ("없" in message or "not found" in m):
        return ErrorCategory.NO_CREDENTIALS
    permission_patterns = (
        "access_denied",
        "access denied",
        "test user",
        "test_user",
        "테스트 사용자",
        "접근 차단",
        "this app is blocked",
        "access blocked",
        "not verified",
        "user denied",
        "consent denied",
    )
    if any(p in m or p in message for p in permission_patterns):
        return ErrorCategory.PERMISSION_DENIED
    if "invalid_grant" in m or "토큰" in message or "refresh" in m:
        return ErrorCategory.AUTH_INVALID
    return ErrorCategory.AUTH_INVALID


def classify_gemini_error(message: str) -> str:
    """Gemini SDK 예외/메시지에서 카테고리 추정.

    400 API_KEY_INVALID / 만료 패턴이면 GEMINI_API_KEY_INVALID,
    그 외 Gemini 호출 실패는 GEMINI_API.
    """
    if not message:
        return ErrorCategory.GEMINI_API
    m = message.lower()
    if (
        "api key expired" in m
        or "api_key_invalid" in m
        or "renew the api key" in m
        or "api key not valid" in m
        or ("generativelanguage.googleapis.com" in m and "400" in m)
    ):
        return ErrorCategory.GEMINI_API_KEY_INVALID
    return ErrorCategory.GEMINI_API


def classify_http_status(status: int, reason: str) -> str:
    """YouTube API HTTP status + reason → 카테고리.

    403 두 갈래:
        - reason="forbidden"     → FORBIDDEN (videos.update 단계: 계정 불일치 / 비소유)
        - 그 외 403              → PERMISSION_DENIED (드물게 OAuth 직후 권한 부족)
        ※ '테스트 사용자 미등록'은 OAuth 흐름에서 access_denied로 잡혀 PERMISSION_DENIED 분류됨
    """
    reason_l = (reason or "").lower()
    if status == 401:
        return ErrorCategory.AUTH_INVALID
    if status == 403:
        if reason in ("quotaExceeded", "uploadLimitExceeded", "rateLimitExceeded"):
            return ErrorCategory.QUOTA_EXCEEDED
        if reason in ("forbidden",) or "forbidden" in reason_l:
            return ErrorCategory.FORBIDDEN
        return ErrorCategory.PERMISSION_DENIED
    if status == 404 or reason in ("videoNotFound", "notFound"):
        return ErrorCategory.VIDEO_NOT_FOUND
    return ErrorCategory.UNKNOWN
