# SPEC-GUI-001 구현 계획

## 패키지 구조
```
src/gui/
├── __init__.py
├── __main__.py            # 진입점 (cp949 + QApplication + 첫 실행 분기)
├── paths.py               # %APPDATA% 경로 + 사용자 데이터 위치 + _MEIPASS
├── setup_wizard.py        # 첫 실행 3단계 마법사 (QStackedWidget)
├── main_window.py         # 메인 화면 (단일 윈도우)
├── upload_worker.py       # QThread Worker (i18n + upload 통합)
└── resources/
    └── icon.ico           # 앱 아이콘 (보라님 나노바나나 제작)

build_exe.py               # 프로젝트 루트, 빌드 + 안전 검증 (SEC-G01)
```

## 의존성 추가
- `PySide6` (~150MB pip wheel, ~80~120MB onefile 산출물)
- `pyinstaller` (개발 의존성)

requirements.txt에 추가:
```
PySide6
pyinstaller
```

---

## T1: PySide6 설치 + 기본 윈도우 스켈레톤
**목표**: `python -m src.gui` → 빈 메인 윈도우가 뜸 + 종료 가능.

- `pip install PySide6 pyinstaller`
- `__init__.py` 빈 파일
- `__main__.py`:
  - cp949 reconfigure
  - `QApplication([])` + `QApplication.setApplicationName("jaylin-yt-translator")`
  - `MainWindow()` show + `app.exec()`
- `main_window.py`: `QMainWindow` 상속, 제목 "jaylin YouTube Translator", 크기 600×500, 빈 central widget.
- `paths.py`:
  - `appdata_dir() -> Path` (`%APPDATA%/jaylin-yt-translator`, 자동 생성)
  - `credentials_path()`, `token_path()`, `env_path()`, `quota_log_path()`
  - `resource_path(relative)` (PyInstaller `_MEIPASS` 핸들링)

**완료 조건**: 윈도우 뜸 + X 닫힘.

---

## T2: 메인 화면 위젯 (단일 화면)
**목표**: 폴더 선택 + 옵션 + 버튼 + 진행률 + 결과 영역 모두 배치 (동작 X).

`main_window.py` 확장:
- `QVBoxLayout`에 위젯 배치:
  - **영상 폴더**: `QHBoxLayout`(QLabel + QLineEdit + QPushButton "폴더 선택"). drag-drop 활성화 (`setAcceptDrops`).
  - **번역 언어**: `QLabel + QComboBox` ("Tier 1: 핵심 6개", "Tier 2: 21개", "Tier 3: 50개").
  - **공개 설정**: `QHBoxLayout`(QRadioButton×3, `QButtonGroup`, 기본 Private).
  - **썸네일 스킵**: `QCheckBox`.
  - **버튼 행**: "번역 + 업로드 시작" + "설정".
  - **진행률**: `QProgressBar` (0~100) + `QLabel` 상태.
  - **결과 영역**: `QTextEdit` read-only.
  - **결과 버튼**: "스튜디오 열기" + "폴더 열기" (초기 비활성).
- 폴더 선택 버튼 → `QFileDialog.getExistingDirectory()` → `QLineEdit.setText`.
- drag-drop 핸들러 → 폴더면 입력에 채움.

**완료 조건**: 모든 위젯 보임 + 폴더 선택 다이얼로그 동작 + drag-drop 동작 (입력에만 들어감, 업로드 X).

---

## T3: 첫 실행 마법사 + paths
**목표**: `%APPDATA%/jaylin-yt-translator` 부재 → 마법사 띄움 + credentials/.env 저장 → 메인 화면.

`setup_wizard.py`:
- `QDialog` + `QStackedWidget` 3페이지
- 페이지 1: credentials.json
  - 안내 라벨 (Google Cloud Console URL + Desktop OAuth 클라이언트 발급 절차)
  - "발급 가이드 열기" 버튼 → `QDesktopServices.openUrl(...)`
  - "credentials.json 선택" 버튼 → `QFileDialog.getOpenFileName(filter="*.json")` → 검증(`installed` 키) → `%APPDATA%`로 복사
  - 다음 버튼 (검증 통과 시 활성)
- 페이지 2: GEMINI_API_KEY
  - 안내 + "API 키 발급 페이지 열기" 버튼 (`https://aistudio.google.com/app/apikey`)
  - `QLineEdit` (Echo Mode = Password) + "저장" → `.env`에 `GEMINI_API_KEY=...` 작성
- 페이지 3: 완료
  - 저장 위치 명시 (`%APPDATA%/jaylin-yt-translator/`)
  - "메인 화면으로" 버튼 → 마법사 종료

`__main__.py` 분기:
- `paths.credentials_path()` 또는 `paths.env_path()` 부재 → `SetupWizard().exec()` 실행. cancel 시 앱 종료.

**완료 조건**:
- 첫 실행 시 마법사 자동 띄움
- credentials.json 선택 + key 입력 → `%APPDATA%`에 저장됨
- 두 번째 실행 시 마법사 안 뜸 → 메인 바로
- 메인 "설정" 버튼 → 마법사 재진입

