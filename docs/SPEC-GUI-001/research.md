# SPEC-GUI-001 조사

## PySide6 핵심 클래스

| 카테고리 | 클래스 | 용도 |
|---|---|---|
| 앱 | `QApplication` | 이벤트 루프 시작점 (`app.exec()`) |
| 윈도우 | `QMainWindow`, `QWidget` | 최상위/일반 위젯 |
| 레이아웃 | `QVBoxLayout`, `QHBoxLayout`, `QFormLayout` | 자식 위젯 배치 |
| 입력 | `QLineEdit`, `QComboBox`, `QRadioButton`, `QCheckBox`, `QPushButton` | 사용자 입력 |
| 출력 | `QLabel`, `QTextEdit`(read-only), `QProgressBar` | 표시 |
| 다이얼로그 | `QFileDialog`, `QMessageBox` | 파일 선택, 모달 알림 |
| 마법사 | `QStackedWidget` | 페이지 전환 (1→2→3 단계) |
| 시스템 | `QDesktopServices` | URL/폴더 열기 (`openUrl`) |

## Signal / Slot 패턴 (PySide6)

```python
from PySide6.QtCore import QObject, Signal

class Worker(QObject):
    progress = Signal(int)         # 시그널 정의
    done = Signal(str)
    error = Signal(str)

    def run(self):
        for i in range(101):
            self.progress.emit(i)  # 발사
        self.done.emit("videoId123")

# 메인 윈도우에서
worker.progress.connect(self.progress_bar.setValue)  # 자동 메인 스레드 전달
worker.done.connect(self.on_done)
```

PyQt5와 차이: PyQt는 `pyqtSignal`, PySide6는 `Signal` (이름만 다름).

## QThread + Worker 패턴 (UI 멈춤 방지)

```python
from PySide6.QtCore import QThread

self.thread = QThread()
self.worker = UploadWorker(folder, options)
self.worker.moveToThread(self.thread)

# 스레드 시작 시 worker.run() 호출
self.thread.started.connect(self.worker.run)

# 종료 시 자동 cleanup
self.worker.done.connect(self.thread.quit)
self.worker.done.connect(self.worker.deleteLater)
self.thread.finished.connect(self.thread.deleteLater)

# 시그널 연결 후 시작
self.worker.progress.connect(self.progress_bar.setValue)
self.thread.start()
```

**중요**: Worker를 `__init__`에서 부모로 만들면 안 됨 (메인 스레드 소속). `moveToThread()` 필수.

## Drag and Drop (폴더 받기)

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_dir():
                self.folder_input.setText(path)
```

## %APPDATA% 경로

```python
from PySide6.QtCore import QStandardPaths
appdata = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
# Windows: C:\Users\<user>\AppData\Roaming\jaylin-yt-translator\
#   (앱 이름이 QApplication.setApplicationName()으로 자동 추가됨)
```

또는 직접:
```python
appdata = Path(os.environ["APPDATA"]) / "jaylin-yt-translator"
appdata.mkdir(parents=True, exist_ok=True)
```

## CLI 코드 → GUI 통합 패턴

기존 CLI는 변경 0줄. 단지 GUI에서 함수 직접 호출:

```python
from src.upload import auth, payload, api, cache, quota
from src.i18n.pipeline import translate_playlist

# Worker.run() 안에서:
i18n_path = translate_playlist(folder, tier=tier_value, force=False)
inputs = payload.discover_inputs(folder, ...)
body = payload.build_body(inputs.metadata, inputs.i18n, privacy_status)
quota.check_or_die(QUOTA_LOG, needed)
creds = auth.get_credentials(creds_path, token_path)
service = api.build_service(creds)
video_id = api.upload_video(service, body, inputs.video, on_progress=lambda p: self.progress.emit(p))
api.set_thumbnail(service, video_id, inputs.thumbnail)
cache.write_cache(folder, video_id=..., ...)
```

CLI의 `cli.py main()`은 GUI에서 미사용. 모듈 함수만 직접 호출.

## PyInstaller --onefile

### 명령
```bash
pyinstaller --onefile --windowed --noconfirm \
  --name jaylin-yt-translator \
  --icon src/gui/resources/icon.ico \
  --add-data "src/i18n/languages.json;src/i18n" \
  src/gui/__main__.py
