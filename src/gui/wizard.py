"""J-LIN Studio 첫 실행 설정 마법사 (SPEC-GUI-001 T3).

3단계:
    1) 환영 + 안내
    2) Google OAuth credentials.json 등록
    3) Gemini API 키 입력

완료 시 %APPDATA%/jaylin-yt-translator/에 저장:
    - credentials.json  (사용자 선택 파일 복사)
    - .env (GEMINI_API_KEY=...)

사용자가 X 닫으면 reject() → 앱 종료.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import paths

GCP_CONSOLE_URL = "https://console.cloud.google.com"
GEMINI_AISTUDIO_URL = "https://aistudio.google.com/apikey"
GUIDE_VIDEO_URL = "https://example.com/jaylin-guide"  # placeholder


def needs_setup() -> bool:
    """credentials.json + GEMINI_API_KEY 둘 다 APPDATA에 있는지 체크.

    Returns:
        True  = 마법사 필요 (적어도 하나 부재)
        False = 둘 다 있음, 메인 화면 진행 OK
    """
    creds_ok = paths.credentials_path().is_file()
    env_p = paths.env_path()
    key_ok = False
    if env_p.is_file():
        try:
            text = env_p.read_text(encoding="utf-8")
            key_ok = "GEMINI_API_KEY=" in text
        except OSError:
            key_ok = False
    return not (creds_ok and key_ok)


class SetupWizard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("J-LIN Studio 환경 설정")
        self.setModal(True)
        self.resize(720, 600)

        self._credentials_validated = False
        self._gemini_key_validated = False

        self._build_ui()

    # ===== UI =====

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        # 단계 표시 (1/3, 2/3, 3/3)
        self.step_label = QLabel("1 / 3")
        self.step_label.setProperty("role", "label")
        self.step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.step_label)

        # 페이지 전환
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_page_welcome())
        self.stack.addWidget(self._build_page_oauth())
        self.stack.addWidget(self._build_page_gemini())
        root.addWidget(self.stack, stretch=1)

        # 네비게이션
        nav = QHBoxLayout()
        self.back_btn = QPushButton("← 이전")
        self.back_btn.clicked.connect(self._on_back)
        nav.addWidget(self.back_btn)
        nav.addStretch()
        self.next_btn = QPushButton("시작 →")
        self.next_btn.setProperty("role", "primary")
        self.next_btn.setMinimumWidth(140)
        self.next_btn.clicked.connect(self._on_next)
        nav.addWidget(self.next_btn)
        root.addLayout(nav)

        self._update_nav()

    def _build_page_welcome(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)
        layout.addStretch()

        title = QLabel("J-LIN Studio에 오신 걸 환영합니다")
        title.setObjectName("heroTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("처음 사용하시려면 2가지 키 발급이 필요합니다")
        sub.setObjectName("heroSubtitle")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        layout.addSpacing(28)

        body = QLabel(
            "1️⃣  Google OAuth (credentials.json) — YouTube 업로드용\n\n"
            "2️⃣  Gemini API 키 — AI 번역용\n\n"
            "각 단계마다 가이드 링크를 제공합니다."
        )
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(body)

        layout.addStretch()
        return w

    def _build_page_oauth(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        title = QLabel("Google OAuth 발급")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        steps = QLabel(
            "1.  Google Cloud Console 접속\n"
            "2.  새 프로젝트 생성\n"
            "3.  YouTube Data API v3 활성화\n"
            "4.  OAuth 동의 화면 + 테스트 사용자 등록\n"
            "5.  데스크톱 앱 OAuth 클라이언트 생성 → credentials.json 다운로드"
        )
        layout.addWidget(steps)

        btn_row = QHBoxLayout()
        gcp_btn = QPushButton("Google Cloud Console 열기")
        gcp_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(GCP_CONSOLE_URL))
        )
        btn_row.addWidget(gcp_btn)

        guide_btn = QPushButton("가이드 영상 보기")
        guide_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(GUIDE_VIDEO_URL))
        )
        btn_row.addWidget(guide_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addSpacing(20)

        select_btn = QPushButton("📁  credentials.json 파일 선택")
        select_btn.setMinimumHeight(40)
        select_btn.clicked.connect(self._on_select_credentials)
        layout.addWidget(select_btn)

        self.credentials_status = QLabel("아직 선택되지 않음")
        self.credentials_status.setProperty("role", "hint")
        self.credentials_status.setWordWrap(True)
        layout.addWidget(self.credentials_status)

        layout.addStretch()
        return w

    def _build_page_gemini(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        title = QLabel("Gemini API 키 입력")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        steps = QLabel(
            "1.  Google AI Studio 접속\n"
            "2.  API 키 발급 (무료, 분당 60회 한도)\n"
            "3.  키 복사해서 아래 입력"
        )
        layout.addWidget(steps)

        btn_row = QHBoxLayout()
        ai_btn = QPushButton("Google AI Studio 열기")
        ai_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(GEMINI_AISTUDIO_URL))
        )
        btn_row.addWidget(ai_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addSpacing(16)

        api_label = QLabel("API 키")
        api_label.setProperty("role", "label")
        layout.addWidget(api_label)

        self.gemini_key_input = QLineEdit()
        self.gemini_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_input.setPlaceholderText("AIzaSy로 시작하는 키 붙여넣기")
        self.gemini_key_input.textChanged.connect(self._on_gemini_key_changed)
        layout.addWidget(self.gemini_key_input)

        self.gemini_status = QLabel("키를 입력해 주세요")
        self.gemini_status.setProperty("role", "hint")
        layout.addWidget(self.gemini_status)

        layout.addSpacing(16)

        save_hint = QLabel(
            f"키는 다음 위치에 저장됩니다:\n{paths.env_path()}"
        )
        save_hint.setProperty("role", "hint")
        save_hint.setWordWrap(True)
        layout.addWidget(save_hint)

        layout.addStretch()
        return w

    # ===== 슬롯 =====

    def _on_back(self) -> None:
        i = self.stack.currentIndex()
        if i > 0:
            self.stack.setCurrentIndex(i - 1)
        self._update_nav()

    def _on_next(self) -> None:
        i = self.stack.currentIndex()
        if i < self.stack.count() - 1:
            self.stack.setCurrentIndex(i + 1)
            self._update_nav()
        else:
            self._finish()

    def _update_nav(self) -> None:
        i = self.stack.currentIndex()
        total = self.stack.count()
        self.step_label.setText(f"{i + 1} / {total}")
        self.back_btn.setVisible(i > 0)

        if i == 0:
            self.next_btn.setText("시작 →")
            self.next_btn.setEnabled(True)
        elif i == 1:
            self.next_btn.setText("다음 →")
            self.next_btn.setEnabled(self._credentials_validated)
        elif i == 2:
            self.next_btn.setText("완료")
            self.next_btn.setEnabled(self._gemini_key_validated)

    def _on_select_credentials(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "credentials.json 선택",
            str(Path.home() / "Downloads"),
            "JSON files (*.json)",
        )
        if not path_str:
            return
        path = Path(path_str)
        valid, msg = self._validate_credentials_json(path)
        if not valid:
            self.credentials_status.setText(f"❌ {msg}")
            self._credentials_validated = False
            self._update_nav()
            return

        dest = paths.credentials_path()
        try:
            shutil.copy(path, dest)
        except OSError as e:
            self.credentials_status.setText(f"❌ 파일 복사 실패: {e}")
            self._credentials_validated = False
            self._update_nav()
            return

        self.credentials_status.setText(f"✅ 인증서 등록 완료\n{dest}")
        self._credentials_validated = True
        self._update_nav()

    def _validate_credentials_json(self, path: Path) -> tuple[bool, str]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            return False, f"파일 읽기/파싱 실패: {e}"
        if "installed" not in data:
            return False, (
                "Desktop 앱 OAuth 클라이언트가 아닙니다.\n"
                "Google Cloud Console에서 '데스크톱 앱'으로 다시 발급하세요."
            )
        return True, ""

    def _on_gemini_key_changed(self, text: str) -> None:
        text = text.strip()
        if not text:
            self.gemini_status.setText("키를 입력해 주세요")
            self._gemini_key_validated = False
        elif text.startswith("AIzaSy") and 30 <= len(text) <= 50:
            self.gemini_status.setText(f"✅ 키 형식 확인됨 ({len(text)}자)")
            self._gemini_key_validated = True
        else:
            self.gemini_status.setText(
                "❌ 형식 불일치 — AIzaSy로 시작하는 30~50자 키여야 합니다."
            )
            self._gemini_key_validated = False
        self._update_nav()

    def _finish(self) -> None:
        """3단계 완료 — .env 작성 후 accept()."""
        env_p = paths.env_path()
        key = self.gemini_key_input.text().strip()
        try:
            env_p.write_text(f"GEMINI_API_KEY={key}\n", encoding="utf-8")
        except OSError as e:
            self.gemini_status.setText(f"❌ .env 저장 실패: {e}")
            return
        self.accept()
