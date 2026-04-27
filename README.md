<div align="center">

<img src="src/gui/assets/logo.png" alt="J-LIN Studio" width="160" />

# J-LIN Studio

**창작자를 위한 영상 번역 · YouTube 업로드 워크스페이스**

한국어로 작성한 YouTube 영상 제목·설명을 **50개국 언어**로 자동 번역하고,
영상에 다국어 메타데이터를 한 번에 등록합니다.

[다운로드](#-빠른-시작) · [발급 가이드](#-google-oauth-발급-약-5분) · [FAQ](#-자주-묻는-질문)

</div>

---

## ✨ 무엇을 하나요?

이미 YouTube에 올린 영상의 **제목·설명을 입력**하면, AI가 즉시 50개국 언어로 번역해서
영상에 다국어 메타데이터로 등록합니다. 시청자가 자기 언어로 YouTube를 보면 자동으로
**해당 언어로 제목·설명이 표시**되어 글로벌 노출이 늘어납니다.

영상 파일을 다시 올리지 않습니다 — **기존 영상의 메타데이터만 갱신**하므로 빠르고 안전합니다.

---

## 🚀 빠른 시작

### 1. 다운로드
[GitHub Releases 페이지](https://github.com/YOUR-USERNAME/jaylin-yt-translator/releases)에서
**`J-LIN-Studio.exe`** 다운로드 (약 90 MB).

### 2. 실행
다운로드한 파일 더블클릭.

> **"Windows의 PC 보호" 경고가 떠요?**
> → "추가 정보" → "실행" 클릭. 정상입니다 (상세는 [FAQ](#-자주-묻는-질문) 참고).

### 3. 첫 실행 — 환경 설정 마법사
3단계 마법사가 자동으로 뜹니다:

| 단계 | 할 일 |
|---|---|
| 1 / 3 | 환영 화면 → **시작** |
| 2 / 3 | Google OAuth `credentials.json` 파일 선택 ([발급 가이드](#-google-oauth-발급-약-5분)) |
| 3 / 3 | Gemini API 키 입력 ([발급 가이드](#-gemini-api-키-발급-약-2분)) |

완료하면 메인 화면이 뜹니다. **다음 실행부터는 마법사가 뜨지 않습니다.**

---

## 💡 사용 방법

메인 화면에서 4가지 입력 후 **"번역 및 자동 업로드 시작"** 클릭:

| 필드 | 입력 |
|---|---|
| **유튜브 영상 주소** | `https://youtube.com/watch?v=ABC1234567` 또는 11자 영상 ID |
| **유튜브 제목** | 한국어 제목 |
| **유튜브 본문** | 한국어 설명 (여러 줄 가능) |
| **번역 언어** | Tier 1(6개) / Tier 2(21개) / Tier 3(50개) 중 선택 |

진행률이 0~100%로 보이고, 완료되면 **YouTube Studio 열기** 버튼으로 결과를 바로 확인할 수 있습니다.

> 💰 **비용**: Tier 1 기준 영상 1개당 약 **$0.0005** (Gemini Flash) + YouTube API 쿼터 50 units.
> 하루 200개 영상까지 무료 한도 안에서 처리 가능합니다.

---

## 🔑 Google OAuth 발급 (약 5분)

YouTube 영상에 메타데이터를 등록하려면 **Google이 "이 앱이 내 채널에 접근해도 된다"** 고
허락하는 인증 파일이 필요합니다. 본인 채널만 접근하므로 안전합니다.

### 발급 절차

1. [Google Cloud Console](https://console.cloud.google.com/) 접속 (Google 계정 로그인)
2. 좌측 상단 **프로젝트 선택** → **새 프로젝트** → 이름 입력 (예: `jlin-studio`)
3. 좌측 메뉴 **API 및 서비스 → 라이브러리** → "**YouTube Data API v3**" 검색 → **사용** 클릭
4. **API 및 서비스 → OAuth 동의 화면**:
   - User Type: **외부** 선택 → 만들기
   - 앱 이름, 사용자 지원 이메일, 개발자 연락처 입력 → 저장
   - **테스트 사용자**에 본인 Gmail 추가
5. **API 및 서비스 → 사용자 인증 정보**:
   - **+ 사용자 인증 정보 만들기** → **OAuth 클라이언트 ID**
   - 애플리케이션 유형: **데스크톱 앱**
   - 이름 입력 → 만들기
   - 다운로드 버튼 클릭 → JSON 파일이 컴퓨터로 저장됨
6. 다운로드된 JSON 파일을 마법사 2단계에서 선택

> ⚠️ 이 파일은 **채널의 마스터키**입니다. 절대 공유하거나 GitHub에 올리지 마세요.

---

## 🔑 Gemini API 키 발급 (약 2분)

번역에 사용할 Google AI 키. **무료** (분당 60회 한도).

1. [Google AI Studio](https://aistudio.google.com/apikey) 접속 (Google 계정 로그인)
2. **Get API key** → **Create API key** 클릭
3. `AIzaSy`로 시작하는 39자 키가 표시됨 → **복사**
4. 마법사 3단계 입력칸에 붙여넣기

> ⚠️ API 키도 **본인만 알아야 합니다**. 채팅/이메일/스크린샷 공유 주의.

---

## 📁 데이터 저장 위치

마법사 완료 시 모든 키가 다음 위치에 저장됩니다 (Windows 사용자별 격리):

```
C:\Users\<사용자명>\AppData\Roaming\jaylin-yt-translator\
├── credentials.json     ← Google OAuth
├── token.json           ← 자동 발급 (첫 업로드 시 브라우저 인증)
├── .env                 ← Gemini API 키
└── .quota_log.json      ← 일일 쿼터 사용량
```

- **다른 사람과 분리됨**: 같은 PC에 다른 Windows 사용자가 있어도 각자의 폴더 사용
- **앱 삭제 시 함께 정리하려면**: 위 폴더 직접 삭제

---

## ❓ 자주 묻는 질문

<details>
<summary><b>Q. "Windows의 PC 보호" 파란 경고가 떠요</b></summary>

A. 정상입니다. Microsoft 코드 사이닝 인증서(연 $300+)를 받지 않아 "Unknown publisher"로 표시됩니다.

**"추가 정보"** 클릭 → **"실행"** 버튼이 나타나면 클릭하세요.
</details>

<details>
<summary><b>Q. 영상이 다시 업로드되나요? 시간 오래 걸리나요?</b></summary>

A. 아니요. **메타데이터(제목·설명)만 갱신**합니다.
영상 파일은 그대로이고, YouTube에 등록된 텍스트만 바뀝니다.
보통 30초~1분 안에 완료됩니다.
</details>

<details>
<summary><b>Q. 다국어 표시 어디서 확인해요?</b></summary>

A. YouTube Studio에서 본인 영상 → **자막** 탭 → 등록된 언어 목록 확인.
또는 영상 URL에 `?hl=en` (영문), `?hl=ja` (일본어) 등을 붙여서
시청자 언어 전환 결과를 미리 볼 수 있습니다.
</details>

<details>
<summary><b>Q. 무료인가요?</b></summary>

A. 거의 무료입니다.
- **Gemini API**: 무료 한도 안에서 분당 60회
- **YouTube API**: 일일 10,000 unit (영상 1개 = 50 units → 일 200개 무료)
- 영상 1개 번역 + 등록 비용은 **약 $0.0005** (실측)
</details>

<details>
<summary><b>Q. 키 변경/재발급은 어떻게 하나요?</b></summary>

A. 메인 화면 우측 하단의 **"환경 설정"** 버튼 클릭 → 마법사 다시 진행.
또는 위의 [데이터 저장 위치](#-데이터-저장-위치) 폴더를 삭제하고 앱을 재실행하면
첫 실행 마법사가 다시 뜹니다.
</details>

<details>
<summary><b>Q. 영상이 비공개여도 동작해요?</b></summary>

A. 네. 영상의 공개 여부와 무관하게 본인 소유 영상이면 메타데이터를 갱신할 수 있습니다.
공개·비공개·일부 공개 모두 동일하게 작동합니다.
</details>

<details>
<summary><b>Q. 50개 언어 다 등록하면 더 좋은가요?</b></summary>

A. **꼭 그렇지 않습니다.** Plimate 채널 실제 시청자 분포 기준
**Tier 1 (영어/일본어/태국어/베트남어/대만 중국어/브라질 포르투갈어 6개)**
이 가장 효과적입니다. 본인 채널 시청자 분포를 보고 결정하세요.
</details>

<details>
<summary><b>Q. 어디까지 자동인가요?</b></summary>

A. **번역 + 메타데이터 등록**만 자동입니다.
영상 업로드, 썸네일, 시청 시간, 제목 카피라이팅 등은 본인이 해야 합니다.
이 도구는 "다국어 메타데이터 등록 1초"에 집중합니다.
</details>

---

## 🌐 English (brief)

**J-LIN Studio** is a Windows desktop app that auto-translates your YouTube video's
Korean title & description into up to 50 languages and registers them as multi-locale
metadata via the YouTube Data API.

**Quick start**: Download `J-LIN-Studio.exe` from
[Releases](https://github.com/YOUR-USERNAME/jaylin-yt-translator/releases) → double-click →
follow the 3-step wizard (Google OAuth + Gemini API key) → paste video URL → done.

Built with PySide6 + PyInstaller. ~90 MB single .exe. Korean UI.

---

## 📜 라이선스 / 의존성

- 본 앱 코드: MIT
- Qt for Python (PySide6): LGPL v3
- 사용 API: Google YouTube Data API v3, Google Gemini API

## 📮 문의

- 영상/텍스트 가이드: Plimate 유튜브 채널
- 버그 제보: GitHub Issues 페이지
- 일반 문의: 추후 추가
