"""upload 모듈 CLI 진입점 (SPEC-UPLOAD-001 T1+T7 통합).

사용:
    python -m src.upload <폴더>                    # private 기본
    python -m src.upload <폴더> --unlisted
    python -m src.upload <폴더> --public
    python -m src.upload <폴더> --dry-run          # API 호출 X, 페이로드만 출력
    python -m src.upload <폴더> --no-thumbnail
    python -m src.upload <폴더> --video <path>
    python -m src.upload <폴더> --thumbnail <path>
    python -m src.upload <폴더> --force-reupload   # y/N 확인 후 재업로드

Exit codes (REQ-19):
    0 = 성공 (썸네일 부분 실패 포함)
    1 = 인증 실패
    2 = 입력 문제
    3 = 사용자 취소
    5 = 쿼터 부족
    6 = API 호출 실패
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from googleapiclient.errors import HttpError

from . import api, auth, cache, payload, quota
from .errors import (
    AuthError,
    InputError,
    QuotaError,
    UploadError,
    UserCancelled,
    classify_http_error,
    with_retry,
)

QUOTA_INSERT = 1600
QUOTA_THUMBNAIL = 50
QUOTA_LOG = Path(".quota_log.json")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m src.upload",
        description="YouTube 영상 + 다국어 메타데이터 업로드 (SPEC-UPLOAD-001)",
    )
    p.add_argument(
        "folder",
        help="영상 폴더 (metadata.json + metadata_i18n.json + .mp4 포함)",
    )
    privacy = p.add_mutually_exclusive_group()
    privacy.add_argument("--unlisted", action="store_true",
                         help="privacyStatus=unlisted (링크 있는 사람만)")
    privacy.add_argument("--public", action="store_true",
                         help="privacyStatus=public (전체 공개)")
    p.add_argument("--dry-run", action="store_true",
                   help="API 호출 없이 페이로드만 stdout 출력")
    p.add_argument("--no-thumbnail", action="store_true",
                   help="썸네일 자동 탐지 + 업로드 완전 스킵")
    p.add_argument("--video", type=Path, default=None, metavar="PATH",
                   help="영상 파일 경로 명시 (자동 탐지 오버라이드)")
    p.add_argument("--thumbnail", type=Path, default=None, metavar="PATH",
                   help="썸네일 파일 경로 명시 (자동 탐지 오버라이드)")
    p.add_argument("--force-reupload", action="store_true",
                   help="이미 업로드된 영상 재업로드 (y/N 확인 프롬프트 있음)")
    return p


def _resolve_privacy(args: argparse.Namespace) -> str:
    if args.public:
        return "public"
    if args.unlisted:
        return "unlisted"
    return "private"


def _make_progress_callback():
    """tqdm 진행바 + 콜백 함수 (close 함께 반환).

    tqdm을 lazy import (api 호출 안 되는 dry-run/입력 검증 단계에서 import 비용 회피).
    """
    from tqdm import tqdm
    bar = tqdm(total=100, desc="업로드", unit="%",
               bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}")
    last = [0]

    def on_progress(pct: int) -> None:
        delta = pct - last[0]
        if delta > 0:
            bar.update(delta)
            last[0] = pct

    return on_progress, bar


def _run(args: argparse.Namespace) -> int:
    """실제 업로드 흐름 (T7, 13단계). 예외는 호출자(main)에서 변환."""
    folder = Path(args.folder).expanduser().resolve()
    privacy_status = _resolve_privacy(args)

    # 1) 입력 검증 + body 빌드
    inputs = payload.discover_inputs(
        folder,
        video_override=args.video,
        thumbnail_override=args.thumbnail,
        no_thumbnail=args.no_thumbnail,
    )
    body = payload.build_body(inputs.metadata, inputs.i18n, privacy_status)

    # 2) --dry-run: 페이로드만 출력 + exit 0
    if args.dry_run:
        print("=== DRY RUN: 페이로드 (실제 업로드 안 함) ===")
        print(f"video    : {inputs.video}")
        print(f"thumbnail: {inputs.thumbnail}")
        print(json.dumps(body, indent=2, ensure_ascii=False))
        return 0

    # 3) 캐시 검사 (REQ-12)
    existing = cache.read_cache(folder)
    if existing is not None:
        if not args.force_reupload:
            studio = f"https://studio.youtube.com/video/{existing['video_id']}/edit"
            print(
                f"이미 업로드된 영상입니다.\n"
                f"  videoId: {existing['video_id']}\n"
                f"  업로드 시간: {existing.get('uploaded_at', '(미기록)')}\n"
                f"  스튜디오: {studio}\n"
                f"재업로드하려면 --force-reupload (확인 프롬프트 있음)."
            )
            return 0
        cache.prompt_force_reupload(existing)  # N이면 UserCancelled raise

    # 4) 썸네일 자동 탐지 실패 경고
    will_upload_thumbnail = inputs.thumbnail is not None and not args.no_thumbnail
    if not will_upload_thumbnail and not args.no_thumbnail and inputs.thumbnail is None:
        print(
            f"⚠ 썸네일을 찾을 수 없어 영상만 업로드합니다.\n"
            f"  탐지 시도: {folder}/thumbnail.png, thumbnail.jpg\n"
            f"  --thumbnail <path>로 명시하거나 --no-thumbnail로 명시 스킵하세요.",
            file=sys.stderr,
        )

    # 5) 쿼터 사전 검사 (REQ-11)
    needed = QUOTA_INSERT + (QUOTA_THUMBNAIL if will_upload_thumbnail else 0)
    quota.check_or_die(QUOTA_LOG, needed)

    # 6) OAuth (REQ-01~03)
    creds = auth.get_credentials()

    # 7) Service 빌드
    service = api.build_service(creds)

    # 8) videos.insert (resumable + tqdm + 백오프)
    print(f"[upload] 영상 업로드 중: {inputs.video}")
    on_progress, bar = _make_progress_callback()
    try:
        try:
            video_id = with_retry(
                lambda: api.upload_video(
                    service, body, inputs.video, on_progress=on_progress
                ),
                max_attempts=3,
            )
        except HttpError as e:
            cls, msg = classify_http_error(e)
            if cls is AuthError:
                auth.delete_token()  # REQ-13: 401 시 토큰 삭제
            raise cls(msg) from e
    finally:
        bar.close()
    quota.record_usage(QUOTA_LOG, QUOTA_INSERT)
    print(f"[upload] ✅ 영상 업로드 완료. videoId: {video_id}")

    # 9) 썸네일 (REQ-10, REQ-17 부분 실패 허용)
    thumbnail_uploaded = False
    if will_upload_thumbnail:
        try:
            with_retry(
                lambda: api.set_thumbnail(service, video_id, inputs.thumbnail),
                max_attempts=3,
            )
            quota.record_usage(QUOTA_LOG, QUOTA_THUMBNAIL)
            thumbnail_uploaded = True
            print("[upload] ✅ 썸네일 업로드 완료")
        except HttpError as e:
            # REQ-17: 썸네일 실패해도 영상 유지 + exit 0
            _, msg = classify_http_error(e)
            print(
                f"⚠ 썸네일 업로드 실패: {msg}\n"
                f"영상은 업로드되어 있습니다. 채널 스튜디오에서 수동으로 추가하세요:\n"
                f"  https://studio.youtube.com/video/{video_id}/edit",
                file=sys.stderr,
            )

    # 10) 캐시 저장 (REQ-12, SEC-03)
    cache.write_cache(
        folder,
        video_id=video_id,
        privacy_status=privacy_status,
        quota_used=QUOTA_INSERT + (QUOTA_THUMBNAIL if thumbnail_uploaded else 0),
        thumbnail_uploaded=thumbnail_uploaded,
    )

    # 11) 최종 메시지
    print(
        f"\n[upload] 완료!\n"
        f"  videoId: {video_id}\n"
        f"  privacy: {privacy_status}\n"
        f"  스튜디오: https://studio.youtube.com/video/{video_id}/edit"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        return _run(args)
    except InputError as e:
        print(str(e), file=sys.stderr)
        return 2
    except AuthError as e:
        print(str(e), file=sys.stderr)
        return 1
    except UserCancelled as e:
        print(str(e), file=sys.stderr)
        return 3
    except QuotaError as e:
        print(str(e), file=sys.stderr)
        return 5
    except UploadError as e:
        print(str(e), file=sys.stderr)
        return 6
