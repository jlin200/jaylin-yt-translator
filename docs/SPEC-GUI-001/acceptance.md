# SPEC-GUI-001 인수 기준

## 1. 환경 / 의존성
- [ ] `requirements.txt`에 `PySide6`, `pyinstaller` 추가
- [ ] `pip install -r requirements.txt` 성공 (PySide6 ~150MB)
- [ ] `python -m src.gui` 실행 가능 (모듈 인식)

## 2. T1: 기본 윈도우
- [ ] `python -m src.gui` → 윈도우 뜸 (제목 "jaylin YouTube Translator", 600×500)
- [ ] X 버튼 클릭 → 정상 종료 (exit 0)
- [ ] `paths.appdata_dir()` 호출 → `%APPDATA%\jaylin-yt-translator\` 자동 생성

## 3. T2: 메인 화면 위젯
- [ ] 위젯 6개 모두 보임 (폴더 입력 / Tier 드롭다운 / Privacy 라디오 / 썸네일 체크 / 시작·설정 버튼 / 진행률+결과)
- [ ] **폴더 선택 버튼** 클릭 → `QFileDialog` 뜸 → 폴더 선택 시 `QLineEdit`에 경로 표시
- [ ] **드래그 앤 드롭**으로 폴더 끌어다 놓으면 `QLineEdit`에 경로 표시
- [ ] 드래그 앤 드롭으로 파일(폴더 아닌 것) 놓으면 무시됨 (입력 변화 X)
- [ ] Tier 드롭다운 기본 = "Tier 1: 핵심 6개"
- [ ] Privacy 기본 = Private 라디오 선택됨
- [ ] 썸네일 스킵 기본 = 체크 해제

## 4. T3: 첫 실행 마법사
- [ ] **첫 실행** (`%APPDATA%/jaylin-yt-translator/credentials.json` 부재) → 마법사 자동 진입
- [ ] **페이지 1** credentials.json:
  - [ ] "발급 가이드 열기" 버튼 → 브라우저에서 Google Cloud Console 페이지 열림
  - [ ] "credentials.json 선택" → 파일 선택 다이얼로그
  - [ ] 잘못된 파일(`installed` 키 없음) 선택 → 에러 메시지, 다음 버튼 비활성
  - [ ] 정상 파일 선택 → `%APPDATA%`로 복사 + 다음 버튼 활성
- [ ] **페이지 2** GEMINI_API_KEY:
  - [ ] "발급 페이지 열기" → 브라우저에서 `https://aistudio.google.com/app/apikey`
  - [ ] `QLineEdit` echo mode = Password (입력 시 ●●●● 표시)
  - [ ] 빈 입력 → 저장 버튼 비활성
  - [ ] 입력 후 저장 → `%APPDATA%/.env`에 `GEMINI_API_KEY=...` 작성
- [ ] **페이지 3** 완료:
  - [ ] 저장 위치 텍스트 명시: `%APPDATA%/jaylin-yt-translator/`
  - [ ] "메인 화면으로" → 마법사 종료, 메인 화면 표시
- [ ] **두 번째 실행** → 마법사 안 뜸 (credentials.json + .env 둘 다 있으면)
- [ ] 메인 "설정" 버튼 클릭 → 마법사 재진입 (페이지 1부터)
- [ ] 마법사 도중 X 닫기 → 앱 종료 (마법사 미완료 시 메인 화면 진입 X)

## 5. T4: 백그라운드 Worker
- [ ] `UploadWorker` 단위 시연 — 가짜 폴더로 `run()` 호출 시 `progress` / `stage` / `done` / `error` 시그널 연속 emit
- [ ] i18n 캐시 적중 시 1단계 빠르게 통과
- [ ] 메인 스레드에서 직접 호출 X (반드시 QThread + moveToThread)

## 6. T5: 메인 ↔ Worker 통합 (실전 검증)
- [ ] 폴더 선택 (T8 SPEC-UPLOAD-001에서 사용한 `output/test_upload`) → 시작 버튼
- [ ] **업로드 중 UI 멈춤 없음** (창 이동/리사이즈 정상)
- [ ] 진행바 0 → 100% 부드럽게 업데이트
- [ ] 상태 라벨 "[1/2] 번역 중..." → "[2/2] 업로드 중..." 전환 표시
- [ ] 시작 버튼 + 설정 버튼 업로드 중 비활성
- [ ] 완료 시:
  - [ ] 결과 영역에 ✅ 검정 텍스트로 videoId 표시
  - [ ] "스튜디오 열기" 클릭 → 브라우저에서 `https://studio.youtube.com/video/<id>/edit` 열림
  - [ ] "폴더 열기" 클릭 → Windows 탐색기에서 영상 폴더 열림
  - [ ] 시작/설정 버튼 재활성

