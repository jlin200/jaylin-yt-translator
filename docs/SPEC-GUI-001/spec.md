# SPEC-GUI-001: PySide6 GUI 앱 + .exe 배포

## 목적
1,700명 수강생용 클릭 기반 영상 업로드 앱. CLI(SPEC-I18N-001 + SPEC-UPLOAD-001) 자체 변경 없이
GUI 레이어만 추가. PyInstaller `--onefile`로 단일 .exe 배포.

## 범위 / 비범위
- **범위**: PySide6 단일 화면 GUI, 첫 실행 마법사, QThread 백그라운드 업로드,
  `%APPDATA%` 사용자 데이터, PyInstaller 빌드 + 안전 검증, 결과 영역 출력.
- **비범위**:
  - **코드 사이닝(Authenticode)** — 영구 비범위. EV 인증서 비용($300+/년) 부담. "Unknown publisher 경고는 정상" 안내문으로 대체.
  - 자동 업데이트 / 자동 빌드 (GitHub Actions)
  - 다국어 UI (한국어 고정)
  - 멀티 채널 / 다중 OAuth 계정
  - 영상 미리보기 / 메타데이터 인플레이스 편집

## 입력 / 출력
- **입력**: 영상 폴더 (CLI와 동일 — `*.mp4` + `metadata.json` + `metadata_i18n.json`(자동 생성됨) + `thumbnail.{png,jpg}`)
- **사용자 환경**:
  - `%APPDATA%/jaylin-yt-translator/.env` — `GEMINI_API_KEY`
  - `%APPDATA%/jaylin-yt-translator/credentials.json` — OAuth Desktop 클라이언트
  - `%APPDATA%/jaylin-yt-translator/token.json` — 자동 발급/갱신
  - `%APPDATA%/jaylin-yt-translator/.quota_log.json` — 일일 쿼터
- **출력**: YouTube 비공개 영상 + `<폴더>/upload_result.json` + 결과 영역 텍스트.

## 요구사항 (GUI)

### 프레임워크 / 패키징
- **GUI-01** PySide6 6.x 사용. tkinter 미사용.
- **GUI-02** PyInstaller `--onefile --windowed --icon=icon.ico --add-data="src/i18n/languages.json:src/i18n"`.
- **GUI-03** Python 진입점: `src/gui/__main__.py`. CLI(`src/upload`, `src/i18n`) 코드 변경 0줄.

### 화면 구조 (단일 메인 + 마법사)
- **GUI-04** 메인 화면 1개. 위젯 6개:
  - 영상 폴더 입력 (텍스트 박스 + "폴더 선택" 버튼 + drag-and-drop)
  - 번역 언어 드롭다운 (Tier 1 6개 / Tier 2 21개 / Tier 3 50개, 기본 Tier 1)
  - 공개 설정 라디오 3개 (Private / Unlisted / Public, 기본 Private)
  - 썸네일 스킵 체크박스 (기본 OFF)
  - "번역 + 업로드 시작" 버튼 + "설정" 버튼
  - 진행률 바 + 상태 텍스트 + 결과 영역 (멀티라인) + 스튜디오/폴더 열기 버튼
- **GUI-05** 폴더 선택 = `QFileDialog.getExistingDirectory()` + drag-and-drop 둘 다 지원.

### 첫 실행 마법사 (3단계)
- **GUI-06** 앱 첫 실행 시 `%APPDATA%/jaylin-yt-translator/` 부재 → 마법사 자동 진입.
  - 1단계: credentials.json 발급 안내 (Google Cloud Console URL) + 파일 선택 → `%APPDATA%`로 복사
  - 2단계: GEMINI_API_KEY 발급 안내 (`https://aistudio.google.com/app/apikey`) + 텍스트 입력 → `.env` 저장
  - 3단계: "완료! 메인 화면으로" + 저장 위치 명시
