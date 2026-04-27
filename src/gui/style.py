"""Jaylin Studio 다크 테마 — DaVinci Resolve / Premiere Pro 스타일.

QApplication.setStyleSheet(STYLESHEET)로 일괄 적용.

위젯 식별 패턴:
    히어로:           QFrame#hero, QLabel#heroTitle, QLabel#heroSubtitle
    패널 (좌/우/하):   QFrame#panel, QLabel#panelTitle
    통계 카드:        QFrame#statCard
    역할 라벨:        role="label" / "hint" / "current-task"
                      role="stat-label" / "stat-value"
                      role="progress-large"
                      role="status-large" / "status-active" / "status-success" / "status-error"
    버튼:             role="primary" / "segment" + segpos="left|middle|right"
"""
from __future__ import annotations

# ===== 색상 팔레트 =====
BG = "#0a0a0a"
PANEL = "#141414"
CARD = "#1c1c1c"
CARD_HOVER = "#242424"
BORDER = "#2a2a2a"
BORDER_HOVER = "#3a3a3a"

ACCENT = "#E50914"          # 넷플릭스 빨강
ACCENT_HOVER = "#B81D24"
ACCENT_PRESSED = "#9D1620"

TEXT = "#ffffff"
TEXT_SUB = "#888888"
TEXT_DIM = "#555555"

SUCCESS = "#46D369"
WARNING = "#F5A623"
ERROR = "#E50914"


STYLESHEET = f"""
/* ===== 베이스 ===== */
QMainWindow, QWidget, QDialog {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Segoe UI", "Inter", "Pretendard", sans-serif;
    font-size: 13px;
}}

/* ===== 히어로 (평면 + 하단 보더, 넷플릭스 스타일) ===== */
QFrame#hero {{
    background-color: {BG};
    border: none;
    border-bottom: 1px solid {BORDER};
    border-radius: 0;
}}

QLabel#heroTitle {{
    color: {TEXT};
    font-size: 32px;
    font-weight: 700;
    background: transparent;
    letter-spacing: -0.5px;
}}

QLabel#heroSubtitle {{
    color: {TEXT_SUB};
    font-size: 14px;
    background: transparent;
    font-weight: 400;
}}

/* ===== 패널 ===== */
QFrame#panel {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

QLabel#panelTitle {{
    color: {TEXT};
    font-size: 16px;
    font-weight: 600;
    background: transparent;
}}

/* ===== Stat 카드 ===== */
QFrame#statCard {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

QLabel[role="stat-label"] {{
    color: {TEXT_SUB};
    font-size: 10px;
    font-weight: 600;
    background: transparent;
    letter-spacing: 0.5px;
}}

QLabel[role="stat-value"] {{
    color: {TEXT};
    font-size: 18px;
    font-weight: 600;
    background: transparent;
}}

/* ===== 큰 진행률 ===== */
QLabel[role="progress-large"] {{
    color: {ACCENT};
    font-size: 32px;
    font-weight: 700;
    background: transparent;
    padding: 0;
}}

QLabel[role="current-task"] {{
    color: {TEXT_SUB};
    font-size: 13px;
    background: transparent;
}}

/* ===== 라벨 ===== */
QLabel {{
    color: {TEXT};
    background: transparent;
    font-size: 13px;
}}

QLabel[role="label"] {{
    color: {TEXT_SUB};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}

QLabel[role="hint"] {{
    color: {TEXT_SUB};
    font-size: 12px;
}}

/* ===== 상태 배지 ===== */
QLabel[role="status-large"] {{
    background-color: rgba(136, 136, 136, 0.15);
    color: {TEXT_SUB};
    padding: 6px 14px;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 600;
}}

QLabel[role="status-active"] {{
    background-color: rgba(99, 102, 241, 0.18);
    color: {ACCENT};
    padding: 6px 14px;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 600;
}}

QLabel[role="status-success"] {{
    background-color: rgba(16, 185, 129, 0.18);
    color: {SUCCESS};
    padding: 6px 14px;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 600;
}}

QLabel[role="status-error"] {{
    background-color: rgba(239, 68, 68, 0.18);
    color: {ERROR};
    padding: 6px 14px;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 600;
}}

/* ===== 입력 ===== */
QLineEdit, QComboBox, QTextEdit {{
    background-color: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 10px 12px;
    selection-background-color: {ACCENT};
    selection-color: white;
    font-size: 13px;
}}

QLineEdit:hover, QComboBox:hover {{
    border-color: {BORDER_HOVER};
}}

QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
    border: 1px solid {ACCENT};
}}

QLineEdit::placeholder {{
    color: {TEXT_SUB};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_SUB};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: rgba(99, 102, 241, 0.25);
    selection-color: {TEXT};
    padding: 4px;
    outline: 0;
}}

/* ===== 작업 로그 영역 (monospace) ===== */
QTextEdit#logArea {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 12px;
    font-family: "Consolas", "Cascadia Mono", "Courier New", monospace;
    font-size: 12px;
    color: {TEXT};
}}

/* ===== 버튼 ===== */
QPushButton {{
    background-color: transparent;
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: rgba(255, 255, 255, 0.04);
    border-color: {BORDER_HOVER};
}}

QPushButton:pressed {{
    background-color: rgba(255, 255, 255, 0.08);
}}

QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {BORDER};
    background-color: transparent;
}}

QPushButton[role="primary"] {{
    background-color: {ACCENT};
    color: white;
    border: none;
    font-size: 14px;
    font-weight: 600;
    padding: 14px 24px;
    border-radius: 10px;
}}

QPushButton[role="primary"]:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton[role="primary"]:pressed {{
    background-color: {ACCENT_PRESSED};
}}

QPushButton[role="primary"]:disabled {{
    background-color: #2a2a3a;
    color: {TEXT_DIM};
}}

/* ===== 세그먼트 ===== */
QPushButton[role="segment"] {{
    background-color: {CARD};
    color: {TEXT_SUB};
    border: 1px solid {BORDER};
    border-radius: 0;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 500;
}}

QPushButton[role="segment"][segpos="left"] {{
    border-top-left-radius: 8px;
    border-bottom-left-radius: 8px;
}}

QPushButton[role="segment"][segpos="middle"] {{
    border-left: none;
}}

QPushButton[role="segment"][segpos="right"] {{
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    border-left: none;
}}

QPushButton[role="segment"]:hover {{
    background-color: {CARD_HOVER};
    color: {TEXT};
}}

QPushButton[role="segment"]:checked {{
    background-color: {ACCENT};
    color: white;
    border-color: {ACCENT};
}}

QPushButton[role="segment"]:checked:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}

QLabel#heroLogo {{
    background: transparent;
    border: none;
}}

/* ===== 체크박스 ===== */
QCheckBox {{
    color: {TEXT};
    spacing: 8px;
    background: transparent;
    font-size: 13px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background-color: {CARD};
}}

QCheckBox::indicator:hover {{
    border-color: {ACCENT};
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

/* ===== 진행바 ===== */
QProgressBar {{
    background-color: {BORDER};
    border: none;
    border-radius: 4px;
    text-align: center;
    color: transparent;
    height: 8px;
    max-height: 8px;
    min-height: 8px;
}}

QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 4px;
}}

/* ===== 스크롤바 ===== */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    border: none;
    margin: 4px 0;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background: {BORDER_HOVER};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    width: 0;
    border: none;
    background: none;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}
"""
