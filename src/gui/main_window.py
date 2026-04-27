"""J-LIN Studio 메인 윈도우 — URL 기반 메타데이터 갱신 워크플로우.

3구역 레이아웃:
    상단 히어로 (로고 + 제목/부제, 평면 + 하단 보더)
    중간 좌/우 패널 (입력 폼 / 현재 상태)
    하단 작업 로그
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import style
from .paths import resource_path
from .upload_worker import UpdateWorker


# (display, value, hint) — value는 SPEC-I18N-001 --tier 인자에 그대로 전달
TIER_OPTIONS: list[tuple[str, str, str]] = [
    ("Tier 1 · 핵심 6개", "1", "en, ja, th, vi, zh-TW, pt-BR"),
    ("Tier 2 · 21개", "2", "Tier 1 + 유럽/아시아 주요 언어"),
    ("Tier 3 · 전체 50개", "all", "전 세계 주요 50개 언어"),
]


def _label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("role", "label")
    return lbl


def _panel() -> tuple[QFrame, QVBoxLayout]:
    panel = QFrame()
    panel.setObjectName("panel")
    inner = QVBoxLayout(panel)
    inner.setContentsMargins(20, 18, 20, 18)
    inner.setSpacing(12)
    return panel, inner


def _stat_card(label: str, value: str) -> tuple[QFrame, QLabel]:
    card = QFrame()
    card.setObjectName("statCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(4)

    lbl = QLabel(label.upper())
    lbl.setProperty("role", "stat-label")
    layout.addWidget(lbl)

    val = QLabel(value)
    val.setProperty("role", "stat-value")
    layout.addWidget(val)
    return card, val


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("J-LIN Studio")
        self.resize(1100, 800)
        self.setAcceptDrops(True)

        # 결과 상태
        self._video_id: str | None = None
        self._studio_url: str | None = None
        self._watch_url: str | None = None
        self._thread: QThread | None = None
        self._worker: UpdateWorker | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        root.addWidget(self._build_hero())

        middle = QHBoxLayout()
        middle.setSpacing(16)
        middle.addWidget(self._build_settings_panel(), stretch=1)
        middle.addWidget(self._build_status_panel(), stretch=1)
        root.addLayout(middle, stretch=1)

        root.addWidget(self._build_log_panel())

        self.setCentralWidget(central)

    # ===== Hero =====

    def _build_hero(self) -> QFrame:
        hero = QFrame()
        hero.setObjectName("hero")
        hero.setFixedHeight(120)

        layout = QHBoxLayout(hero)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(20)

        logo_label = QLabel()
        logo_label.setObjectName("heroLogo")
        logo_label.setFixedSize(80, 80)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_path = resource_path("src/gui/assets/logo.png")
        if logo_path.is_file():
            pixmap = QPixmap(str(logo_path))
            logo_label.setPixmap(
                pixmap.scaled(
                    80, 80,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(logo_label)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        text_col.setContentsMargins(0, 4, 0, 4)
        text_col.addStretch()

        title = QLabel("J-LIN Studio")
        title.setObjectName("heroTitle")
        text_col.addWidget(title)

        sub = QLabel("창작자를 위한 영상 번역 · 업로드 워크스페이스")
        sub.setObjectName("heroSubtitle")
        text_col.addWidget(sub)

        text_col.addStretch()
        layout.addLayout(text_col, stretch=1)
        return hero

    # ===== 좌측: 설정 (URL/제목/본문/tier) =====

    def _build_settings_panel(self) -> QFrame:
        panel, inner = _panel()

        title = QLabel("설정")
        title.setObjectName("panelTitle")
        inner.addWidget(title)

        # 유튜브 영상 주소
        inner.addWidget(_label("유튜브 영상 주소"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("URL 또는 영상 ID 붙여넣기")
        inner.addWidget(self.url_input)

        # 유튜브 제목
        inner.addWidget(_label("유튜브 제목"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("한국어 제목")
        inner.addWidget(self.title_input)

        # 유튜브 본문
        inner.addWidget(_label("유튜브 본문"))
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("한국어 설명")
        self.description_input.setFixedHeight(140)
        inner.addWidget(self.description_input)

        # 번역 언어
        inner.addWidget(_label("번역 언어"))
        self.tier_combo = QComboBox()
        for label, _, _ in TIER_OPTIONS:
            self.tier_combo.addItem(label)
        self.tier_combo.currentIndexChanged.connect(self._on_tier_changed)
        inner.addWidget(self.tier_combo)
        self.tier_hint = QLabel(TIER_OPTIONS[0][2])
        self.tier_hint.setProperty("role", "hint")
        inner.addWidget(self.tier_hint)

        inner.addStretch()

        # Primary 버튼
        self.start_btn = QPushButton("번역 및 자동 업로드 시작")
        self.start_btn.setProperty("role", "primary")
        self.start_btn.setMinimumHeight(48)
        self.start_btn.clicked.connect(self._on_start_clicked)
        inner.addWidget(self.start_btn)

        # 환경 설정 (작게, 보조)
        self.settings_btn = QPushButton("환경 설정")
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        inner.addWidget(self.settings_btn)

        return panel

    # ===== 우측: 현재 상태 =====

    def _build_status_panel(self) -> QFrame:
        panel, inner = _panel()

        title = QLabel("현재 상태")
        title.setObjectName("panelTitle")
        inner.addWidget(title)

        badge_row = QHBoxLayout()
        self.status_badge = QLabel("대기 중")
        self.status_badge.setProperty("role", "status-large")
        badge_row.addWidget(self.status_badge)
        badge_row.addStretch()
        inner.addLayout(badge_row)

        self.progress_pct_large = QLabel("0%")
        self.progress_pct_large.setProperty("role", "progress-large")
        inner.addWidget(self.progress_pct_large)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.valueChanged.connect(
            lambda v: self.progress_pct_large.setText(f"{v}%")
        )
        inner.addWidget(self.progress_bar)

        self.current_task = QLabel("작업이 시작되면 여기에 표시됩니다")
        self.current_task.setProperty("role", "current-task")
        inner.addWidget(self.current_task)

        inner.addStretch()

        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)

        today_card, self.today_value = _stat_card("오늘 처리", "0")
        stats_row.addWidget(today_card, stretch=1)

        quota_card, self.quota_value = _stat_card("사용 쿼터", "0 / 10K")
        stats_row.addWidget(quota_card, stretch=1)

        eta_card, self.eta_value = _stat_card("예상 완료", "—")
        stats_row.addWidget(eta_card, stretch=1)

        inner.addLayout(stats_row)
        return panel

    # ===== 하단: 작업 로그 =====

    def _build_log_panel(self) -> QFrame:
        panel, inner = _panel()

        title_row = QHBoxLayout()
        title = QLabel("작업 로그")
        title.setObjectName("panelTitle")
        title_row.addWidget(title)
        title_row.addStretch()

        self.open_studio_btn = QPushButton("YouTube Studio 열기")
        self.open_studio_btn.setEnabled(False)
        self.open_studio_btn.clicked.connect(self._on_open_studio)
        title_row.addWidget(self.open_studio_btn)

        self.open_watch_btn = QPushButton("영상 보기")
        self.open_watch_btn.setEnabled(False)
        self.open_watch_btn.clicked.connect(self._on_open_watch)
        title_row.addWidget(self.open_watch_btn)

        inner.addLayout(title_row)

        self.result_area = QTextEdit()
        self.result_area.setObjectName("logArea")
        self.result_area.setReadOnly(True)
        self.result_area.setPlaceholderText("작업 결과가 여기에 표시됩니다")
        self.result_area.setFixedHeight(200)
        inner.addWidget(self.result_area)

        return panel

    # ===== 슬롯: UI =====

    def _on_tier_changed(self, idx: int) -> None:
        self.tier_hint.setText(TIER_OPTIONS[idx][2])

    def _on_settings_clicked(self) -> None:
        self._append_log("[T2 placeholder] 환경 설정 마법사는 T3에서 통합됩니다.")

    def _on_open_studio(self) -> None:
        if self._studio_url:
            QDesktopServices.openUrl(QUrl(self._studio_url))

    def _on_open_watch(self) -> None:
        if self._watch_url:
            QDesktopServices.openUrl(QUrl(self._watch_url))

    # ===== 시작 + Worker 통합 =====

    def _on_start_clicked(self) -> None:
        url = self.url_input.text().strip()
        title = self.title_input.text().strip()
        description = self.description_input.toPlainText().strip()
        tier = TIER_OPTIONS[self.tier_combo.currentIndex()][1]

        # 입력 검증
        if not url:
            self._show_error("유튜브 영상 주소를 입력하세요.")
            return
        if not title:
            self._show_error("유튜브 제목을 입력하세요.")
            return
        if not description:
            self._show_error("유튜브 본문을 입력하세요.")
            return

        # UI 잠금 + 초기화
        self._lock_ui(True)
        self._set_badge("진행 중", "status-active")
        self.result_area.clear()
        self.progress_bar.setValue(0)
        self.open_studio_btn.setEnabled(False)
        self.open_watch_btn.setEnabled(False)
        self.current_task.setText("작업 시작 중...")
        self._append_log(f"[{_now()}] 🎬 작업 시작")

        # Worker 시작 (QThread + signal/slot)
        self._thread = QThread()
        self._worker = UpdateWorker(url, title, description, tier)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress_bar.setValue)
        self._worker.stage.connect(self._on_worker_stage)
        self._worker.log.connect(self._on_worker_log)
        self._worker.done.connect(self._on_worker_done)
        self._worker.error.connect(self._on_worker_error)

        self._worker.done.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    # ===== 슬롯: Worker → UI =====

    def _on_worker_stage(self, text: str) -> None:
        self.current_task.setText(text)

    def _on_worker_log(self, text: str) -> None:
        self._append_log(f"[{_now()}] {text}")

    def _on_worker_done(self, result: dict) -> None:
        self._video_id = result["video_id"]
        self._studio_url = result["studio_url"]
        self._watch_url = result["watch_url"]
        langs = result["languages"]
        self._set_badge("완료", "status-success")
        self.current_task.setText("업데이트 완료")
        self._append_log(
            f"\n[{_now()}] ✅ 업데이트 완료\n"
            f"        videoId   : {self._video_id}\n"
            f"        언어 등록  : {len(langs)}개 ({', '.join(langs)})\n"
            f"        토큰 사용  : {result['tokens_in']:,} in / {result['tokens_out']:,} out\n"
            f"        스튜디오  : {self._studio_url}"
        )
        self.open_studio_btn.setEnabled(True)
        self.open_watch_btn.setEnabled(True)
        self._lock_ui(False)

    def _on_worker_error(self, msg: str) -> None:
        self._set_badge("오류", "status-error")
        self.current_task.setText("오류 발생")
        self._append_log(f"[{_now()}] ❌ {msg}")
        self._lock_ui(False)

    # ===== 헬퍼 =====

    def _lock_ui(self, locked: bool) -> None:
        self.start_btn.setEnabled(not locked)
        self.settings_btn.setEnabled(not locked)
        self.url_input.setEnabled(not locked)
        self.title_input.setEnabled(not locked)
        self.description_input.setEnabled(not locked)
        self.tier_combo.setEnabled(not locked)

    def _set_badge(self, text: str, role: str) -> None:
        self.status_badge.setText(text)
        self.status_badge.setProperty("role", role)
        # property 변경 시 스타일 재계산
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

    def _append_log(self, text: str) -> None:
        self.result_area.append(text)

    def _show_error(self, msg: str) -> None:
        self._append_log(f"[{_now()}] ❌ {msg}")

    # ===== Drag and Drop (URL 텍스트 받기) =====

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        md = event.mimeData()
        if md.hasText() or md.hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        md = event.mimeData()
        # 1) 텍스트 (URL 복붙)
        if md.hasText():
            text = md.text().strip()
            if text:
                self.url_input.setText(text)
                event.acceptProposedAction()
                return
        # 2) URL 객체 (브라우저에서 끌어다 놓기)
        if md.hasUrls():
            for url in md.urls():
                url_str = url.toString()
                if "youtube.com" in url_str or "youtu.be" in url_str:
                    self.url_input.setText(url_str)
                    event.acceptProposedAction()
                    return
        event.ignore()


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")