- **GUI-07** 메인 화면 "설정" 버튼 → 마법사 재진입 (credentials/키 변경 시).
- **GUI-08** 모든 키/credentials 저장 위치를 GUI에 명시:
  ```
  키는 다음 위치에 저장됩니다:
  C:\Users\<사용자>\AppData\Roaming\jaylin-yt-translator\
  ```

### 워크플로우
- **GUI-09** "번역 + 업로드 시작" = i18n 자동 실행 → upload 자동 실행 (단일 클릭).
  - `metadata_i18n.json` 캐시 적중 시 i18n 스킵.
  - 단계별 진행률: `[1/2] 번역 중...` → `[2/2] 업로드 중...`
- **GUI-10** Tier 드롭다운 선택값을 i18n에 전달 (`--tier 1/2/3/all` 매핑).
- **GUI-11** Privacy 라디오 선택값을 upload에 전달 (`--unlisted/--public` 매핑).

### 백그라운드 + 진행률
- **GUI-12** QThread + Worker QObject + signal/slot. 메인 스레드 UI 멈춤 절대 금지.
- **GUI-13** `api.upload_video(..., on_progress=callback)` 콜백을 `Signal(int)` emit으로 매핑.
  CLI 코드 0줄 변경.
- **GUI-14** 업로드 중 메인 버튼 비활성화 (중복 클릭 방지).

### 에러 / 결과 표시
- **GUI-15** 정상/에러 모두 결과 영역 텍스트로 출력 (비모달). 색상: 성공 ✅ 검정, 경고 ⚠ 주황, 에러 ❌ 빨강.
- **GUI-16** 치명 에러만 `QMessageBox` 모달:
  - credentials.json 손상 (마법사 재진입 유도)
  - token.json refresh 실패 (재인증 안내)
- **GUI-17** 결과 영역 메시지 = SPEC-UPLOAD-001 에러 메시지 그대로 (현재+기대+해결 3요소).
- **GUI-18** 업로드 성공 시 "스튜디오 열기" / "폴더 열기" 버튼 활성화 (`QDesktopServices.openUrl`).

## 보안 (SEC-G)
- **SEC-G01** 빌드 .exe에 사용자 데이터 절대 미포함. 빌드 스크립트가 자동 검증:
  - 빌드 직전 `credentials.json`, `token.json`, `.env`가 빌드 컨텍스트(=프로젝트 루트)에 존재하면 빌드 거부.
  - 빌드 후 `.exe` 안에 위 파일명 검색 → 발견 시 산출물 삭제.
- **SEC-G02** 사용자가 본인 키 직접 발급:
  - credentials.json: Google Cloud Console에서 본인 OAuth 클라이언트 생성
  - GEMINI_API_KEY: Google AI Studio에서 본인 키 생성
- **SEC-G03** 모든 사용자 데이터는 `%APPDATA%/jaylin-yt-translator/`에 저장. .exe 디렉토리에 안 씀.
- **SEC-G04** 코드 사이닝 영구 비범위. 배포 시 안내문 동봉:
  > Windows SmartScreen "Unknown publisher" 경고는 정상입니다.
  > "추가 정보" → "실행" 클릭하여 진행하세요.

## 에러 메시지 예문 (GUI-17)

```
❌ 영상 폴더를 찾을 수 없습니다.
폴더 경로: C:\Users\user\Desktop\my_video
해결: "폴더 선택" 버튼으로 다시 선택하거나 드래그 앤 드롭 해주세요.
```
```
⚠ metadata_i18n.json이 없어 자동으로 번역을 먼저 실행합니다.
사용 언어: Tier 1 (6개)
예상 비용: 약 $0.0005
```
```
✅ 업로드 완료
videoId: Klf3-Nv6_Zs
공개 설정: private
사용 쿼터: 1,650 units (오늘 잔여 8,350)
[ 스튜디오 열기 ] [ 폴더 열기 ]
```

## 관련 SPEC
- 의존: SPEC-I18N-001, SPEC-UPLOAD-001 (CLI 그대로 호출)
- 후속 가능: SPEC-GUI-002 (자동 업데이트 / 다채널 / DPAPI 암호화)
