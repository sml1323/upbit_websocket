---
# gstack: design-md-format=spec
name: Market Incident Copilot
description: 차분한 분석 도구의 밀도에 판정서의 읽히는 순서. 라이트 종이 위 1px 선, 색은 심각도·조치에만.
colors:
  # 라이트 (기본). 다크는 prefers-color-scheme 으로 자동 — 값은 "## Colors" 표 참고
  background: "#fafafa"
  surface: "#ffffff"
  surface-2: "#f2f2f2"
  surface-3: "#e8e8e8"
  line: "rgba(0, 0, 0, 0.08)"
  line-strong: "rgba(0, 0, 0, 0.14)"
  text: "#171717"
  text-muted: "#4d4d4d"
  text-faint: "#7a7a7a"
  text-ghost: "#a3a3a3"
  primary: "#0f8f82"
  on-primary: "#ffffff"
  accent: "#0f8f82"
  severity-low: "#6b7280"
  severity-medium: "#b07a0a"
  severity-high: "#c2410c"
  severity-critical: "#d92d20"
  action-monitor: "#6b7280"
  action-alert: "#b07a0a"
  action-escalate: "#d92d20"
  success: "#0f8f82"
  warning: "#b07a0a"
  error: "#d92d20"
typography:
  display:
    fontFamily: Pretendard Variable
    fontWeight: 600
    fontSize: 1.625rem
    lineHeight: 1.385
    letterSpacing: -0.02em
  body:
    fontFamily: Pretendard Variable
    fontWeight: 400
    fontSize: 0.875rem
    lineHeight: 1.571
  ui:
    fontFamily: Pretendard Variable
    fontWeight: 500
    fontSize: 0.8125rem
    lineHeight: 1.538
  label:
    fontFamily: Pretendard Variable
    fontWeight: 500
    fontSize: 0.6875rem
    lineHeight: 1.455
    letterSpacing: 0.02em
  mono:
    fontFamily: JetBrains Mono
    fontWeight: 500
    fontSize: 1.25rem
    lineHeight: 1.2
    fontFeature: tnum, zero
rounded:
  xs: 2px
  sm: 4px
  md: 6px
  lg: 8px
  full: 9999px
spacing:
  1: 4px
  2: 8px
  3: 12px
  4: 16px
  5: 24px
  6: 32px
  7: 48px
  list-width: 304px
  list-row: 68px
  detail-pad: 40px
  detail-max: 1040px
  chart-height: 220px
components:
  badge-escalate:
    backgroundColor: "{colors.action-escalate}"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
  badge-alert:
    borderColor: "{colors.action-alert}"
    textColor: "{colors.action-alert}"
    rounded: "{rounded.sm}"
  badge-monitor:
    borderColor: "{colors.line-strong}"
    textColor: "{colors.action-monitor}"
    rounded: "{rounded.sm}"
  list-row-selected:
    backgroundColor: "{colors.surface-2}"
    borderColor: "{colors.accent}"
  input:
    backgroundColor: "{colors.surface}"
    borderColor: "{colors.line}"
    rounded: "{rounded.md}"
  chart-frame:
    backgroundColor: "{colors.surface}"
    borderColor: "{colors.line}"
    rounded: "{rounded.lg}"
  kbd:
    borderColor: "{colors.line-strong}"
    textColor: "{colors.text-faint}"
    rounded: "{rounded.xs}"
---

# Market Incident Copilot — 디자인 시스템

## Overview

**Creative North Star:** "판정서" — 숫자 타일이 아니라 LLM 에이전트의 결론 한 줄과 그 근거 사슬이 먼저 읽히는 분석 도구. 색은 아끼고(심각도·조치·선택에만), 면은 평평하고, 선은 1px.

