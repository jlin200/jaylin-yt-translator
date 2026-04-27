"""J-LIN Studio .exe 빌드 스크립트 (SPEC-GUI-001 T6).

흐름:
    1) 사전 검증 — 민감 파일 부재 강제 (SEC-G01)
    2) icon.ico 자동 생성 (logo.png → multi-resolution)
    3) PyInstaller --onefile --windowed
    4) 사후 검증 — spec 파일 + .exe 바이너리 패턴 grep
    5) 결과 출력 (사이즈, 경로)

사용:
    python build_exe.py

환경 의존:
    - PyInstaller (requirements.txt)
    - Pillow (icon 변환)
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

# Windows cp949 stdout 회피 (em dash, ✓, ❌ 등 출력)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent
SRC = PROJECT_ROOT / "src"
DIST = PROJECT_ROOT / "dist"
BUILD = PROJECT_ROOT / "build"
SPEC = PROJECT_ROOT / "J-LIN-Studio.spec"

LOGO_PNG = SRC / "gui" / "assets" / "logo.png"
ICON_ICO = SRC / "gui" / "assets" / "icon.ico"
LANGUAGES_JSON = SRC / "i18n" / "languages.json"

# SEC-G01: 절대 .exe에 들어가면 안 되는 파일
SENSITIVE_FILES = [
    "credentials.json",
    "token.json",
    ".env",
    ".quota_log.json",
]

# .exe 바이너리에서 발견되면 안 되는 패턴 (사용자 데이터 흔적)
SUSPICIOUS_PATTERNS: list[bytes] = [
    rb'"client_secret"\s*:\s*"[A-Za-z0-9_\-]{10,}"',
    rb'"refresh_token"\s*:\s*"[A-Za-z0-9_\-/]{30,}"',
]


def step(msg: str) -> None:
    print(f"\n[build] {msg}")


def fail(msg: str) -> None:
    print(f"\n❌ {msg}", file=sys.stderr)
    sys.exit(1)


# ===== 1) 사전 검증 =====

def precheck() -> None:
    step("사전 검증 — 민감 파일 부재 확인 (SEC-G01)")
    found = []
    for name in SENSITIVE_FILES:
        if (PROJECT_ROOT / name).exists():
            found.append(name)
    if found:
        fail(
            "다음 민감 파일이 빌드 컨텍스트에 존재합니다 — 빌드 거부.\n"
            + "\n".join(f"  - {PROJECT_ROOT / f}" for f in found)
            + "\n\n해결: 빌드 전에 위 파일들을 다른 폴더로 임시 이동하세요.\n"
            "예) mkdir .build_backup && mv credentials.json token.json .env .quota_log.json .build_backup/"
        )
    print("  ✓ 민감 파일 없음")


# ===== 2) icon.ico 변환 =====

def make_ico() -> None:
    step("아이콘 변환 — logo.png → icon.ico")
    if not LOGO_PNG.is_file():
        fail(f"logo.png가 없습니다: {LOGO_PNG}")

    if ICON_ICO.is_file() and ICON_ICO.stat().st_mtime > LOGO_PNG.stat().st_mtime:
        print(f"  ✓ 캐시 사용 (skip): {ICON_ICO}")
        return

    try:
        from PIL import Image
    except ImportError:
        fail("Pillow가 설치되지 않았습니다. 'pip install Pillow' 후 재시도.")

    img = Image.open(LOGO_PNG)
    img.save(
        ICON_ICO,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"  ✓ 생성: {ICON_ICO} ({ICON_ICO.stat().st_size:,} bytes)")


# ===== 3) 이전 빌드 정리 =====

def clean_old_build() -> None:
    step("이전 빌드 산출물 정리")
    for path in (BUILD, DIST):
        if path.is_dir():
            shutil.rmtree(path)
            print(f"  - 삭제: {path}")
    if SPEC.is_file():
        SPEC.unlink()
        print(f"  - 삭제: {SPEC}")


# ===== 4) PyInstaller =====

def run_pyinstaller() -> None:
    step("PyInstaller --onefile --windowed 실행 (수 분 소요)")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--name", "J-LIN-Studio",
        "--icon", str(ICON_ICO),
        "--add-data", f"{LANGUAGES_JSON};src/i18n",
        "--add-data", f"{LOGO_PNG};src/gui/assets",
        "--add-data", f"{ICON_ICO};src/gui/assets",
        str(PROJECT_ROOT / "gui_main.py"),  # 패키지 외부 entry — 상대 import 회피
    ]
    print("  $ " + " ".join(str(c) for c in cmd[2:]))
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if proc.returncode != 0:
        fail(f"PyInstaller 실패 (exit {proc.returncode})")
    print("  ✓ 빌드 완료")


# ===== 5) 사후 검증 =====

def postcheck() -> Path:
    step("사후 검증 — 산출물 + 민감 정보 패턴 grep")
    exe_path = DIST / "J-LIN-Studio.exe"
    if not exe_path.is_file():
        fail(f".exe 산출물이 생성되지 않았습니다: {exe_path}")

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"  ✓ 산출물: {exe_path} ({size_mb:.1f} MB)")

    if SPEC.is_file():
        spec_text = SPEC.read_text(encoding="utf-8")
        for name in SENSITIVE_FILES:
            if f"'{name}'" in spec_text or f'"{name}"' in spec_text:
                fail(
                    f"spec 파일에 {name!r} 발견 — 빌드 부정 감지\n"
                    f"  spec: {SPEC}"
                )
        print("  ✓ spec 파일 — 민감 파일명 미포함")

    print("  - .exe 바이너리 패턴 grep 진행 중...")
    blob = exe_path.read_bytes()
    for pat in SUSPICIOUS_PATTERNS:
        m = re.search(pat, blob)
        if m:
            exe_path.unlink()
            fail(
                f".exe 안에 의심 패턴 발견 — 산출물 자동 삭제됨\n"
                f"  패턴: {pat!r}\n"
                f"  매칭: {m.group(0)[:120]!r}\n"
                "민감 파일이 빌드에 섞였을 가능성. 프로젝트 루트를 점검하세요."
            )
    print("  ✓ .exe 바이너리 — 의심 패턴 없음")

    return exe_path


def main() -> None:
    print("=" * 64)
    print(" J-LIN Studio — .exe 빌드 (SPEC-GUI-001 T6)")
    print("=" * 64)

    precheck()
    make_ico()
    clean_old_build()
    run_pyinstaller()
    exe_path = postcheck()

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print()
    print("=" * 64)
    print(f"✅ 빌드 성공")
    print(f"   경로:   {exe_path}")
    print(f"   사이즈: {size_mb:.1f} MB")
    print()
    print("다음 단계:")
    print("  1) 더블클릭 또는 다른 PC에서 실행")
    print("  2) 첫 실행 시 마법사 진입 확인 (다른 PC)")
    print("  3) 메인 화면 → URL/제목/본문 입력 → 시작")
    print("=" * 64)


if __name__ == "__main__":
    main()