---

## T4: upload_worker.py — QThread + i18n + upload 통합
**목표**: 백그라운드에서 i18n → upload 한 번에 실행. 시그널로 진행률 + 결과 알림.

`upload_worker.py`:
- `class UploadWorker(QObject)`:
  - 시그널: `progress = Signal(int)`, `stage = Signal(str)` ("[1/2] 번역 중..."), `done = Signal(dict)` (videoId/privacy/quota), `error = Signal(str, bool)` (메시지, 치명성)
  - `__init__(folder, tier, privacy, no_thumbnail)`
  - `run()`:
    1. `stage.emit("[1/2] 번역 중...")`
    2. `translate_playlist(folder, tier=tier)` (i18n 캐시 적중 시 빠름)
    3. `stage.emit("[2/2] 업로드 중...")`
    4. payload.discover_inputs() / build_body()
    5. quota.check_or_die() / auth.get_credentials() (paths.credentials/token 사용)
    6. api.build_service() / upload_video(on_progress=lambda p: self.progress.emit(p))
    7. (옵션) set_thumbnail()
    8. cache.write_cache() / quota.record_usage()
    9. `done.emit({"video_id": ..., ...})`
  - 예외 분기 → `error.emit(str(e), is_fatal)` 후 return.

**완료 조건**: 단위 시연 — 가짜 폴더로 worker.run() 직접 호출 시 시그널 연속 emit 확인.

---

## T5: 메인 윈도우 ↔ Worker 통합
**목표**: 시작 버튼 클릭 → QThread 띄움 → 진행률/상태/결과 자동 업데이트.

`main_window.py` 확장:
- `_on_start_clicked()`:
  - 입력 검증 (폴더 비었으면 결과 영역에 ❌)
  - QThread + UploadWorker 생성, `moveToThread`, signal/slot 연결
  - 시작 버튼 비활성, "설정" 비활성 (중복 클릭 방지)
  - thread.start()
- 슬롯:
  - `_on_progress(pct)` → `progress_bar.setValue(pct)`
  - `_on_stage(text)` → `status_label.setText(text)`
  - `_on_done(result)` → 결과 영역에 "✅ 업로드 완료, videoId: ..." + 스튜디오/폴더 버튼 활성 + 시작 버튼 재활성
  - `_on_error(msg, fatal)` → 결과 영역 빨강 ❌ + (fatal이면 `QMessageBox.critical`) + 시작 재활성

**완료 조건**: 실전 폴더 선택 → 시작 → 진행바 0~100% 부드럽게 + 결과 표시 + 스튜디오 버튼으로 브라우저 열림.

---

## T6: build_exe.py — PyInstaller 빌드 + 안전 검증 (SEC-G01)
**목표**: 단일 명령으로 .exe 생성 + 사용자 데이터 미포함 검증.

`build_exe.py` (프로젝트 루트):
1. **빌드 전 검증**:
   - 프로젝트 루트에 `credentials.json`, `token.json`, `.env` 존재 시 SystemExit (안내 메시지: 임시 이동/삭제)
   - `src/gui/resources/icon.ico` 존재 확인 (없으면 안내)
2. **PyInstaller 호출**:
   ```python
   subprocess.run(["pyinstaller", "--onefile", "--windowed", "--noconfirm",
                   "--name", "jaylin-yt-translator",
                   "--icon", "src/gui/resources/icon.ico",
                   "--add-data", "src/i18n/languages.json;src/i18n",
                   "src/gui/__main__.py"], check=True)
   ```
3. **빌드 후 검증**:
   - `dist/jaylin-yt-translator.exe` 존재 확인
   - 바이너리 안에 `credentials.json` / `token.json` / `.env` 문자열 존재 시 .exe 삭제 + SystemExit
4. **사이즈 출력**: `print(f".exe size: {size_mb:.1f} MB")`
5. **빈 디렉토리 실행 테스트 가이드 출력**:
   - "빈 폴더에서 .exe 실행 시 마법사 떠야 함. 떠나기 전 직접 검증 권장."

**완료 조건**:
- 민감 파일 있는 상태에서 build_exe.py 실행 → 빌드 거부
- 민감 파일 임시 이동 후 → .exe 생성 + 사이즈 출력
- 빈 디렉토리에서 .exe 더블클릭 → 마법사 진입

---

## 페이싱 (오늘 진행 가능 분량)

오늘 1.5시간 남으면:
- T1 (~20분): 빈 윈도우 띄우기
- T2 (~30분): 메인 위젯 배치
- T3 (~40분): 마법사 (가장 긴 단계, 다음 세션 가능)

T4~T6은 다음 세션. 단, **T1~T3 완성하면 사용자가 외형 + 첫 실행 흐름 확인 가능** → 디자인 피드백 받을 좋은 끊기점.

## 의존성
- T2 → T5
- T3 → T5 (paths 사용)
- T4 → T5
- T1~T5 → T6