**Product context:** Upbit 실시간 가격에서 앙상블 지표(z-score·볼린저 %B·RSI·VWAP)로 이상 징후를 감지하고, LangGraph 에이전트가 원인·근거·대안 가설·권장 조치를 쓴 걸 보여주는 리포트 뷰어(`frontend/`, React 19 + Vite + 순수 CSS 변수). 주 관객은 **포트폴리오 면접관**. 30초 안에 "에이전트가 이 이상 징후를 이렇게 판단했고 근거는 이것"이 읽혀야 한다. 동류: Linear(밀도), Vercel 대시보드(여백·타이포), Grafana류 관측 도구(관례).

**Mode per surface:**
- 인시던트 목록(왼쪽) — Operate: 빠르게 훑고 고른다. 밀도 높게, j/k·⌘K.
- 상세 상단부 — Read: 결론 → 근거 순서로 읽는 문서. 여백 넉넉, 상자 없음.
- 탭 패널(리포트·시장 분석·뉴스·지표) — Read: 심층 근거. 본문 폭 64ch.
- 차트 — Operate 보조: "그 순간"을 보여주는 증거 사진. 흑백, 감지 창만 색.

**Reference sites:** https://linear.app, https://linear.app/docs (bg #08090a, text #f7f8f8/#8a8f98, 제목 weight 510~590·tracking -0.022em), https://vercel.com/geist/colors, https://vercel.com/geist/typography (gray-alpha 선, radius 6, heading/label/copy 스케일).

**Key characteristics (첫 5초):**
- 흰 종이 같은 바탕에 한 문장 결론이 크게, 그 밑에 숫자·지표·뉴스·신뢰도·조치가 한 줄 선으로 이어진다.
- 색이 있는 건 심각도 단어, 조치 배지, 감지 순간뿐. 나머지는 회색 계단.
- 상자가 없다. 구분은 1px 선과 간격.
- 숫자는 전부 고정폭(JetBrains Mono)이라 열이 맞는다.
- 아무것도 번쩍이지 않는다. 움직이는 건 분석 완료 순간 한 번.

**미리보기(산출물):** `~/.gstack/projects/sml1323-upbit_websocket/designs/design-system-20261008/preview-top-band-light.html` (기본), `preview-top-band.html` (다크). 상세 상단부 + 목록 + 토큰 시트 + 전/후 팔레트.

## Colors

**Strategy:** Restrained — 액센트 1개(티일) + 회색 계단. 색은 의미가 있을 때만: 심각도 4단, 조치 3종, 선택/포커스/AI 신뢰도.

