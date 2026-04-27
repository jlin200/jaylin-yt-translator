# SPEC-UPLOAD-001 구현 계획

## 패키지 구조
```
src/upload/
├── __init__.py
├── __main__.py     # cp949 회피 + .env 로드 + sys.exit(main())
├── cli.py          # argparse 8개 플래그, main() 오케스트레이션
├── auth.py         # OAuth flow + token 저장/로드/리프레시
├── api.py          # service build + videos.insert (resumable) + thumbnails.set
├── payload.py      # 입력 폴더 검증 + body dict 빌드
├── quota.py        # .quota_log.json 일일 누적
├── cache.py        # upload_result.json 읽기/쓰기/검사
└── errors.py       # 커스텀 예외 + HttpError 분류 + 백오프 데코레이터
```

REQ-XX 매핑 표는 각 태스크 안에 명시.

---

## T1: 패키지 스켈레톤 (REQ-18, REQ-19)
**목표**: `python -m src.upload --help` 동작.

- `__init__.py` 빈 파일.
- `__main__.py`: SPEC-I18N-001과 동일 패턴 (cp949 reconfigure + dotenv + `from .cli import main`).
- `cli.py`: argparse 8개 플래그 (`folder` positional + 7 옵션). main()은 `print(args)` 만.
- `errors.py`: `UploadError`, `AuthError`, `QuotaError`, `InputError`, `UserCancelled` 클래스만 (빈 본문).

**완료 조건**: `--help` 출력에 8 옵션 모두 표시. 다른 명령은 args 출력만.

---

## T2: payload.py — 입력 검증 + body 빌드 (REQ-04~07)
**목표**: 폴더 → `(video_path, body, thumbnail_path | None)` 반환.

함수:
- `discover_inputs(folder, video_override, thumbnail_override, no_thumbnail) -> Inputs(NamedTuple)`
  - `*.mp4` 정확히 1개 검증 (또는 override)
  - `metadata.json`, `metadata_i18n.json` 존재 검증
  - `thumbnail.png` → `thumbnail.jpg` 순으로 자동 탐지
  - 누락 시 `InputError` (REQ-19 exit 2)
- `build_body(metadata, i18n, privacy_status) -> dict`
  - snippet (REQ-05): title, description, tags, categoryId="10", defaultLanguage/defaultAudioLanguage="ko"
  - status (REQ-07): privacyStatus, selfDeclaredMadeForKids=False
  - localizations (REQ-06): `{k:v for k,v in i18n.items() if not k.startswith("_")}`

**완료 조건**: 단위 테스트 — 정상 폴더 / metadata 누락 / 영상 2개 / 썸네일 없음 4가지 케이스.
`--dry-run` 구현 가능 (T7에서 통합).

---

## T3: auth.py — OAuth flow + token 관리 (REQ-01~03)
**새 개념 ramp-up: OAuth 2.0 Installed App Flow** (research.md 호텔 마스터키 비유).

함수:
- `get_credentials(creds_path: Path, token_path: Path) -> Credentials`
  - token.json 있으면 로드 → `valid` 체크
  - `expired and refresh_token` → `refresh(Request())` → 저장
  - 그 외 (없거나 refresh 실패) → `InstalledAppFlow.from_client_secrets_file(...).run_local_server(port=0)`
  - 끝에 `token_path.write_text(creds.to_json(), encoding="utf-8")`
- `delete_token(token_path: Path)` — 401 핸들러용

**완료 조건**:
- 첫 실행 시 브라우저 자동 열림 + token.json 생성
- 두 번째 실행 시 브라우저 안 열림 (재사용)
- 수동 token.json 삭제 시 다시 인증 흐름

---

## T4: api.py — videos.insert (resumable + 진행률) + thumbnails.set (REQ-08~10)
**새 개념 ramp-up: resumable upload + tqdm 콜백** (research.md 50MB 청크 비유).

함수:
- `build_service(creds: Credentials)` → discovery service 객체
- `upload_video(service, body, video_path, on_progress) -> str (videoId)`
  - `MediaFileUpload(video_path, chunksize=50*1024*1024, resumable=True, mimetype="video/*")`
  - `request = service.videos().insert(part="snippet,status,localizations", body=body, media_body=media)`
  - while 루프 + `next_chunk()` + `on_progress(int(status.progress()*100))` 콜백
  - 최종 `response["id"]` 반환
- `set_thumbnail(service, video_id, thumbnail_path)` — 단순 .execute()

**완료 조건**:
- 진행률 콜백 0~100% 정상 호출됨
- videoId 반환됨
- 썸네일 별도 호출 동작

---

