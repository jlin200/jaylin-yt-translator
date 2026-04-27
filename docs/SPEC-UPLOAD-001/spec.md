# SPEC-UPLOAD-001: YouTube 영상 업로드 + 다국어 메타데이터

## 목적
영상 파일(.mp4) + 한국어 메타데이터 + 50개국 번역(SPEC-I18N-001 출력) 묶음을
**비공개(private) YouTube 영상**으로 한 번에 업로드. 다국어 표시는 채널 스튜디오에서 자동.

## 범위 / 비범위
- **범위**: OAuth 2.0 인증, `videos.insert` (snippet+status+localizations 1회), `thumbnails.set`,
  resumable upload, 진행률, 쿼터 추적, 중복 방지, HTTP 에러 처리.
- **비범위**: 영상 생성/편집(SPEC-VIDEO-001 영역), 번역(SPEC-I18N-001), 자동 공개 전환,
  댓글/플레이리스트 관리, 멀티 채널 지원.

## 입력
폴더 1개 (positional). 폴더 안에서 자동 탐지:

| 파일 | 필수 | 비고 |
|---|---|---|
| `*.mp4` | ✅ | 정확히 1개. 0개/2개+ 시 에러 (또는 `--video <path>` 명시) |
| `metadata.json` | ✅ | `{"title", "description", "tags"?}` (한국어, tags는 옵션) |
| `metadata_i18n.json` | ✅ | SPEC-I18N-001 출력. `{"_source_hash", "ko": {...}, "en": {...}, ...}` |
| `thumbnail.{png,jpg}` | ❌ | 자동 탐지. 없으면 경고만, 영상은 업로드. `--no-thumbnail`로 명시 스킵 가능 |

추가 필수 (프로젝트 루트):
- `credentials.json` — Google Cloud OAuth 2.0 Desktop 클라이언트 ID
- `.env` — (선택) 일부 설정용

## 출력
- **YouTube**: 비공개 영상 1개 + 다국어 localizations + (옵션) 썸네일
- **표준 출력**: videoId, 채널 스튜디오 링크 (`https://studio.youtube.com/video/{videoId}/edit`)
- **`<폴더>/upload_result.json`**: 캐시 (중복 업로드 방지)
- **`./.quota_log.json`**: 일일 쿼터 누적

## 요구사항 (REQ)

### 인증
- **REQ-01** OAuth 2.0 scope = `https://www.googleapis.com/auth/youtube` 단일.
- **REQ-02** 첫 실행 시 `InstalledAppFlow.run_local_server(port=0)`로 브라우저 자동 열림.
  사용자 동의 후 `token.json` 저장.
- **REQ-03** 재실행 시 `token.json` 재사용. 만료(`expired`)면 `refresh_token`으로 자동 갱신
  후 저장. 갱신 실패 시 친절한 재인증 안내(`token.json 삭제 후 재실행`).

### 페이로드
- **REQ-04** `videos.insert` 1회 호출, `part="snippet,status,localizations"`. update 불필요.
- **REQ-05** `snippet`: `title=ko.title`, `description=ko.description`, `categoryId=10` (Music 고정),
  `tags=metadata.json.tags ?? []`, `defaultLanguage="ko"`, `defaultAudioLanguage="ko"`.
- **REQ-06** `localizations`: `metadata_i18n.json`에서 `_` prefix 키 제외한 모든 항목 그대로.
  ko 포함(중복이지만 명시 권장).
- **REQ-07** `status`: `privacyStatus` = `private`(기본) / `unlisted`(`--unlisted`) / `public`(`--public`).
  추가: `selfDeclaredMadeForKids=False`(필수 필드).

### 업로드
- **REQ-08** `MediaFileUpload(path, chunksize=50*1024*1024, resumable=True)`. 청크 단위 재개 가능.
- **REQ-09** tqdm 진행바로 0~100% 표시 (chunk 콜백 = `status.progress() * 100`).
- **REQ-10** 썸네일 자동 탐지: `thumbnail.png` 우선, 없으면 `thumbnail.jpg`.
  `--thumbnail <path>` 플래그로 오버라이드. `--no-thumbnail`로 스킵.
  영상 insert 성공 후 즉시 `thumbnails.set` 호출.

### 쿼터 / 캐시
- **REQ-11** `.quota_log.json` 일자별 누적 (KST 기준 자정 리셋 가정).
  업로드 전 잔여 < 1650 시 사전 거부 + 자정 안내.
