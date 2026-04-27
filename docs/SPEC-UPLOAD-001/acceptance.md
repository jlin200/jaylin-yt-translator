# SPEC-UPLOAD-001 인수 기준

> 모든 항목 통과 시 SPEC 완료. 실전 1회 검증 필수.

## 1. 환경 / 의존성
- [ ] `credentials.json` 프로젝트 루트 존재 (Desktop OAuth 클라이언트)
- [ ] `.gitignore`에 `credentials.json`, `token.json`, `.quota_log.json` 등록 (SEC-01)
- [ ] `requirements.txt`에 다음 포함:
  - `google-auth-oauthlib`
  - `google-api-python-client`
  - `google-auth`
  - `tqdm`
- [ ] `python -m src.upload` 실행 가능 (패키지 인식)

## 2. CLI 인터페이스 (REQ-18, REQ-19)
- [ ] `python -m src.upload --help` → 8개 옵션 모두 표시:
  - `folder` (positional), `--unlisted`, `--public`, `--dry-run`, `--no-thumbnail`,
    `--video <path>`, `--thumbnail <path>`, `--force-reupload`
- [ ] 폴더 인자 누락 → argparse 에러 + exit 2
- [ ] `--unlisted`와 `--public` 동시 지정 → 에러 (mutually exclusive)

## 3. 입력 검증 (REQ-04, T2)
- [ ] 존재 안 하는 폴더 → exit 2 + "폴더가 아닙니다: <path>"
- [ ] `metadata.json` 누락 → exit 2 + 포맷 안내 (`{"title", "description"}`)
- [ ] `metadata_i18n.json` 누락 → exit 2 + "SPEC-I18N-001 (`python -m src.i18n <폴더>`)을 먼저 실행하세요" 안내
- [ ] `*.mp4` 0개 → exit 2 + "영상 파일이 없습니다. --video 플래그로 명시하세요"
- [ ] `*.mp4` 2개 이상 → exit 2 + "영상 파일이 N개 발견되었습니다: [...]. .mp4 1개만 두거나 --video 명시"
- [ ] 썸네일 없음 + `--no-thumbnail` 미지정 → 경고만 출력하고 영상은 업로드 진행

## 4. OAuth 인증 (REQ-01~03, T3)
- [ ] `credentials.json` 없음 → exit 1 + Google Cloud Console 발급 안내
- [ ] **첫 실행** → 브라우저 자동 열림 + 동의 후 `token.json` 생성됨
- [ ] **두 번째 실행** → 브라우저 안 열림 (token.json 재사용)
- [ ] `token.json` 만료 (1시간 후) → `refresh_token`으로 자동 갱신, 사용자에게 보이지 않음
- [ ] 수동 `token.json` 삭제 후 실행 → 첫 실행 흐름 다시 진행
- [ ] `refresh_token`도 만료 → exit 1 + "token.json 삭제 후 재실행하세요" 안내
- [ ] OAuth scope = `youtube` 단일 (동의 화면에서 "YouTube 계정 관리" 항목만 표시)

## 5. 페이로드 빌드 (REQ-05~07, T2)
- [ ] `--dry-run` → API 호출 0회, snippet/status/localizations 페이로드 stdout 출력
- [ ] snippet:
  - [ ] `title` = `metadata_i18n.json["ko"]["title"]`
  - [ ] `description` = `metadata_i18n.json["ko"]["description"]`
  - [ ] `categoryId` = `"10"` (string)
  - [ ] `tags` = `metadata.json["tags"]` 또는 `[]`
  - [ ] `defaultLanguage` = `"ko"`
  - [ ] `defaultAudioLanguage` = `"ko"`
- [ ] localizations:
  - [ ] `_` prefix 키 모두 제외됨 (예: `_source_hash` 없음)
  - [ ] `ko` 포함됨 (defaultLanguage와 중복 무해)
  - [ ] tier 1 = 6개 키, tier all = 50개 키
- [ ] status:
  - [ ] 기본 `privacyStatus` = `"private"`
  - [ ] `--unlisted` → `"unlisted"`
  - [ ] `--public` → `"public"`
  - [ ] `selfDeclaredMadeForKids` = `False`

## 6. 영상 업로드 (REQ-08, REQ-09, T4)
- [ ] resumable upload 사용 (50MB chunksize)
- [ ] tqdm 진행바 0~100% 부드럽게 표시
- [ ] 업로드 성공 시 videoId 반환됨 (11자 영숫자)
- [ ] **YouTube 채널 스튜디오에서 영상 확인됨** (`https://studio.youtube.com/video/<id>/edit`)
- [ ] **언어 전환 시 영문 제목/설명 표시** (다국어 동작 검증)
- [ ] `defaultLanguage=ko` 설정 → 한국어 시청자에게 한국어 제목 표시

