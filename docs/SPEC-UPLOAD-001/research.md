# SPEC-UPLOAD-001 조사

## YouTube Data API v3

### Discovery 빌드
```python
from googleapiclient.discovery import build
service = build("youtube", "v3", credentials=creds)
```
- `service.videos()`, `service.thumbnails()` 등 리소스 컬렉션
- 메서드 체이닝: `service.videos().insert(part=..., body=..., media_body=...).execute()`

### `videos.insert`
- **쿼터: 1,600 units**
- HTTP `POST https://www.googleapis.com/upload/youtube/v3/videos`
- `part="snippet,status,localizations"` — 한 번에 다 박음 (insert+update 분리 불필요)
- body 구조:
```python
body = {
    "snippet": {
        "title": "한국어 제목",
        "description": "한국어 설명",
        "tags": ["lofi", "플레이리스트"],
        "categoryId": "10",
        "defaultLanguage": "ko",
        "defaultAudioLanguage": "ko",
    },
    "status": {
        "privacyStatus": "private",
        "selfDeclaredMadeForKids": False,
    },
    "localizations": {
        "en": {"title": "...", "description": "..."},
        "ja": {"title": "...", "description": "..."},
        # ko 포함 가능 (defaultLanguage와 중복이지만 무해)
    },
}
```
- `media_body=MediaFileUpload(path, chunksize=50*1024*1024, resumable=True)` — resumable 필수
- 응답: `{"kind": "youtube#video", "id": "abc123", "snippet": {...}, ...}`

### Resumable upload 루프
```python
request = service.videos().insert(part=..., body=..., media_body=media)
response = None
while response is None:
    status, response = request.next_chunk()
    if status:
        progress_pct = int(status.progress() * 100)
        # tqdm 업데이트
```
- `next_chunk()`가 청크별로 호출되며 끝나면 `(None, response_dict)` 반환
- 중간에 5xx 에러 시 `next_chunk()` 안에서 자체 재시도 안 함 → 외부 백오프 필요

### `thumbnails.set`
- **쿼터: 50 units**
- 호출:
```python
service.thumbnails().set(
    videoId=video_id,
    media_body=MediaFileUpload(thumbnail_path),
).execute()
```
- 영상 insert 후에만 호출 가능 (videoId 필요)
- 1280×720 기본, 2MB 이하 권장 (Plimate 워크플로우와 일치)
- 실패해도 영상 자체는 살아 있음

### `localizations` 동작 방식
- 사용자가 YouTube에서 언어 변경 시 자동 표시 전환
- `defaultLanguage` 명시 안 하면 localizations 무시될 수 있음 → REQ-05에 명시
- 키는 BCP-47 (`en`, `ja`, `zh-TW`, `pt-BR` 등) — SPEC-I18N-001 출력과 호환

## OAuth 2.0 Installed App Flow

### 비유 (사용자 ramp-up용)
**호텔 마스터키 발급 절차**:
1. `credentials.json` = 호텔 신분증 (앱이 누구인지)
2. 사용자가 프론트(브라우저)에 가서 동의 = "이 앱이 내 채널에 영상 올리는 거 OK"
3. 프론트가 마스터키(`access_token` + `refresh_token`) 발급 → `token.json` 저장
4. `access_token`은 1시간짜리 (만료) → `refresh_token`으로 새 마스터키 자동 발급
5. `refresh_token`도 만료되면(7일 미사용 등) 다시 1번부터

### 코드 패턴
```python
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/youtube"]

def get_credentials(creds_path: Path, token_path: Path) -> Credentials:
    creds: Credentials | None = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds
```

### `run_local_server(port=0)` 동작
- 빈 포트 자동 할당 → 로컬 HTTP 서버 띄움
- 브라우저 자동 열림 → Google 로그인 / 동의 → `http://localhost:<port>?code=...` 리다이렉트
- 코드 받아서 토큰 교환 → 서버 종료
- Desktop 앱 타입은 redirect URI 와일드카드라 별도 설정 불필요

## 쿼터 (2026-01 시점)
- 일일 한도: **10,000 units / project**
- 비용:
  - `videos.insert` = 1,600
  - `thumbnails.set` = 50
  - `videos.list` = 1 (조회는 거의 무료)
  - `videos.update` = 50
- 한 영상 풀 업로드 = 1,650 → **하루 6개 한계**
- 리셋: **00:00 미국 태평양시(PT)** = **17:00 KST (서머타임 시 16:00)**
- 초과 시: HTTP 403 + `quotaExceeded` reason

## 에러 응답 처리

### `googleapiclient.errors.HttpError`
```python
from googleapiclient.errors import HttpError

try:
    response = request.execute()
except HttpError as e:
    status = e.resp.status                    # 401, 403, 503 등
    body = e.error_details                    # 리스트 또는 None
    # e.content = bytes → json.loads로 reason 추출
    import json as _json
    error_obj = _json.loads(e.content)
    reason = error_obj.get("error", {}).get("errors", [{}])[0].get("reason", "")
    # reason 예: "quotaExceeded", "uploadLimitExceeded", "invalidVideo"
```

### 분기 매트릭스
| status | reason | 처리 |
|---|---|---|
| 401 | `authError` 등 | refresh 시도 → 실패 시 token.json 삭제 안내 |
| 403 | `quotaExceeded` | exit 5, 잔여/자정 안내 |
| 403 | `forbidden` (scope 부족) | scope 확인 안내 |
| 5xx | * | 지수 백오프 3회 (1, 2, 4초) |
| 그 외 4xx | * | 응답 본문 일부 + exit 6 |

## 지수 백오프 패턴
```python
def with_retry(fn, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            return fn()
        except HttpError as e:
            if 500 <= e.resp.status < 600 and attempt < max_attempts - 1:
                time.sleep(2 ** attempt)  # 1 → 2 → 4
                continue
            raise
```
- SPEC-I18N-001의 `translator.py` 패턴과 동일 → 코드 일관성

## `metadata_i18n.json` 형식 (SPEC-I18N-001 출력)
```json
{
  "_source_hash": "sha256:abc123...",
  "ko": {"title": "오늘은 괜찮은 하루~!!!", "description": "..."},
  "en": {"title": "It's Okay Today~!!!", "description": "..."},
  "ja": {"title": "...", "description": "..."},
  "th": {...}, "vi": {...}, "zh-TW": {...}, "pt-BR": {...}
}
```
- localizations 변환:
```python
i18n = json.loads(i18n_path.read_text(encoding="utf-8"))
localizations = {k: v for k, v in i18n.items() if not k.startswith("_")}
```
- 한 줄 컴프리헨션. ko도 포함됨(중복 무해).

## 라이브러리 버전 (requirements.txt 기준)
- `google-api-python-client==2.194.0`
- `google-auth-oauthlib==1.3.1`
- `google-auth==2.49.2`
- `tqdm==4.67.3`

## 참고 링크 (개발 시 참조)
- API 메서드: developers.google.com/youtube/v3/docs/videos/insert
- localizations: developers.google.com/youtube/v3/docs/videos#localizations
- OAuth Quickstart: developers.google.com/youtube/v3/quickstart/python
- Quota costs: developers.google.com/youtube/v3/determine_quota_cost