- **REQ-12** `<폴더>/upload_result.json` 존재 시 "이미 업로드됨" 에러 + 스튜디오 링크.
  `--force-reupload` 플래그 시 **`y/N` 확인 프롬프트** 후에만 재업로드.

### 에러 처리
- **REQ-13** HTTP 401 → `token.json` 삭제 안내 (exit 1).
- **REQ-14** HTTP 403 quotaExceeded → 현재 사용량 + 자정 안내 (exit 5).
- **REQ-15** HTTP 5xx → 지수 백오프 3회 (1→2→4초). 그래도 실패 시 exit 6.
- **REQ-16** 그 외 4xx → 응답 본문 일부 출력 후 exit 6.
- **REQ-17** **부분 실패**: `videos.insert` 성공 후 `thumbnails.set` 실패 시 영상 유지(삭제 X),
  경고 + 스튜디오 링크 출력. exit 0(영상 자체는 살아 있으므로).

### CLI
- **REQ-18** 인터페이스:
```bash
python -m src.upload <폴더>                    # private 기본
python -m src.upload <폴더> --unlisted         # 링크 공유용
python -m src.upload <폴더> --public           # 공개
python -m src.upload <폴더> --dry-run          # API 호출 X, 페이로드만 stdout
python -m src.upload <폴더> --no-thumbnail
python -m src.upload <폴더> --video <path>     # *.mp4 자동 탐지 오버라이드
python -m src.upload <폴더> --thumbnail <path> # 썸네일 명시
python -m src.upload <폴더> --force-reupload   # y/N 확인 후 재업로드
```
- **REQ-19** Exit codes:
  - `0` 성공 (썸네일 부분 실패 포함)
  - `1` 인증 실패 (credentials.json 없음, refresh 실패)
  - `2` 입력 문제 (폴더/파일 누락, 영상 N개)
  - `3` 사용자 취소 (`--force-reupload` y/N 거부)
  - `5` 쿼터 부족
  - `6` API 호출 실패 (5xx 백오프 후, 또는 4xx)

## 보안 (SEC)
- **SEC-01** `credentials.json`, `token.json` 절대 Git 커밋 금지. `.gitignore` 등록 필수 (이미 등록됨).
- **SEC-02** stdout / stderr / 로그 어디에도 `access_token` / `refresh_token` 출력 금지.
  디버그 출력 시 `***` 마스킹.
- **SEC-03** `upload_result.json`에 민감 정보 미포함 (videoId, ISO 시간, privacy, quota_used만).
- **SEC-04** `credentials.json` 누락 시 발급 절차 안내 (Google Cloud Console URL 안내 OK).
- **SEC-05** 사용자 책임 명시: 채널 마스터키이므로 PC 공유 환경 / 클라우드 동기화 폴더 주의.

## 에러 메시지 예문 (현재 + 기대 + 해결 3요소)

```
credentials.json이 없습니다.
현재 폴더: C:\Users\user\my-projects\jaylin-yt-translator
해결: Google Cloud Console (console.cloud.google.com) → API 및 서비스 → 사용자 인증 정보
      → OAuth 클라이언트 ID 만들기 (Desktop 앱) → 다운로드 후 프로젝트 루트에 저장.
```

```
영상 파일이 3개 발견되었습니다: video1.mp4, video2.mp4, old_render.mp4
폴더에 .mp4 1개만 두거나 --video <path>로 명시하세요.
```

```
오늘 사용 가능한 쿼터: 850 units
업로드에 필요한 쿼터: 1,650 units (videos.insert 1600 + thumbnails.set 50)
해결: 자정(00:00 PT, 약 17:00 KST) 이후 다시 시도하거나 --no-thumbnail (1600만 사용)
```

```
이미 업로드된 영상입니다.
videoId: dQw4w9WgXcQ
업로드 시간: 2026-04-27T13:42:11+09:00
스튜디오: https://studio.youtube.com/video/dQw4w9WgXcQ/edit
재업로드하려면 --force-reupload (확인 프롬프트 있음).
```

## 관련 SPEC
- 의존: SPEC-I18N-001 (`metadata_i18n.json` 생성)
- 후속: 추후 SPEC-UPLOAD-002 (메타 갱신 전용 update 모드) 가능성