## 7. T5: 에러 표시
- [ ] 폴더 비우고 시작 → 결과 영역 ❌ 빨강 + "영상 폴더가 비어 있습니다" + 시작 버튼 즉시 재활성
- [ ] 잘못된 폴더 (mp4 없음) → 결과 영역 ❌ + 메시지 (현재+기대+해결 3요소)
- [ ] credentials.json 손상 시뮬 → `QMessageBox.critical` 모달 + "마법사 다시 실행" 안내
- [ ] 쿼터 부족 시 결과 영역 ❌ + 자정 안내

## 8. T6: 빌드 스크립트
- [ ] `python build_exe.py` 실행
- [ ] **민감 파일 있는 상태**: 프로젝트 루트에 `.env` / `credentials.json` / `token.json` 중 하나라도 있으면 빌드 거부 + 명확한 메시지
- [ ] **민감 파일 모두 이동/삭제 후**: 빌드 진행 → `dist/jaylin-yt-translator.exe` 생성
- [ ] 빌드 후 자동 검증: .exe 안에 `credentials.json`/`token.json`/`.env` 문자열 발견 시 .exe 삭제
- [ ] .exe 사이즈 출력 (예상 80~120MB)

## 9. .exe 실전 검증 (T6 후)
- [ ] **빈 디렉토리에서 .exe 실행** (또는 다른 PC) → 첫 실행 마법사 진입
- [ ] 마법사 완료 → 메인 화면 정상
- [ ] 메인에서 폴더 선택 + 시작 → CLI와 동일한 영상 비공개 업로드 성공
- [ ] `%APPDATA%/jaylin-yt-translator/`에 `.env`, `credentials.json`, `token.json`, `.quota_log.json` 4개 파일 존재
- [ ] **개발 PC와 .exe PC 격리 검증**: 빌드 PC의 `%APPDATA%`와 .exe 사용 PC의 `%APPDATA%`는 별개 (각자의 키)

## 10. 보안 (SEC-G)
- [ ] **SEC-G01**: 빌드 .exe에 사용자 데이터 미포함 (자동 검증 + 수동 grep 확인)
- [ ] **SEC-G02**: README 또는 마법사 안내에 "본인 키 발급" 명시
- [ ] **SEC-G03**: 모든 사용자 데이터가 `%APPDATA%/jaylin-yt-translator/`에만 저장 (.exe 디렉토리 X)
- [ ] **SEC-G04**: 배포 안내문에 "Unknown publisher 경고는 정상" 포함

## 11. UX 디테일
- [ ] 윈도우 아이콘 = `src/gui/resources/icon.ico` (작업표시줄/타이틀바 모두)
- [ ] 키 저장 위치 GUI 명시 (마법사 페이지 3 + 메인 "설정" 버튼 옆 작은 텍스트)
- [ ] 모든 한국어 텍스트 정상 (cp949 깨짐 없음)
- [ ] tab 키로 위젯 간 포커스 이동 자연스러움

## 12. 문서
- [ ] `docs/SPEC-GUI-001/{spec,research,plan,acceptance}.md` 모두 작성됨
- [ ] 1,700명 배포 시 README/안내문 (별도, .exe 동봉 또는 Notion 링크) — 비범위지만 권장:
  - 다운로드 / 첫 실행 / 키 발급 / SmartScreen 경고 안내

---

## Known Issues / 비범위 (참고)
- **코드 사이닝(Authenticode)** 영구 비범위 (SEC-G04)
- **자동 업데이트** 비범위 (사용자가 새 .exe 다운받아 교체)
- **다중 OAuth 계정** 비범위 (1 PC = 1 채널 가정)
- **GEMINI_API_KEY 암호화** 비범위 (1차는 평문 .env)
- **다국어 UI** 비범위 (한국어 고정)
- **tqdm 한글 깨짐** (SPEC-UPLOAD-001 Known) — GUI에서는 tqdm 미사용이라 자연 해결