## 7. 썸네일 (REQ-10, T4)
- [ ] `thumbnail.png` 자동 탐지 + 업로드 성공
- [ ] `thumbnail.png` 없고 `thumbnail.jpg` 있음 → jpg 자동 사용
- [ ] `--thumbnail <path>` 명시 → 해당 파일 사용 (자동 탐지 무시)
- [ ] `--no-thumbnail` → 썸네일 단계 완전 스킵
- [ ] 썸네일 업로드 실패 (예: 파일 손상) → 영상은 유지, 경고 + Studio 링크 출력, exit 0 (REQ-17)

## 8. 캐시 / 중복 방지 (REQ-12, T6)
- [ ] 업로드 성공 시 `<폴더>/upload_result.json` 생성:
  - `video_id`, `uploaded_at` (ISO 8601 + KST), `privacy_status`, `quota_used`, `thumbnail_uploaded`
  - **민감 정보 (token, secret) 미포함** (SEC-03)
- [ ] 두 번째 실행 (캐시 존재) → exit 0 + "이미 업로드됨: videoId, Studio 링크" 출력
- [ ] `--force-reupload` → "이미 업로드된 영상입니다. ... 정말 다시 올리시겠어요? [y/N]" 프롬프트
  - `y` 또는 `Y` → 진행
  - 그 외 (Enter/N/n/임의 입력) → exit 3 + "취소되었습니다"

## 9. 쿼터 추적 (REQ-11, T6)
- [ ] 업로드 성공 시 `.quota_log.json`에 오늘 날짜 키로 1,650 누적
- [ ] 썸네일 스킵 시 1,600만 누적
- [ ] 썸네일 업로드 실패 시 1,600만 누적 (50은 미사용)
- [ ] 잔여 < 1,650 + 썸네일 사용 시 → exit 5 + "오늘 사용 가능 쿼터: X. 필요: 1,650. 자정 이후 또는 --no-thumbnail" 안내
- [ ] 잔여 < 1,600 + `--no-thumbnail` 사용 시 → exit 5 (위와 동일 메시지, 1,600 기준)
- [ ] 다음 날짜 (KST 자정 통과) → 쿼터 자동 0부터 시작

## 10. HTTP 에러 처리 (REQ-13~16, T5)
- [ ] 401 토큰 무효 → exit 1 + token.json 삭제 안내
- [ ] 403 `quotaExceeded` → exit 5 + 자정 안내 (사전 검사 우회한 경우 대비)
- [ ] 5xx → 1초 → 2초 → 4초 백오프 3회 재시도. 최종 실패 시 exit 6 + "서버 일시 오류, 잠시 후 다시 시도하세요"
- [ ] 그 외 4xx → exit 6 + 응답 본문에서 reason/message 추출 출력 (단, 토큰/secret 마스킹)
- [ ] 모든 에러 메시지 = 현재 상태 + 기대치 + 해결 방법 3요소 포함

## 11. 보안 (SEC-01~05)
- [ ] `git status` 실행 시 `credentials.json`, `token.json` 표시 안 됨 (`.gitignore` 작동)
- [ ] stdout / stderr 어디에도 `access_token` / `refresh_token` 평문 출력 없음
  - 디버그 모드 시도 → 토큰 영역 `***` 마스킹 또는 출력 자체 차단
- [ ] `upload_result.json` 내용 검사 → 민감 정보 0개
- [ ] `credentials.json` 누락 시 안내에 발급 절차 (Google Cloud Console URL) 포함
- [ ] README 또는 `--help` 끝에 "credentials.json/token.json은 채널 마스터키이므로 절대 공유 금지" 명시

## 12. 실전 검증 (T8)
- [ ] tier 1 6개 언어 + 썸네일 포함 1개 영상 비공개 업로드 성공
- [ ] 영상 1분 이상 길이 (resumable upload 청크 분할 확인)
- [ ] YouTube 스튜디오에서:
  - [ ] 영상 재생 가능
  - [ ] 카테고리 = Music
  - [ ] 언어 = 한국어
  - [ ] 설정 → 자막/번역 → 6개 언어 모두 등록됨
  - [ ] URL `?hl=en` 추가 시 영문 표시
- [ ] 캐시/쿼터 파일 모두 정상 갱신
- [ ] 두 번째 실행 시 거부 메시지 정상

## 13. 문서 / 운영
- [ ] `docs/SPEC-UPLOAD-001/spec.md`, `research.md`, `plan.md`, `acceptance.md` 모두 작성됨
- [ ] `src/upload/` 모듈 docstring 모두 있음 (한국어 OK)
- [ ] README 또는 `--help`에 사용 예시 포함

---

## Known Issues / 비범위 (참고)
- 멀티 채널 지원 (1 OAuth = 1 채널 가정) → 향후 SPEC-UPLOAD-003 가능
- 자동 공개 전환 → 사용자가 채널 스튜디오에서 수동 (안전 우선)
- 메타데이터 변경 시 update 호출 → SPEC-UPLOAD-002로 분리
- `made for kids` 분기 → 음악 채널 가정으로 항상 `false` 고정