## T5: errors.py — HTTP 분류 + 백오프 (REQ-13~16)
함수:
- `classify_http_error(e: HttpError) -> tuple[Class, str]`
  - 401 → `AuthError("토큰 만료/무효...")`
  - 403 + reason="quotaExceeded" → `QuotaError(...)`
  - 5xx → 백오프 대상 표식 → 재시도
  - 그 외 4xx → `UploadError(상세)`
- `with_retry(fn, *, max_attempts=3)` 함수 (데코레이터 X, 단순 wrapper)
  - 5xx만 `time.sleep(2 ** attempt)` (1, 2, 4초)

**완료 조건**: monkeypatch로 HttpError 5xx → 정확히 3회 시도 / 4xx → 즉시 raise 검증.

---

## T6: quota.py + cache.py (REQ-11, REQ-12)

### quota.py
- `.quota_log.json` 형식: `{"YYYY-MM-DD": units_used, ...}` (KST 자정 리셋)
- `get_remaining(quota_path) -> int` (10000 - 오늘 사용량)
- `record_usage(quota_path, units: int)` — 오늘 키에 누적
- `check_or_die(quota_path, needed: int)` — 부족 시 `QuotaError` raise

### cache.py
- `<폴더>/upload_result.json` 형식:
```json
{
  "video_id": "abc123",
  "uploaded_at": "2026-04-27T13:42:11+09:00",
  "privacy_status": "private",
  "quota_used": 1650,
  "thumbnail_uploaded": true
}
```
- `read_cache(folder) -> dict | None`
- `write_cache(folder, ...)` — atomic write (write to tmp, rename)
- `prompt_force_reupload(cache: dict) -> bool` — `y/N` 입력. N이면 `UserCancelled`

**완료 조건**: 두 번째 실행 시 캐시 적중 거부, `--force-reupload` y/N 분기, 쿼터 누적 검증.

---

## T7: cli.py — main() 통합 (REQ-17, REQ-19)
**흐름**:
```
1) argparse 파싱
2) payload.discover_inputs() → Inputs (실패 시 exit 2)
3) cache.read_cache()
   - 존재 + not --force-reupload → exit 0 with 메시지 + Studio 링크
   - 존재 + --force-reupload → prompt_force_reupload (N이면 exit 3)
4) payload.build_body()
5) --dry-run 이면 payload print + exit 0
6) quota.check_or_die(needed=1650 또는 1600)
7) auth.get_credentials() (실패 시 exit 1)
8) api.build_service()
9) tqdm bar 생성 → with_retry(api.upload_video(..., on_progress=bar.update_to))
   - HttpError → errors.classify → 401이면 token 삭제 안내 + exit 1
   - 5xx 백오프 후도 실패면 exit 6
10) quota.record_usage(1600)
11) thumbnail_path 있고 not --no-thumbnail → with_retry(api.set_thumbnail)
    - 실패 시 경고만 출력 (REQ-17), 영상 유지
    - 성공 시 quota.record_usage(50)
12) cache.write_cache()
13) 성공 출력: videoId + Studio 링크
```

**완료 조건**: end-to-end 흐름이 모듈 호출 단위로 깔끔하게 보임 (한 함수 ≤ 60줄 권장).

---

## T8: 실전 테스트
**목표**: 실제 영상 1개 비공개 업로드 + 다국어 표시 확인.

체크리스트:
- [ ] `--dry-run`으로 페이로드 시각 검증 (snippet/localizations/status 모두 있음)
- [ ] 첫 실행 → 브라우저 OAuth → token.json 생성
- [ ] tier 1 (6개 언어) localizations 적용 영상 업로드 성공
- [ ] 채널 스튜디오에서 언어 전환 시 영문 제목/설명 표시
- [ ] `thumbnail.png` 자동 인식 + 등록
- [ ] 두 번째 실행 → "이미 업로드됨" 거부
- [ ] `--force-reupload` → y/N 프롬프트 → N 입력 시 취소
- [ ] `.quota_log.json` 1650 누적 확인

**비용 추정**: 영상 1개 = 1,650 units. 테스트 2~3회 = 3,300~4,950 units (안전 한도 내).

---

## 일정 / 페이싱
- **오늘 (2026-04-27)**: T1 패키지 스켈레톤만 — 익숙한 작업, 빠르게.
- **다음 세션**: T2 payload (입력 검증, 어제 i18n discover 패턴과 비슷) + T3 auth (OAuth 새 개념, ramp-up 시간 확보).
- **그 다음**: T4 resumable upload (새 개념) + T5 errors.
- **마지막**: T6 + T7 통합 + T8 실전.

총 5~6 세션 예상. 어제 SPEC-I18N-001과 비슷한 분량(T1-T8 + T11).

## 의존성
- T2 → T7
- T3 → T7
- T4 → T7 (T5 wrap)
- T5 → T7 (errors)
- T6 → T7 (quota+cache)

T1~T6은 서로 독립이라 순서 자유롭지만, 권장은 T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8.