```

Windows 구분자 `;`, Unix `:`. PySide6 6.x는 자체 hook이 있어 추가 설정 거의 불필요.

### `_MEIPASS` 패턴 (런타임 리소스 경로)
```python
import sys
from pathlib import Path

def resource_path(relative: str) -> Path:
    """PyInstaller --onefile에서 번들된 리소스 절대 경로."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).parent.parent / relative

# 사용
languages_path = resource_path("src/i18n/languages.json")
```

`src/i18n/prompt.py`의 languages.json 로드 부분이 이 함수를 거쳐야 .exe에서 정상 작동.

### Hidden imports
PyInstaller가 동적 import 못 찾을 수 있음. 필요 시:
```bash
--hidden-import googleapiclient.discovery
--hidden-import google.auth.transport.requests
```

PySide6 + 우리 의존성은 대부분 자동 감지. 빌드 후 빈 디렉토리에서 .exe 실행 테스트로 검증.

## 빌드 안전 검증 (SEC-G01)

```python
# build_exe.py 핵심 로직
SENSITIVE = ["credentials.json", "token.json", ".env"]
for name in SENSITIVE:
    if (PROJECT_ROOT / name).exists():
        raise SystemExit(f"❌ 빌드 거부: 민감 파일 발견 → {name}\n"
                         f"해결: {name}을 빌드 전 임시 이동하거나 삭제하세요.")

# PyInstaller 실행

# 빌드 후 검증
import zipfile
with open(EXE_PATH, "rb") as f:
    blob = f.read()
for name in SENSITIVE:
    if name.encode() in blob:
        EXE_PATH.unlink()
        raise SystemExit(f"❌ .exe 안에 {name} 발견 → 산출물 삭제됨")
```

## 화면 모킹 (Q4 합의안)

```
┌─ jaylin YouTube Translator ─────────────────────┐
│                                                  │
│  영상 폴더                                        │
│  ┌──────────────────────────────┐ ┌──────────┐  │
│  │ (드래그 앤 드롭 또는 선택)    │ │ 폴더 선택│  │
│  └──────────────────────────────┘ └──────────┘  │
│                                                  │
│  번역 언어:  [Tier 1: 핵심 6개            ▾]    │
│                                                  │
│  공개 설정:  ◉ Private  ○ Unlisted  ○ Public    │
│                                                  │
│  ☐ 썸네일 스킵                                  │
│                                                  │
│  ┌──────────────────────┐  ┌────────┐           │
│  │ 번역 + 업로드 시작     │  │  설정  │          │
│  └──────────────────────┘  └────────┘           │
│                                                  │
│  진행률: [████████░░░░░░] 40%                   │
│  상태:   영상 업로드 중...                        │
│                                                  │
│  ─── 결과 ────────────────────────────────────  │
│  ✅ 업로드 완료                                  │
│  videoId: Klf3-Nv6_Zs                           │
│  ┌─────────────┐  ┌─────────────┐               │
│  │ 스튜디오 열기 │  │  폴더 열기  │              │
│  └─────────────┘  └─────────────┘               │
└──────────────────────────────────────────────────┘
```

## 참고 링크
- PySide6: doc.qt.io/qtforpython-6
- PyInstaller PySide6 hook: github.com/pyinstaller/pyinstaller/tree/develop/PyInstaller/hooks
- QStandardPaths: doc.qt.io/qt-6/qstandardpaths.html
- SmartScreen 안내 (사용자용): support.microsoft.com/en-us/topic/93af1da9-4c1a-7c08-c5d7-...