**Light or dark:** **라이트 기본, 다크 자동.** 관객(면접관)은 낮 사무실, GitHub README 스크린샷, 데모 링크로 본다. 흰 바탕이 "보고서·판정서"의 신뢰감과 인쇄·발표 가독성에 맞다. 다크는 `prefers-color-scheme: dark`로 따라가며 토글 버튼은 두지 않는다. 두 팔레트는 토큰 이름이 같고 값만 다르다. 다크는 라이트의 반전이 아니라 Linear/Geist 계열 **중성 검정**(파란 기 없음)으로 재설계했다. 이전 GitHub 팔레트(#0d1117·#161b22·#30363d·#58a6ff)는 폐기.

| 토큰 | 라이트 (기본) | 다크 | 쓰임 |
|---|---|---|---|
| `--bg` | #fafafa | #0a0a0b | 페이지·목록 바탕 |
| `--surface` | #ffffff | #111113 | 입력·차트 프레임·hover |
| `--surface-2` | #f2f2f2 | #18181b | 선택 행·active |
| `--surface-3` | #e8e8e8 | #1f1f23 | 미터 트랙·꺼진 세그먼트 |
| `--line` | rgba(0,0,0,.08) | rgba(255,255,255,.08) | 기본 구분선 (알파라 어떤 면 위에서도 같은 톤) |
| `--line-strong` | rgba(0,0,0,.14) | rgba(255,255,255,.14) | 입력 테두리·kbd·외곽선 배지 |
| `--text` | #171717 | #ededed | 결론·숫자·코인코드 |
| `--text-2` | #4d4d4d | #a1a1a6 | 본문·요약 |
| `--text-3` | #7a7a7a | #6b6b70 | 라벨·메타·설명 |
| `--text-4` | #a3a3a3 | #48484d | 플레이스홀더·축 숫자 |
| `--accent` | #0f8f82 | #3fb6a8 | 선택 행 2px 바, 포커스 링, AI 신뢰도 트랙, 실시간 점 |
| `--sev-low` | #6b7280 | #8a8f98 | 심각도 '낮음' (회색 = 색이 아님) |
| `--sev-medium` | #b07a0a | #d9a441 | '보통' |
| `--sev-high` | #c2410c | #e8793a | '높음' |
| `--sev-critical` | #d92d20 | #e5484d | '심각', 차트 감지 창 |
| `--act-monitor` | #6b7280 | #8a8f98 | 관찰 MONITOR — 외곽선 배지 |
| `--act-alert` | #b07a0a | #d9a441 | 알림 ALERT — 색 외곽선 배지 |
| `--act-escalate` | #d92d20 | #e5484d | 즉시 대응 ESCALATE — 유일한 채움 배지, 흰 글자 |

**역할 분리 규칙:** 심각도는 **글자색**(단어·세그먼트), 조치는 **배지 배경/외곽선**. 둘이 같은 빨강 계열이어도 처리 방식이 달라 헷갈리지 않는다. 심각도로 조치를, 조치로 심각도를 유추해 그리지 않는다(둘은 다른 질문에 답한다: "신호가 얼마나 강한가" vs "에이전트가 뭘 권하나").

**신뢰도는 액센트:** AI 신뢰도는 의미색이 아니라 액센트 트랙으로 그린다. 결론과 시각적으로 경쟁하지 않는 주석이어야 하고, 라벨에 "모델 자체 평가 · 정확도 확률 아님"을 붙인다.

**차트:** 종가 `--text-2` 1.5px, VWAP `--text-3` 점선, 볼린저 밴드 `rgba(0,0,0,.05)`(다크 `.05` 흰색), 거래량 `line` 톤. **감지 ±3분 창만** `--sev-critical`(해당 심각도 색) — 창 배경 7% 틴트, 그 구간 종가선 2px, 감지 수직선 1px, 라벨 `감지 HH:mm`. 초록/빨강 캔들은 쓰지 않는다. 이 화면은 시세가 아니라 "그 순간"을 보는 화면이다.

## Typography

**본문/UI/디스플레이: Pretendard Variable.** 한글 본문(에이전트의 결론·근거)이 주인공이라 한 가족으로 간다 — Linear가 Inter 하나로 끝내는 것과 같은 이유. 굵기(400/500/600)와 크기로만 위계를 만든다. Pretendard는 Inter 골격에 한글이 붙어 있어 Linear/Vercel 레퍼런스와 리듬이 맞고, 자간 -0.02em에서 제목이 단단해진다. 대안으로 Wanted Sans(조금 좁고 중립)도 검증됐다.

**숫자: JetBrains Mono.** 앙상블 점수·가격·시각·incident_id·%는 전부 이걸로. `font-variant-numeric: tabular-nums; font-feature-settings: 'zero'`. 목록의 점수 열과 레일의 숫자가 세로로 맞는다.

| 역할 | 크기/행간 | 굵기 | 자간 | 쓰임 |
|---|---|---|---|---|
| display | 26/36 | 600 | -0.02em | 결론 헤드라인(`report.root_cause`). 최대 32em |
| body | 14/22 | 400 | 0 | 요약·근거·대안. 최대 64ch |
| ui | 13/20 | 500 | -0.01em(코인코드) | 목록 행·탭·메타·버튼 |
| label | 11/16 | 500 | +0.02em | 레일 노드 라벨·패널 소제목·칩 |
| num | 20/24 | 500 | 0 | 레일 노드 값 (JetBrains Mono) |
| num-sm | 13/20 | 500 | 0 | 목록 점수·메타 ID·축 |

**한글 조판:** `word-break: keep-all; overflow-wrap: anywhere;` 전역. 라벨을 장식용으로 대문자화하지 않는다(한글 옆 영문 ESCALATE 같은 코드명은 예외, 자간 0.01em).

**로딩:**
```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap">
```
Pretendard는 dynamic subset(글리프 단위 분할)이라 첫 로드가 가볍다. 폴백 `'Apple SD Gothic Neo', sans-serif` / `ui-monospace, Menlo, monospace`. `-apple-system`/`system-ui`를 주 서체로 두지 않는다.

## Layout

- **셸:** `grid-template-columns: 304px 1fr; height: 100vh`. 목록·상세 각자 스크롤.
- **목록 행 68px**(Linear 밀도): 1줄 코인코드(ui 600) + 심각도 단어(label, 심각도색) / 2줄 조치·신뢰도·원인 한 줄 미리보기(12px, text-3, ellipsis) / 오른쪽 점수(num-sm)·상대시각(label). 선택 행은 `--surface-2` + 왼쪽 2px `--accent` 바(상하 10px 인셋).
- **상세:** 패딩 32 상 / 40 좌우, 콘텐츠 최대 1040. 읽는 순서는 아래 "상단부 구조" 고정.
- **근거 레일:** 5열 균등 그리드, 위에 1px `--line-strong` 선. 노드 = label → 값(num 20) → 설명(12px text-3). 노드 간 24. 순서는 LangGraph 노드 순서: 탐지(앙상블) → 지표 → 뉴스 → AI 신뢰도 → 권장 조치.
- **차트 220px** 고정 높이, 프레임 `--surface` + `--line` + radius 8. 레일과 32 간격.
- **탭** 아래 패널은 64ch. 탭은 심층 근거만 담는다 — 결론·근거 요약·조치는 탭 밖(첫 화면)에 있어야 한다.
- **반응형:** ≤1100 목록 256·상세 패딩 24. ≤900 목록 위/상세 아래(또는 목록→상세 내비), 레일 2열. 읽는 순서는 유지.

### 상단부 구조 (적용 예시)

```html
<article class="detail">
  <div class="meta">
    <span class="coin">LIT</span><span class="sev sev-critical">심각</span>
    · 10월 4일 02:34 KST · 4일 전 · <span class="num">57b32e03</span> <span class="ghost">데모</span>
  </div>
  <h2 class="headline">{report.root_cause}</h2>
  <p class="summary">{report.summary}</p>

  <div class="rail">
    <div class="node"><span class="label">앙상블 점수</span><span class="v num">1.00 <small>/ 임계 0.50</small></span><span class="d">지표 4개 가중 합산</span></div>
    <div class="node"><span class="label">발화 지표</span><span class="v num">4 <small>/ 4</small> [segs]</span><span class="d">Z 3.1σ · %B 1.08 · RSI 82.9 · VWAP +3.9%</span></div>
    <div class="node"><span class="label">뉴스</span><span class="v">긍정 <small>주요 언론</small></span><span class="d">관련도 0.8 · 헤드라인 3건</span></div>
    <div class="node"><span class="label">AI 신뢰도</span><span class="v num">90% <small>높음</small></span>[accent track]<span class="d">Report 노드 자체 평가 · 정확도 확률 아님</span></div>
    <div class="node"><span class="label">권장 조치</span><span class="badge escalate">즉시 대응 ESCALATE</span><span class="d">전 지표 발화 + 과열 → 긴급 확인</span></div>
  </div>

  <figure class="chart">…흑백 종가·VWAP·밴드, 감지 ±3분만 심각도색…</figure>
  <nav class="tabs">리포트 1 · 시장 분석 2 · 뉴스 3 · 지표 4</nav>
</article>
```

```css
.meta     { display:flex; gap:12px; font:500 13px/20px var(--font-sans); color:var(--text-3); }
.meta .coin { color:var(--text); font-weight:600; letter-spacing:-0.01em; }
.headline { margin:12px 0 0; font:600 26px/36px var(--font-sans); letter-spacing:-0.02em; color:var(--text); max-width:32em; }
.summary  { margin:12px 0 0; color:var(--text-2); max-width:64ch; }
.rail     { margin-top:24px; display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); border-top:1px solid var(--line-strong); }
.node     { padding:12px 16px 0 0; display:flex; flex-direction:column; gap:2px; }
.node .v  { font:500 20px/24px var(--font-mono); font-variant-numeric:tabular-nums; color:var(--text); }
.node .v small { font:400 13px var(--font-sans); color:var(--text-3); }
.badge    { height:24px; padding:0 8px; border-radius:4px; font:600 12px var(--font-sans); }
.badge.escalate { background:var(--act-escalate); color:#fff; }
.badge.alert    { color:var(--act-alert); border:1px solid var(--act-alert); }
.badge.monitor  { color:var(--act-monitor); border:1px solid var(--line-strong); }
.chart    { margin-top:32px; height:220px; background:var(--surface); border:1px solid var(--line); border-radius:8px; }
```

지금 코드 대비 바뀌는 것: `.d-head h2`(코인코드 28px) → 메타 줄로 축소, `.meters` 3개 → `.rail` 5노드, 리포트 탭의 `원인 추정`/`요약` → 상단 `headline`/`summary`로 승격, `PriceChart`의 `SEV_COLOR` 캔들 → 흑백 + 감지 창.

## Elevation & Depth

그림자 없음. 층은 **면 색 계단**(bg → surface → surface-2)과 **1px 알파 선**으로만. 떠 있는 것(⌘K 팔레트·툴팁·토스트)만 Geist식 `0 0 0 1px line-strong, 0 8px 24px rgba(0,0,0,.08)`(다크 `.5`). 글로우·zero-offset 할로 금지. 목록 머리의 블러 배경(backdrop-filter)은 제거 — 불투명 `--bg`.

## Shapes

- 2px: kbd, 세그먼트, 미터 트랙
- 4px: 배지, 칩, 탭 포커스 링
- 6px: 입력, 목록 행 hover, ⌘K 항목
- 8px: 차트 프레임, ⌘K 패널(12px 허용)
- 레일·선·구분은 각(0). 알약(9999)은 쓰지 않는다 — 조치 배지는 사각.
- 중첩 시 안쪽 radius = 바깥 − 간격.

## Components

- **목록 행:** hover `--surface`, active `--surface-2`, selected `--surface-2` + 2px accent 바, focus-visible 2px accent outline(-2px). 새 인시던트는 선택 행을 밀지 않고 "새 인시던트 N건" 컨트롤로 노출.
- **칩(필터):** 22px, `--line` 테두리, 꺼짐 text-2 / 켜짐 `--surface-2` + text. 심각도 칩의 점은 6px 사각(radius 1).
- **배지(조치):** 위 표. 버튼처럼 보이면 안 된다 — 권고이지 실행이 아니다. hover 없음.
- **레일 노드:** 자체 hover 없음. 값 클릭 시 해당 탭으로 점프(Reference Focus 모션).
- **AI 신뢰도 트랙:** 3px, 120px, `--surface-3` 위 `--accent`. 같은 인시던트 값 갱신 때만 width 전환.
- **탭:** 13px text-3 / 선택 text + 밑줄 1px `--text`(액센트 아님). 단축키 kbd 동반.
- **입력(검색):** 30px, `--surface` + `--line`, focus-within `--accent` 테두리.
- **툴팁:** `--surface` + `--line-strong`, 12px/18px, 그림자 위 규칙.
- **빈/로딩/오류:** "분석 대기 중"(has_report=false), "자료 없음"(evidence 비어 있음), "차트를 불러오지 못했어"(오류). 뉴스 없음은 "관련 뉴스 없음"이 아니라 "뉴스 자료 없음" — 검색이 끝났다는 뜻이 아니다.

## Do's and Don'ts

- Do: LLM 결론(`root_cause`)을 상세의 첫 번째 큰 글자로. 코인코드는 메타 줄.
- Do: 숫자는 전부 `.num`(JetBrains Mono + tabular-nums).
- Do: 심각도는 글자색, 조치는 배지. 둘을 섞어 그리지 않는다.
- Do: 차트는 흑백, 감지 ±3분만 색.
- Do: 대안 가설·자료 한계를 첫 화면 또는 리포트 탭 최상단에 둔다 — 판단의 경계가 보여야 한다.
- Don't: 숫자 KPI 타일·미터 카드 3개. 상자 안에 숫자를 가두지 않는다.
- Don't: 카드 안 카드, 그림자 쌓기, 글로우, 블러 머리.
- Don't: 알약 배지, 왼쪽 색 띠 카드(목록 선택 바 2px accent만 예외).
- Don't: 펄스 점·무한 애니메이션. "실시간"은 정적 점 + 글자.
- Don't: 선택 전환 때 숫자 보간(NumberFlow). 같은 인시던트 값 갱신에만.
- Don't: `-apple-system`/`system-ui`를 주 서체로.

## Motion

- **Approach:** minimal-functional. 셸·열 폭·축·감지 마커·목록 위치는 절대 움직이지 않는다. Recharts 기본 진입 애니메이션 off.
- **Easing:** enter `cubic-bezier(0.2, 0, 0, 1)` · exit ease-in · chain `cubic-bezier(0.16, 1, 0.3, 1)`
- **Duration:** cut 120ms · tip 125ms · revise 240ms · chain 420ms
- **네 가지 전환:**
  - *Incident Cut* 120ms — 인시던트 선택 시 상세 전체 opacity 0→1만. 슬라이드·숫자 보간 없음.
  - *Tooltip* 125ms — opacity + scale .97→1, transform-origin 앵커.
  - *Value Revise* 240ms — 같은 인시던트의 점수·신뢰도 갱신에만 NumberFlow·트랙 width.
  - *Evidence Chain* 420ms — 분석 대기였던 인시던트가 완료되는 순간 한 번: 레일 선이 좌→우 scaleX, 노드 5개가 60ms 간격 fade. **The one authored moment.**
- `prefers-reduced-motion: reduce`: Chain·Cut 즉시, Tooltip opacity만.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-08 | 초기 디자인 시스템 생성 (/design-consultation) | Linear·Vercel Geist 공개 페이지 실측 + Codex·Claude 독립 제안 비교 |
| 2026-10-08 | 메터 3개 삭제 → 결론 헤드라인 + 근거 레일 5노드 | 기억점 "근거가 보인다". 내 초안·Codex·Claude 서브에이전트 세 제안이 독립적으로 수렴 |
| 2026-10-08 | 심각도=글자색 / 조치=배지 / 신뢰도=액센트 주석 | 서로 다른 질문에 답하는 값이 같은 색 체계로 보이면 안 됨 (Codex 제안 채택) |
| 2026-10-08 | 차트 흑백 + 감지 ±3분만 색 | 시세 화면이 아니라 "그 순간" 화면 (Claude 서브에이전트 제안 채택) |
| 2026-10-08 | GitHub 팔레트 폐기 → 중성 회색 계단 + 알파 선 | 레퍼런스(Linear/Geist)와 일치. 외부 의견의 따뜻한 차콜은 레퍼런스와 멀어 미채택 |
| 2026-10-08 | 라이트 기본 + 다크 자동 (원래 다크 전제에서 변경) | 사용자: "꼭 검은 테마 안 해도 됨". 관객 장면이 낮·README·발표라 흰 바탕이 신뢰감·가독성에 유리 |
| 2026-10-08 | Pretendard Variable + JetBrains Mono | 한글 본문이 주인공, 한 가족 + 숫자 전용. Paperlogy 디스플레이·도장 모션은 "차분한 신뢰"에 과해 미채택 |
