# R1 뉴스 도구 반환 개선 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `search_news`가 기사 URL과 조회 상태(`ok / empty / error / unavailable`)를 담은 `NewsSearchResult`를 반환하고, 뉴스 노드는 기사가 있을 때만 기사 JSON을 LLM에 넘기며 기사 0건은 코드가 결과를 정한다.

**Architecture:** 요청 실패 분류(`_get_json`)와 공급자별 응답 해석(`_fetch_cryptopanic`, `_fetch_serpapi`)을 나누고,
공급자를 순서대로 확인하는 `search_news`가 시도 기록으로 전체 상태를 정한다(`_decide_status`).
반환 계약은 `schemas.py`의 Pydantic 모델이 검증한다. 뉴스 노드는 전체 상태를 보고 LLM 호출 여부를 정한다.

**Tech Stack:** Python 3.13, Pydantic 2.13.4, langchain-core 1.4.8(`@tool`), langchain-openai(structured output), requests 2.34.2, pytest 9.1.1

**Spec:** [ROADMAP.md](ROADMAP.md) §4 “R1 — 뉴스 도구 반환 개선 상세 설계” (2026-10-02 사용자 최종 승인)

**검증 근거:** 2026-10-02 저장소 밖 임시 복사본에 이 문서의 코드 블록만 작업 순서대로 적용했다.
각 단계의 실패·통과 수(127 → 151 → 173 → 194 → 201 passed)와 비교 스크립트의 변경 전후 출력이 이 문서의 Expected와 일치했다.
저장소 코드에는 아직 적용하지 않았다.

## Global Constraints

- Python은 `.venv/bin/python`만 사용한다. `uv run`·`uv sync` 금지 — `pyproject.toml` 의존성이 비어 있어 `.venv` 패키지가 지워진다.
- 테스트는 `.venv/bin/python -m pytest tests ...`로만 실행한다. 루트에서 경로 없이 `pytest`를 실행하면 `scratch/test_all_structured.py`가 실제 OpenAI를 호출한다.
- 테스트에서 실제 HTTP·OpenAI·DB를 호출하지 않는다. `.env`의 실제 SerpAPI 키가 import 시점에 로드되므로 키와 `requests.get`을 반드시 patch한다.
- 커밋은 사용자가 요청할 때만 한다. 요청을 받으면 `master`에서 새 브랜치를 만든 뒤 바꾼 파일만 경로를 지정해 stage한다. `git add -A`·`git add .` 금지.
- 이 계획에 적힌 파일만 수정한다. `scratch/`, `.specify/`, 다른 학습 트랙 문서 등 기존 미커밋 작업은 건드리지 않는다.
- 반환값·로그·`NewsEvidence`에 API 키·요청 URL·예외 원문을 넣지 않는다. 뉴스 경로 로그는 공급자·상태·오류 분류·HTTP 상태 코드·제외 건수·예외 클래스 이름만 남긴다.
- 공급자 순서 CryptoPanic → SerpAPI와 최초 유효 기사 목록 채택을 유지한다. 공급자 추가·결과 병합·모델의 도구 선택·CryptoPanic v2 이전은 하지 않는다.
- `NewsEvidence` 스키마와 `with_structured_output(NewsEvidence, method="json_schema")`는 바꾸지 않는다. 시장·리포트 노드와 리포트 프롬프트도 바꾸지 않는다.
- 기사는 최대 5건(`MAX_NEWS_ARTICLES = 5`)이다. URL은 앞뒤 공백만 제거하고 원래 문자열 그대로 보존한다(`HttpUrl` 사용 금지).
- learning 모드: Task 3의 `_decide_status`는 사용자 작성 지점이다. 실행자가 먼저 채우지 않는다.

## Review Focus

1. API 키가 메시지에 담긴 requests 예외(연결 실패·타임아웃) → 로그와 반환값에 키가 없어야 함 — Task 3 `TestNoSecretLeak`, Task 4 `test_tool_failure`·`test_llm_failure_hides_exception_text`.
2. SerpAPI 결과 없음 응답(HTTP 200 + `error` 메시지) → `error`가 아니라 `empty` — Task 2 `test_no_results_message_is_empty_not_error`.
3. CryptoPanic 키가 설정된 상태에서 폐기된 v1 엔드포인트가 404 JSON을 줌 → `http_error`로 기록하고 SerpAPI로 계속 — Task 2 `test_retired_v1_endpoint_is_http_error`, Task 3 매트릭스 `("error", "ok")`.
4. 정상 기사 사이에 깨진 항목(link 없음·`javascript:`·공백 제목·dict 아님)이 섞임 → 깨진 항목만 제외, 전부 깨지면 `invalid_response` — Task 2 `test_drops_only_invalid_items`·`test_all_items_invalid_is_invalid_response`.
5. 한글·쿼리 문자열이 있는 URL → LLM 입력까지 같은 문자열(정규화·`\u` 이스케이프 없음) — Task 1 `test_keeps_url_string_as_given`, Task 4 `test_provider_url_reaches_llm_input`.

## 실행 전에 알아 둘 영향

- 리포트 화면(`src/api/main.py`의 `_format_news`)은 바꾸지 않는다. `error`는 “관련 뉴스: • [ERROR] 뉴스 조회 실패”, `empty`·`unavailable`은 “관련 뉴스 없음”으로 보인다. 정리는 R3에서 한다.
- `scratch/check_news.py`는 Task 3 이후(`_search_*` 삭제), `scratch/test_all_structured.py`는 Task 4 이후(문자열 스텁) 동작하지 않는다. 미추적 실험 파일이라 수정하지 않는다.
- 뉴스 노드의 LLM 실패 로그가 예외 메시지 대신 클래스 이름만 남겨 디버깅 정보가 줄어든다. 보안 규칙과 맞바꾼 것이다.
- 작업은 현재 작업 트리에서 한다. 설계·계획 문서가 미추적이라 git worktree에서는 보이지 않는다.

## File Structure

| 파일 | 변경 | 책임 |
|---|---|---|
| `src/agent/schemas.py` | 수정 | 뉴스 도구 반환 계약 모델 추가 |
| `src/agent/tools/search_news.py` | 수정 | 요청 실패 분류, 공급자별 응답 해석, 순서대로 확인, 전체 상태 결정 |
| `src/agent/news_agent.py` | 수정 | 상태별 LLM 호출 여부, 기사 JSON 입력, 안전한 fallback |
| `src/agent/prompts.py` | 수정 | `NEWS_SYSTEM_PROMPT` 입력 설명 추가, “뉴스가 없으면” 규칙 제거 |
| `tests/test_news_contract.py` | 생성 | 계약 검증 규칙 |
| `tests/test_agent_tools.py` | 수정 | 공급자 해석·실패 분류·상태 매트릭스·키 노출·도구→노드 경로 |
| `tests/test_multi_agent.py` | 수정 | 뉴스 노드 동작 |
| `docs/agent-improvement/baseline/search_news_compare.py` | 생성 | 변경 전후 비교 스크립트(mock 전용) |
| `docs/agent-improvement/{ROADMAP,CURRENT,LEARNING_LOG}.md` | 수정 | 진행 상태·검증 근거 |

## 사용자 작성 지점 진행 방식

- 실행자는 함수 서명·docstring·TODO·실패하는 테스트까지 준비하고 멈춘다. 뼈대를 먼저 주지 않는다.
- 사용자가 막히면 막힌 지점을 (a) 입력에서 상태 꺼내기 (b) 우선순위 순서 표현 (c) 반환 중에서 고르게 한다.
  그다음 빈칸 2~3개 뼈대와 REPL 스니펫을 주고, 빈칸마다 직전 변수 값을 print로 확인하게 한다.
- 사용자가 실행자에게 맡기면 참고 구현을 사용하고, 기록에 “실행자 작성”으로 남긴다. 사용자가 쓴 경우 “사용자 작성”으로 구분한다.

---

### Task 0: 변경 전 기준 보존 (R1.0)

**Files:**
- Create: `docs/agent-improvement/baseline/search_news_compare.py`
- Modify: `docs/agent-improvement/LEARNING_LOG.md`, `docs/agent-improvement/ROADMAP.md`, `docs/agent-improvement/CURRENT.md`

**Interfaces:**
- Consumes: 현재 `src.agent.tools.search_news` (문자열 반환, `CRYPTOPANIC_API_KEY`·`SERPAPI_API_KEY`·`requests`·`logger` 모듈 전역)
- Produces: 비교 스크립트. 문자열 반환(변경 전)과 `NewsSearchResult` 반환(변경 후) 모두에서 돈다. Task 5가 다시 실행한다.

- [ ] **Step 1: 기준 상태 확인**

```bash
git rev-parse --short HEAD
git status --short src tests
.venv/bin/python -m pytest tests -q -p no:cacheprovider
```

Expected: `1fc7119`, 두 번째 명령은 출력 없음, `127 passed, 1 warning`. 다르면 멈추고 사용자에게 알린다.

- [ ] **Step 2: 비교 스크립트 작성**

`docs/agent-improvement/baseline/search_news_compare.py`:

```python
"""search_news 변경 전후 비교 (R1.0 기준선). mock 전용 — 실제 API·LLM 호출 없음.

같은 공급자 응답을 넣고 도구 반환값과 '실패 로그에 키가 찍히는지'를 출력한다.
문자열을 반환하던 변경 전 버전과 NewsSearchResult 를 반환하는 변경 후 버전 모두에서 돈다.

실행 (저장소 루트, ⚠️ uv run 금지):
    .venv/bin/python docs/agent-improvement/baseline/search_news_compare.py

변경 전 버전 재현:
    git worktree add ../upbit_r1_before 1fc7119
    cd ../upbit_r1_before && <저장소>/.venv/bin/python <저장소>/docs/agent-improvement/baseline/search_news_compare.py
    cd - && git worktree remove ../upbit_r1_before
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import requests

sys.path.insert(0, os.getcwd())
import src.agent.tools.search_news as sn  # noqa: E402

FAKE_KEY = "FAKE-KEY-0000"  # 실제 키가 아니다. 로그 노출 여부 확인용 표식
SERP_URL = f"https://serpapi.com/search.json?api_key={FAKE_KEY}&q=BTC"


def response(status: int, payload: object) -> requests.Response:
    resp = requests.Response()
    resp.status_code = status
    resp._content = json.dumps(payload).encode("utf-8")
    resp.encoding = "utf-8"
    resp.url = SERP_URL  # 실제 requests 처럼 HTTPError 메시지에 URL 이 들어가게
    resp.reason = "Unauthorized" if status == 401 else "OK"
    return resp


ITEM = {"title": "Bitcoin ETF inflows hit record", "link": "https://news.example.com/a?id=1&lang=한글", "source": "CoinDesk"}
SUCCESS = {"status": "Success"}
CASES = [
    ("1) SerpAPI 기사 2건", FAKE_KEY, lambda: response(200, {"search_metadata": SUCCESS, "news_results": [
        ITEM, {"title": "비트코인 급등", "link": "https://news.example.kr/b", "source": "한경"}]})),
    ("2) SerpAPI 정상 0건", FAKE_KEY, lambda: response(200, {
        "search_metadata": SUCCESS, "error": "Google hasn't returned any results for this query."})),
    ("3) SerpAPI 401", FAKE_KEY, lambda: response(401, {"error": "Invalid API key."})),
    ("4) SerpAPI 연결 타임아웃", FAKE_KEY, requests.ConnectTimeout(f"Max retries exceeded with url: {SERP_URL}")),
    ("5) 두 키 모두 없음", "", AssertionError("키가 없으면 요청하면 안 됨")),
    ("6) 1건만 깨짐(link 없음)", FAKE_KEY, lambda: response(200, {"search_metadata": SUCCESS, "news_results": [
        {"title": "link 없는 항목"}, ITEM]})),
]


def show(output: object) -> str:
    if isinstance(output, str):
        return output
    return output.model_dump_json(ensure_ascii=False)


for name, serp_key, effect in CASES:
    get = MagicMock()
    if callable(effect) and not isinstance(effect, BaseException):
        get.side_effect = lambda *a, effect=effect, **k: effect()
    else:
        get.side_effect = effect
    with patch.object(sn, "CRYPTOPANIC_API_KEY", ""), patch.object(sn, "SERPAPI_API_KEY", serp_key), \
         patch.object(sn.requests, "get", get), patch.object(sn, "logger") as logger:
        output = sn.search_news.invoke({"coin_code": "BTC"})
    logged = " ".join(str(arg) for call in logger.method_calls for arg in call.args)
    print(f"--- {name} | 로그에 키 노출: {FAKE_KEY in logged}")
    print(show(output))
```

- [ ] **Step 3: 변경 전 출력 기록**

Run: `.venv/bin/python docs/agent-improvement/baseline/search_news_compare.py`

Expected:

```text
--- 1) SerpAPI 기사 2건 | 로그에 키 노출: False
[BTC] 관련 뉴스 2건:
1. Bitcoin ETF inflows hit record (CoinDesk)
2. 비트코인 급등 (한경)
--- 2) SerpAPI 정상 0건 | 로그에 키 노출: False
BTC: 관련 뉴스를 찾을 수 없습니다.
--- 3) SerpAPI 401 | 로그에 키 노출: True
BTC: 관련 뉴스를 찾을 수 없습니다.
--- 4) SerpAPI 연결 타임아웃 | 로그에 키 노출: True
BTC: 관련 뉴스를 찾을 수 없습니다.
--- 5) 두 키 모두 없음 | 로그에 키 노출: False
BTC: 관련 뉴스를 찾을 수 없습니다.
--- 6) 1건만 깨짐(link 없음) | 로그에 키 노출: False
BTC: 관련 뉴스를 찾을 수 없습니다.
```

- [ ] **Step 4: 착수 기록**

- `LEARNING_LOG.md`에 날짜별 항목을 추가한다: 기준 커밋 `1fc7119`, `src/`·`tests/` 미커밋 변경 없음, `127 passed`, 스크립트 경로, Step 3 출력(URL 누락, 2~6번이 같은 문장, 3·4번 키 노출).
- `ROADMAP.md` §3의 R1 상태를 `예정`에서 `진행`으로 바꾸고, §4 R1.0 행의 예상 위치를 `LEARNING_LOG.md`, `baseline/search_news_compare.py`로 맞춘다.
  R1.0 체크박스는 스크립트와 출력 기록을 근거로 체크한다.
- `CURRENT.md`의 다음 행동을 “R1 실행 중 — [R1-PLAN.md](R1-PLAN.md) Task 1”로 바꾼다.

- [ ] **Step 5: 체크포인트 (커밋하지 않음)**

Run: `git status --short docs/agent-improvement src tests`
Expected: `docs/agent-improvement/`만 미추적(`??`)으로 보이고 `src`·`tests` 변경 없음.

---

### Task 1: 반환 계약 정의 (R1.1)

**Files:**
- Modify: `src/agent/schemas.py:1` (모듈 docstring), `src/agent/schemas.py:5-7` (import), 파일 끝에 추가
- Create: `tests/test_news_contract.py`

**Interfaces:**
- Consumes: 없음
- Produces (`src.agent.schemas`):
  - `MAX_NEWS_ARTICLES: int = 5`
  - `NewsSearchStatus = Literal["ok", "empty", "error", "unavailable"]`
  - `NewsProvider = Literal["cryptopanic", "serpapi"]`
  - `NewsErrorCode = Literal["timeout", "http_error", "invalid_response", "request_error"]`
  - `NewsArticle(title: str, url: str, source: str = "")`
  - `NewsProviderAttempt(provider: NewsProvider, status: NewsSearchStatus, error_code: NewsErrorCode | None = None)`
  - `NewsSearchResult(status: NewsSearchStatus, articles: list[NewsArticle] = [], attempts: list[NewsProviderAttempt] = [])`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_news_contract.py`:

```python
"""뉴스 검색 도구 반환 계약(R1) — 기사·시도·결과의 검증 규칙."""

import pytest
from pydantic import ValidationError

from src.agent.schemas import NewsArticle, NewsProviderAttempt, NewsSearchResult

ARTICLE = {"title": "BTC surges", "url": "https://news.example.com/a", "source": "CoinDesk"}


class TestNewsArticle:
    def test_keeps_url_string_as_given(self):
        # HttpUrl 이었다면 '/' 추가·퍼센트 인코딩·호스트 소문자화가 일어난다.
        raw = "https://News.Example.com/a b?q=한글"
        assert NewsArticle(title="t", url=f"  {raw}  ").url == raw

    @pytest.mark.parametrize("url", ["ftp://x.com/f", "javascript:alert(1)", "example.com/x", "https://", "http://[::1"])
    def test_rejects_non_http_url(self, url):
        with pytest.raises(ValidationError):
            NewsArticle(title="t", url=url)

    @pytest.mark.parametrize("field", ["title", "url"])
    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_rejects_missing_required_field(self, field, value):
        with pytest.raises(ValidationError):
            NewsArticle(**{**ARTICLE, field: value})

    def test_source_defaults_to_empty(self):
        assert NewsArticle(title="t", url="https://x.com").source == ""


class TestNewsProviderAttempt:
    def test_error_requires_error_code(self):
        with pytest.raises(ValidationError):
            NewsProviderAttempt(provider="serpapi", status="error")

    @pytest.mark.parametrize("status", ["ok", "empty", "unavailable"])
    def test_non_error_rejects_error_code(self, status):
        with pytest.raises(ValidationError):
            NewsProviderAttempt(provider="serpapi", status=status, error_code="timeout")

    def test_unknown_values_rejected(self):
        with pytest.raises(ValidationError):
            NewsProviderAttempt(provider="serpapi", status="error", error_code="boom")
        with pytest.raises(ValidationError):
            NewsProviderAttempt(provider="google", status="ok")


class TestNewsSearchResult:
    def test_ok_requires_articles(self):
        with pytest.raises(ValidationError):
            NewsSearchResult(status="ok", articles=[])

    @pytest.mark.parametrize("status", ["empty", "error", "unavailable"])
    def test_non_ok_rejects_articles(self, status):
        with pytest.raises(ValidationError):
            NewsSearchResult(status=status, articles=[ARTICLE])

    def test_caps_articles_at_five(self):
        with pytest.raises(ValidationError):
            NewsSearchResult(status="ok", articles=[ARTICLE] * 6)

    def test_json_keeps_url_and_attempt_order(self):
        result = NewsSearchResult(
            status="ok",
            articles=[ARTICLE],
            attempts=[
                {"provider": "cryptopanic", "status": "unavailable"},
                {"provider": "serpapi", "status": "ok"},
            ],
        )
        data = result.model_dump(mode="json")
        assert data["articles"][0]["url"] == ARTICLE["url"]
        assert [a["provider"] for a in data["attempts"]] == ["cryptopanic", "serpapi"]
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_news_contract.py -q -p no:cacheprovider`
Expected: 수집 오류 `ImportError: cannot import name 'NewsArticle' from 'src.agent.schemas'`

- [ ] **Step 3: 최소 구현**

`src/agent/schemas.py` 1행을 교체:

```python
"""Typed 스키마 — 에이전트 출력(LLM 강제)과 도구 반환(코드 검증)을 구조화한다."""
```

5~7행의 import를 교체:

```python
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
```

파일 끝(`IncidentAssessment` 뒤)에 추가:

```python


# ── 뉴스 검색 도구 반환 계약 (R1) ─────────────────────────────
# LLM 출력 스키마가 아니라 도구 결과를 코드가 검증하는 계약이다.
# 설계: docs/agent-improvement/ROADMAP.md §4

MAX_NEWS_ARTICLES = 5

NewsSearchStatus = Literal["ok", "empty", "error", "unavailable"]
NewsProvider = Literal["cryptopanic", "serpapi"]
NewsErrorCode = Literal["timeout", "http_error", "invalid_response", "request_error"]


class NewsArticle(BaseModel):
    """검색 공급자가 준 기사 1건. 링크한 페이지는 요청하지 않는다."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, description="기사 제목")
    url: str = Field(min_length=1, description="공급자가 준 기사 링크. 앞뒤 공백 외에는 원래 문자열 그대로")
    source: str = Field(default="", description="매체명. 모르면 빈 문자열")

    @field_validator("url")
    @classmethod
    def _require_http_url(cls, url: str) -> str:
        # HttpUrl 은 '/' 추가·퍼센트 인코딩·호스트 소문자화로 문자열을 바꾼다 → 형식만 검사하고 원문을 돌려준다.
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("http(s)://호스트 형식의 URL이 아님")
        return url


class NewsProviderAttempt(BaseModel):
    """공급자 1곳을 확인한 결과. 앞선 성공으로 확인하지 않은 공급자는 기록하지 않는다."""

    provider: NewsProvider
    status: NewsSearchStatus
    error_code: NewsErrorCode | None = None

    @model_validator(mode="after")
    def _error_code_only_on_error(self) -> NewsProviderAttempt:
        if (self.status == "error") != (self.error_code is not None):
            raise ValueError("error_code 는 status 가 error 일 때만 있어야 한다")
        return self


class NewsSearchResult(BaseModel):
    """search_news 도구의 반환값."""

    status: NewsSearchStatus
    articles: list[NewsArticle] = Field(default_factory=list, max_length=MAX_NEWS_ARTICLES)
    attempts: list[NewsProviderAttempt] = Field(default_factory=list)

    @model_validator(mode="after")
    def _articles_only_on_ok(self) -> NewsSearchResult:
        if (self.status == "ok") != bool(self.articles):
            raise ValueError("ok 면 기사가 1건 이상, 그 외 상태는 빈 목록이어야 한다")
        return self
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_news_contract.py -q -p no:cacheprovider`
Expected: `24 passed`

- [ ] **Step 5: 전체 회귀**

Run: `.venv/bin/python -m pytest tests -q -p no:cacheprovider`
Expected: `151 passed, 1 warning`

- [ ] **Step 6: 체크포인트 (커밋하지 않음)**

Run: `git status --short src tests`
Expected: `M src/agent/schemas.py`, `?? tests/test_news_contract.py`

---

### Task 2: 공급자 응답 해석과 요청 실패 분류 (R1.2 전반)

기존 `_search_cryptopanic`·`_search_serpapi`·`search_news`는 Task 3에서 교체하므로 이 단계에서는 그대로 둔다.

**Files:**
- Modify: `src/agent/tools/search_news.py:1-11` (import·상수), 기존 함수 앞에 새 함수 추가
- Modify: `tests/test_agent_tools.py:1-9` (import), `class TestQueryMarketWindow` 위에 fixture·도우미 추가, 파일 끝에 테스트 클래스 추가

**Interfaces:**
- Consumes: Task 1의 `MAX_NEWS_ARTICLES`, `NewsArticle`, `NewsErrorCode`, `NewsProvider`
- Produces (`src.agent.tools.search_news`):
  - `class _ProviderError(Exception)` — `.error_code: NewsErrorCode`, `.http_status: int | None`
  - `_get_json(url: str, params: dict) -> object` — 실패 시 `_ProviderError`
  - `_collect_articles(provider: NewsProvider, items: list, to_fields: Callable[[dict], dict]) -> list[NewsArticle]`
  - `_fetch_cryptopanic(coin_code: str) -> list[NewsArticle]`, `_fetch_serpapi(coin_code: str) -> list[NewsArticle]` — 키를 확인하지 않음, 실패 시 `_ProviderError`
  - 상수 `CRYPTOPANIC_URL`, `SERPAPI_URL`, `REQUEST_TIMEOUT_SECONDS`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_agent_tools.py` 1~9행(import 부분)을 교체:

```python
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import pytest
import requests

import src.agent.tools.search_news as sn
from src.agent.schemas import NewsArticle
from src.agent.tools.query_market import query_market_window
from src.agent.tools.search_news import (
    _ProviderError,
    _fetch_cryptopanic,
    _fetch_serpapi,
    _get_json,
    _search_cryptopanic,
    _search_serpapi,
    search_news,
)
```

`class TestQueryMarketWindow:` 바로 위에 추가:

```python
@pytest.fixture(autouse=True)
def _block_real_http(monkeypatch):
    """.env 의 실제 SerpAPI 키가 로드돼 있으므로, mock 을 빠뜨린 테스트가 진짜 요청을 보내지 않게 막는다."""
    monkeypatch.setattr(sn.requests, "get", MagicMock(side_effect=AssertionError("테스트에서 실제 HTTP 요청 금지")))


@pytest.fixture
def mock_get(monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(sn.requests, "get", fake)
    return fake


def _response(status: int = 200, payload: object = None, body: str | None = None) -> requests.Response:
    """실제 requests.Response — status_code·json() 이 진짜와 같게 동작한다."""
    resp = requests.Response()
    resp.status_code = status
    resp._content = (json.dumps(payload) if body is None else body).encode("utf-8")
    resp.encoding = "utf-8"
    return resp


SERP_ITEM = {
    "title": "Bitcoin ETF inflows hit record",
    "link": "https://news.example.com/a?id=1&lang=한글",
    "source": "CoinDesk",
}
SERP_OK = {
    "search_metadata": {"status": "Success"},
    "news_results": [SERP_ITEM, {"title": "비트코인 급등", "link": "https://news.example.kr/b", "source": "한경"}],
}
SERP_NO_RESULTS = {
    "search_metadata": {"status": "Success"},
    "error": "Google hasn't returned any results for this query.",
}
CRYPTO_OK = {
    "results": [
        {"title": "BTC surges", "url": "https://cryptopanic.com/news/1/btc-surges", "source": {"title": "CoinDesk"}},
    ]
}


def _serp_payload(items: list) -> dict:
    return {"search_metadata": {"status": "Success"}, "news_results": items}


```

파일 끝에 추가:

```python


class TestGetJson:
    def test_returns_json_body(self, mock_get):
        mock_get.return_value = _response(200, {"a": 1})
        assert _get_json("https://x.test", {}) == {"a": 1}

    @pytest.mark.parametrize("exc, code", [
        (requests.Timeout(), "timeout"),
        (requests.ConnectTimeout(), "timeout"),  # ConnectionError 이기도 함 — timeout 이 먼저
        (requests.ConnectionError(), "request_error"),
    ])
    def test_request_failures_are_classified(self, mock_get, exc, code):
        mock_get.side_effect = exc
        with pytest.raises(_ProviderError) as info:
            _get_json("https://x.test", {})
        assert info.value.error_code == code

    def test_non_2xx_is_http_error(self, mock_get):
        mock_get.return_value = _response(429, {"error": "Your account has run out of searches."})
        with pytest.raises(_ProviderError) as info:
            _get_json("https://x.test", {})
        assert (info.value.error_code, info.value.http_status) == ("http_error", 429)

    def test_broken_json_is_invalid_response(self, mock_get):
        # requests.JSONDecodeError 는 RequestException 이기도 함 — request_error 로 새면 안 된다
        mock_get.return_value = _response(200, body="<html>not json</html>")
        with pytest.raises(_ProviderError) as info:
            _get_json("https://x.test", {})
        assert info.value.error_code == "invalid_response"


class TestFetchCryptoPanic:
    def test_parses_articles(self, mock_get):
        mock_get.return_value = _response(200, CRYPTO_OK)
        assert _fetch_cryptopanic("BTC") == [
            NewsArticle(title="BTC surges", url="https://cryptopanic.com/news/1/btc-surges", source="CoinDesk"),
        ]

    def test_empty_results_list(self, mock_get):
        mock_get.return_value = _response(200, {"results": []})
        assert _fetch_cryptopanic("BTC") == []

    @pytest.mark.parametrize("payload", [{"status": "api_error"}, {"results": {"a": 1}}, ["not", "a", "dict"]])
    def test_malformed_body_is_invalid_response(self, mock_get, payload):
        mock_get.return_value = _response(200, payload)
        with pytest.raises(_ProviderError) as info:
            _fetch_cryptopanic("BTC")
        assert info.value.error_code == "invalid_response"

    def test_retired_v1_endpoint_is_http_error(self, mock_get):
        # 2026-10-02 실측: 폐기된 /api/free/v1/ 은 404 와 api_error 본문을 준다.
        mock_get.return_value = _response(404, {"status": "api_error", "info": "Unknown API endpoint."})
        with pytest.raises(_ProviderError) as info:
            _fetch_cryptopanic("BTC")
        assert (info.value.error_code, info.value.http_status) == ("http_error", 404)


class TestFetchSerpApi:
    def test_parses_articles_and_keeps_url_string(self, mock_get):
        mock_get.return_value = _response(200, SERP_OK)
        articles = _fetch_serpapi("BTC")
        assert [a.url for a in articles] == [SERP_ITEM["link"], "https://news.example.kr/b"]
        assert articles[0].source == "CoinDesk"

    def test_no_results_message_is_empty_not_error(self, mock_get):
        mock_get.return_value = _response(200, SERP_NO_RESULTS)
        assert _fetch_serpapi("BTC") == []

    @pytest.mark.parametrize("payload", [
        {"search_metadata": {"status": "Error"}, "error": "Search failed"},
        {"news_results": [SERP_ITEM]},  # search_metadata 없음
        {"search_metadata": {"status": "Success"}, "news_results": {"a": 1}},
        ["not", "a", "dict"],
    ])
    def test_unsuccessful_or_malformed_is_invalid_response(self, mock_get, payload):
        mock_get.return_value = _response(200, payload)
        with pytest.raises(_ProviderError) as info:
            _fetch_serpapi("BTC")
        assert info.value.error_code == "invalid_response"

    def test_drops_only_invalid_items(self, mock_get):
        items = [
            {"title": "no link"},
            {"title": "bad scheme", "link": "javascript:alert(1)"},
            {"title": "   ", "link": "https://news.example.com/blank-title"},
            "not a dict",
            SERP_ITEM,
        ]
        mock_get.return_value = _response(200, _serp_payload(items))
        assert [a.title for a in _fetch_serpapi("BTC")] == [SERP_ITEM["title"]]

    def test_all_items_invalid_is_invalid_response(self, mock_get):
        mock_get.return_value = _response(200, _serp_payload([{"title": "no link"}]))
        with pytest.raises(_ProviderError) as info:
            _fetch_serpapi("BTC")
        assert info.value.error_code == "invalid_response"

    def test_caps_at_five_valid_articles(self, mock_get):
        items = [{"title": "no link"}] + [{"title": f"t{i}", "link": f"https://news.example.com/{i}"} for i in range(7)]
        mock_get.return_value = _response(200, _serp_payload(items))
        assert [a.title for a in _fetch_serpapi("BTC")] == ["t0", "t1", "t2", "t3", "t4"]

    def test_non_string_source_becomes_empty(self, mock_get):
        mock_get.return_value = _response(200, _serp_payload([{**SERP_ITEM, "source": {"name": "CoinDesk"}}]))
        assert _fetch_serpapi("BTC")[0].source == ""
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_agent_tools.py -q -p no:cacheprovider`
Expected: 수집 오류 `ImportError: cannot import name '_ProviderError' from 'src.agent.tools.search_news'`

- [ ] **Step 3: 최소 구현**

`src/agent/tools/search_news.py` 1~11행(import·키 상수)을 교체:

```python
import os
from collections.abc import Callable

import requests
from langchain_core.tools import tool
from pydantic import ValidationError

from src.agent.schemas import MAX_NEWS_ARTICLES, NewsArticle, NewsErrorCode, NewsProvider
from src.config import setup_logging

logger = setup_logging("tool-search-news")

CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")

# 2026-10-02 확인: 이 v1 경로는 폐기되어 404 를 준다 (현재 경로는 /api/{plan}/v2/, 유료 플랜).
# 유료 키 없이 검증할 수 없어 R1 에서는 옮기지 않는다 — docs/agent-improvement/ROADMAP.md §4 알려진 문제.
CRYPTOPANIC_URL = "https://cryptopanic.com/api/free/v1/posts/"
SERPAPI_URL = "https://serpapi.com/search.json"
REQUEST_TIMEOUT_SECONDS = 10


class _ProviderError(Exception):
    """공급자 조회 실패. 외부 원문 대신 분류만 담는다."""

    def __init__(self, error_code: NewsErrorCode, http_status: int | None = None):
        super().__init__(error_code)
        self.error_code = error_code
        self.http_status = http_status


def _get_json(url: str, params: dict) -> object:
    """GET 후 JSON 본문을 반환한다. 실패는 분류만 담은 _ProviderError 로 바꾼다.

    requests 예외 메시지에는 쿼리 문자열의 API 키가 들어 있으므로 원래 예외를 전달·기록하지 않는다(from None).
    """
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.Timeout:  # ConnectTimeout 은 ConnectionError 이기도 해서 먼저 잡는다
        raise _ProviderError("timeout") from None
    except requests.RequestException:
        raise _ProviderError("request_error") from None
    if not 200 <= resp.status_code < 300:
        raise _ProviderError("http_error", http_status=resp.status_code)
    try:
        return resp.json()
    except ValueError:  # requests.JSONDecodeError 는 RequestException 이기도 해서 요청 예외와 따로 처리한다
        raise _ProviderError("invalid_response", http_status=resp.status_code) from None


def _text(value: object) -> str:
    """매체명처럼 없어도 되는 필드 — 문자열이 아니면 빈 문자열."""
    return value if isinstance(value, str) else ""


def _collect_articles(
    provider: NewsProvider,
    items: list,
    to_fields: Callable[[dict], dict],
) -> list[NewsArticle]:
    """항목별로 검증해 무효 항목만 뺀다. 항목이 있었는데 전부 무효면 invalid_response."""
    articles = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            articles.append(NewsArticle.model_validate(to_fields(item)))
        except ValidationError:
            continue
    dropped = len(items) - len(articles)
    if dropped:
        logger.warning("뉴스 항목 제외: provider=%s dropped=%d", provider, dropped)
    if items and not articles:
        raise _ProviderError("invalid_response")
    return articles[:MAX_NEWS_ARTICLES]


def _cryptopanic_fields(item: dict) -> dict:
    source = item.get("source")
    return {
        "title": item.get("title"),
        "url": item.get("url"),
        "source": _text(source.get("title")) if isinstance(source, dict) else "",
    }


def _serpapi_fields(item: dict) -> dict:
    return {"title": item.get("title"), "url": item.get("link"), "source": _text(item.get("source"))}


def _fetch_cryptopanic(coin_code: str) -> list[NewsArticle]:
    """CryptoPanic 뉴스. 빈 목록이면 정상 0건이고 실패는 _ProviderError 로 알린다."""
    payload = _get_json(CRYPTOPANIC_URL, {
        "auth_token": CRYPTOPANIC_API_KEY,
        "currencies": coin_code,
        "kind": "news",
        "regions": "en",
    })
    items = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise _ProviderError("invalid_response")
    return _collect_articles("cryptopanic", items, _cryptopanic_fields)


def _fetch_serpapi(coin_code: str) -> list[NewsArticle]:
    """SerpAPI Google News. 결과 없음도 HTTP 200 + error 메시지로 오므로 search_metadata.status 로 판정한다."""
    payload = _get_json(SERPAPI_URL, {
        "api_key": SERPAPI_API_KEY,
        "q": f"{coin_code} 코인 뉴스",
        "tbm": "nws",
        "num": MAX_NEWS_ARTICLES,
    })
    if not isinstance(payload, dict):
        raise _ProviderError("invalid_response")
    metadata = payload.get("search_metadata")
    if not isinstance(metadata, dict) or metadata.get("status") != "Success":
        raise _ProviderError("invalid_response")
    items = payload.get("news_results", [])
    if not isinstance(items, list):
        raise _ProviderError("invalid_response")
    return _collect_articles("serpapi", items, _serpapi_fields)
```

교체한 부분 아래의 기존 `_search_cryptopanic`, `_search_serpapi`, `search_news`는 그대로 둔다.

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_agent_tools.py -q -p no:cacheprovider`
Expected: `28 passed` (기존 6건 + 새 22건)

- [ ] **Step 5: 전체 회귀**

Run: `.venv/bin/python -m pytest tests -q -p no:cacheprovider`
Expected: `173 passed, 1 warning`

- [ ] **Step 6: 체크포인트 (커밋하지 않음)**

Run: `git status --short src tests`
Expected: `M src/agent/schemas.py`, `M src/agent/tools/search_news.py`, `M tests/test_agent_tools.py`, `?? tests/test_news_contract.py`

---

### Task 3: 공급자를 순서대로 확인하고 전체 상태 정하기 (R1.2 후반) — 사용자 작성 지점

**Files:**
- Modify: `src/agent/tools/search_news.py` (모듈 docstring 추가, import 교체, 기존 `_search_cryptopanic`·`_search_serpapi`·`search_news` 삭제 후 새 함수 추가)
- Modify: `tests/test_agent_tools.py` (import 교체, 기존 `class TestSearchNews` 삭제, 파일 끝에 새 테스트 추가)

**Interfaces:**
- Consumes: Task 1의 `NewsProviderAttempt`, `NewsSearchResult`, `NewsSearchStatus`; Task 2의 `_ProviderError`, `_fetch_cryptopanic`, `_fetch_serpapi`
- Produces (`src.agent.tools.search_news`):
  - `_run_provider(provider: NewsProvider, api_key: str, fetch: Callable[[str], list[NewsArticle]], coin_code: str) -> tuple[NewsProviderAttempt, list[NewsArticle]]`
  - `_decide_status(attempts: list[NewsProviderAttempt]) -> NewsSearchStatus` — **사용자 작성**
  - `search_news` (`@tool`): `search_news.invoke({"coin_code": str}) -> NewsSearchResult`
  - 삭제: `_search_cryptopanic`, `_search_serpapi` (문자열 반환 버전)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_agent_tools.py` 맨 위 import 부분(Task 2에서 바꾼 부분)을 교체:

```python
import json
import logging
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import pytest
import requests

import src.agent.tools.search_news as sn
from src.agent.schemas import NewsArticle, NewsProviderAttempt
from src.agent.tools.query_market import query_market_window
from src.agent.tools.search_news import (
    _ProviderError,
    _decide_status,
    _fetch_cryptopanic,
    _fetch_serpapi,
    _get_json,
    search_news,
)
```

기존 `class TestSearchNews:` 전체(기존 테스트 4개: `test_cryptopanic_success`, `test_cryptopanic_no_key`,
`test_search_news_no_results`, `test_search_news_with_results`)를 삭제한다. 문자열 반환을 전제한 테스트라서 아래 매트릭스로 대체한다.

파일 끝에 추가:

```python


ARTICLE = NewsArticle(title="BTC surges", url="https://news.example.com/a", source="CoinDesk")


def _attempts(*statuses: str) -> list[NewsProviderAttempt]:
    return [
        NewsProviderAttempt(provider=provider, status=status, error_code="timeout" if status == "error" else None)
        for provider, status in zip(("cryptopanic", "serpapi"), statuses)
    ]


class TestDecideStatus:
    @pytest.mark.parametrize("statuses, expected", [
        (("ok",), "ok"),
        (("error", "ok"), "ok"),
        (("empty", "error"), "error"),
        (("error", "unavailable"), "error"),
        (("empty", "unavailable"), "empty"),
        (("unavailable", "empty"), "empty"),
        (("unavailable", "unavailable"), "unavailable"),
    ])
    def test_priority(self, statuses, expected):
        assert _decide_status(_attempts(*statuses)) == expected


def _run_search(monkeypatch, crypto: str, serp: str):
    """두 공급자의 결과를 정해 두고 search_news 를 실행한다. outcome: ok / empty / error / unavailable."""
    fetches = {}
    for name, outcome in (("cryptopanic", crypto), ("serpapi", serp)):
        def fetch(coin_code, outcome=outcome):
            if outcome == "error":
                raise _ProviderError("timeout")
            return [ARTICLE] if outcome == "ok" else []
        fetches[name] = MagicMock(side_effect=fetch)
    monkeypatch.setattr(sn, "CRYPTOPANIC_API_KEY", "" if crypto == "unavailable" else "test-key")
    monkeypatch.setattr(sn, "SERPAPI_API_KEY", "" if serp == "unavailable" else "test-key")
    monkeypatch.setattr(sn, "_fetch_cryptopanic", fetches["cryptopanic"])
    monkeypatch.setattr(sn, "_fetch_serpapi", fetches["serpapi"])
    return search_news.invoke({"coin_code": "BTC"}), fetches


class TestSearchNews:
    @pytest.mark.parametrize("crypto, serp, status, attempts", [
        ("ok", "ok", "ok", ["cryptopanic:ok"]),
        ("error", "ok", "ok", ["cryptopanic:error", "serpapi:ok"]),
        ("unavailable", "ok", "ok", ["cryptopanic:unavailable", "serpapi:ok"]),
        ("empty", "ok", "ok", ["cryptopanic:empty", "serpapi:ok"]),
        ("empty", "empty", "empty", ["cryptopanic:empty", "serpapi:empty"]),
        ("unavailable", "unavailable", "unavailable", ["cryptopanic:unavailable", "serpapi:unavailable"]),
        ("error", "empty", "error", ["cryptopanic:error", "serpapi:empty"]),
        ("empty", "error", "error", ["cryptopanic:empty", "serpapi:error"]),
        ("error", "unavailable", "error", ["cryptopanic:error", "serpapi:unavailable"]),
        ("unavailable", "error", "error", ["cryptopanic:unavailable", "serpapi:error"]),
        ("error", "error", "error", ["cryptopanic:error", "serpapi:error"]),
        ("empty", "unavailable", "empty", ["cryptopanic:empty", "serpapi:unavailable"]),
        ("unavailable", "empty", "empty", ["cryptopanic:unavailable", "serpapi:empty"]),
    ])
    def test_status_matrix(self, monkeypatch, crypto, serp, status, attempts):
        result, _ = _run_search(monkeypatch, crypto, serp)
        assert result.status == status
        assert [f"{a.provider}:{a.status}" for a in result.attempts] == attempts
        assert result.articles == ([ARTICLE] if status == "ok" else [])

    def test_first_success_skips_second_provider(self, monkeypatch):
        _, fetches = _run_search(monkeypatch, "ok", "ok")
        fetches["serpapi"].assert_not_called()

    def test_missing_key_skips_request(self, monkeypatch):
        _, fetches = _run_search(monkeypatch, "unavailable", "ok")
        fetches["cryptopanic"].assert_not_called()

    def test_error_attempt_keeps_error_code(self, monkeypatch):
        result, _ = _run_search(monkeypatch, "error", "ok")
        assert result.attempts[0].error_code == "timeout"


class TestNoSecretLeak:
    SECRET = "SECRET-KEY-123"

    @pytest.mark.parametrize("exc", [requests.ConnectionError, requests.Timeout])
    def test_request_failure_does_not_leak_key(self, monkeypatch, mock_get, caplog, exc):
        # 실제 requests 예외처럼 메시지에 쿼리 문자열의 키를 넣는다.
        mock_get.side_effect = exc(f"Max retries exceeded with url: /search.json?api_key={self.SECRET}&q=BTC")
        monkeypatch.setattr(sn, "CRYPTOPANIC_API_KEY", "")
        monkeypatch.setattr(sn, "SERPAPI_API_KEY", self.SECRET)
        with caplog.at_level(logging.INFO):
            result = search_news.invoke({"coin_code": "BTC"})
        assert result.status == "error"
        assert "serpapi" in caplog.text  # 로그는 남긴다 — 키만 빠진다
        assert self.SECRET not in caplog.text
        assert self.SECRET not in result.model_dump_json()
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_agent_tools.py -q -p no:cacheprovider`
Expected: 수집 오류 `ImportError: cannot import name '_decide_status' from 'src.agent.tools.search_news'`

- [ ] **Step 3: 오케스트레이터 구현 (`_decide_status`는 TODO로 둠)**

`src/agent/tools/search_news.py` 맨 위에 모듈 docstring을 추가하고 schemas import를 교체:

```python
"""뉴스 검색 도구 — 공급자 응답을 검증된 NewsSearchResult 로 정규화한다."""

import os
from collections.abc import Callable

import requests
from langchain_core.tools import tool
from pydantic import ValidationError

from src.agent.schemas import (
    MAX_NEWS_ARTICLES,
    NewsArticle,
    NewsErrorCode,
    NewsProvider,
    NewsProviderAttempt,
    NewsSearchResult,
    NewsSearchStatus,
)
from src.config import setup_logging
```

기존 `def _search_cryptopanic(`부터 파일 끝까지(`_search_cryptopanic`, `_search_serpapi`, 문자열 반환 `search_news`)를 삭제하고 아래로 교체:

```python
def _run_provider(
    provider: NewsProvider,
    api_key: str,
    fetch: Callable[[str], list[NewsArticle]],
    coin_code: str,
) -> tuple[NewsProviderAttempt, list[NewsArticle]]:
    """공급자 1곳을 확인해 시도 기록과 기사를 돌려준다. 키가 없으면 요청하지 않는다."""
    if not api_key:
        return NewsProviderAttempt(provider=provider, status="unavailable"), []
    try:
        articles = fetch(coin_code)
    except _ProviderError as e:
        logger.warning(
            "뉴스 공급자 조회 실패: provider=%s error_code=%s http_status=%s",
            provider, e.error_code, e.http_status,
        )
        return NewsProviderAttempt(provider=provider, status="error", error_code=e.error_code), []
    return NewsProviderAttempt(provider=provider, status="ok" if articles else "empty"), articles


def _decide_status(attempts: list[NewsProviderAttempt]) -> NewsSearchStatus:
    """공급자별 시도 기록으로 전체 상태를 정한다. 우선순위: ok > error > empty > unavailable.

    error 가 empty 보다 앞서는 이유: 일부 검색을 끝내지 못했는데 '정상적으로 0건'이라고 말하지 않기 위해서.
    """
    # TODO(사용자): attempts 의 status 들을 보고 위 우선순위대로 하나를 돌려준다 (5~6줄).
    #   확인: .venv/bin/python -m pytest tests/test_agent_tools.py -k "DecideStatus or SearchNews or SecretLeak" -q -p no:cacheprovider
    raise NotImplementedError("_decide_status 는 사용자 작성 지점")


@tool
def search_news(coin_code: str) -> NewsSearchResult:
    """특정 코인에 대한 최신 뉴스를 검색합니다.

    CryptoPanic → SerpAPI 순서로 확인하고, 검증된 기사를 처음 얻은 공급자의 목록을 채택합니다.

    Args:
        coin_code: 코인 코드 (예: BTC, ETH)

    Returns:
        NewsSearchResult — status(ok/empty/error/unavailable), articles(title·url·source), attempts(공급자별 시도)
    """
    attempts: list[NewsProviderAttempt] = []
    articles: list[NewsArticle] = []
    # 키와 조회 함수를 호출 시점에 모듈 전역에서 읽는다 — 테스트의 patch 가 반영되게.
    for provider, api_key, fetch in (
        ("cryptopanic", CRYPTOPANIC_API_KEY, _fetch_cryptopanic),
        ("serpapi", SERPAPI_API_KEY, _fetch_serpapi),
    ):
        attempt, articles = _run_provider(provider, api_key, fetch, coin_code)
        attempts.append(attempt)
        if articles:
            break

    result = NewsSearchResult(status=_decide_status(attempts), articles=articles, attempts=attempts)
    logger.info(
        "뉴스 검색: coin=%s status=%s attempts=%s articles=%d",
        coin_code,
        result.status,
        ",".join(f"{a.provider}:{a.status}" for a in result.attempts),
        len(result.articles),
    )
    return result
```

- [ ] **Step 4: TODO 상태 확인**

Run: `.venv/bin/python -m pytest tests/test_agent_tools.py -q -p no:cacheprovider`
Expected: `TestDecideStatus`, `TestSearchNews`, `TestNoSecretLeak`만 `NotImplementedError`로 실패(25 failed).
`TestQueryMarketWindow`, `TestGetJson`, `TestFetchCryptoPanic`, `TestFetchSerpApi`는 통과(24 passed).

- [ ] **Step 5: 🧑‍💻 사용자 작성 — `_decide_status`**

사용자에게 다음을 전달하고 기다린다.

- 위치: `src/agent/tools/search_news.py`의 `_decide_status` TODO 2줄과 `raise`를 지우고 5~6줄로 구현
- 규칙: 시도 중 하나라도 `ok`면 `ok`, 아니면 `error`가 있으면 `error`, 아니면 `empty`가 있으면 `empty`, 전부 `unavailable`이면 `unavailable`
- 확인 명령: TODO 주석의 명령. 통과하면 다음 Step으로 간다.

막혔을 때 REPL 스니펫:

```bash
.venv/bin/python -c '
from src.agent.schemas import NewsProviderAttempt as A
attempts = [A(provider="cryptopanic", status="empty"), A(provider="serpapi", status="error", error_code="timeout")]
print({a.status for a in attempts})
'
```

막혔을 때 빈칸 뼈대:

```python
    statuses = {attempt.____ for attempt in attempts}
    for status in (____):  # 우선순위 순서대로
        if status in statuses:
            return ____
    return "unavailable"
```

<details>
<summary>참고 구현 — 사용자가 실행자에게 맡길 때만 사용</summary>

```python
    statuses = {attempt.status for attempt in attempts}
    for status in ("ok", "error", "empty"):
        if status in statuses:
            return status
    return "unavailable"
```

</details>

- [ ] **Step 6: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_agent_tools.py -q -p no:cacheprovider`
Expected: `49 passed`

- [ ] **Step 7: 전체 회귀**

Run: `.venv/bin/python -m pytest tests -q -p no:cacheprovider`
Expected: `194 passed, 1 warning`. 이 시점의 뉴스 노드는 아직 문자열을 기대하지만 노드 테스트가 `search_news`를 mock하므로 통과한다.

- [ ] **Step 8: 체크포인트 (커밋하지 않음)**

Run: `grep -n "_search_cryptopanic\|_search_serpapi" src tests -r`
Expected: 출력 없음

---

### Task 4: 뉴스 노드 연결과 프롬프트 (R1.3)

**Files:**
- Modify: `src/agent/news_agent.py` (전체 교체)
- Modify: `src/agent/prompts.py:21-27` (`NEWS_SYSTEM_PROMPT` 앞부분)
- Modify: `tests/test_multi_agent.py:3-10` (import), `class TestNewsAnalystNode` 전체 교체(`class TestReportWriterNode` 직전까지)
- Modify: `tests/test_agent_tools.py` (import 1줄 추가·1줄 교체, 파일 끝에 경로 테스트 추가)

**Interfaces:**
- Consumes: Task 3의 `search_news.invoke(...) -> NewsSearchResult`; Task 1의 `NewsArticle`, `NewsSearchResult`; 기존 `NewsEvidence`
- Produces:
  - `news_analyst_node(state: dict) -> {"news_analysis": str}` — `NewsEvidence` JSON. `ok`일 때만 LLM 호출
  - `_neutral_evidence(headlines: list[str]) -> NewsEvidence`
  - 갱신된 `NEWS_SYSTEM_PROMPT`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_multi_agent.py` 3~10행(import 부분)을 교체:

```python
import json
import logging
from unittest.mock import patch, MagicMock

import pytest

from src.agent.market_agent import market_analyst_node
from src.agent.news_agent import news_analyst_node
from src.agent.prompts import NEWS_SYSTEM_PROMPT
from src.agent.report_agent import report_writer_node
from src.agent.graph import build_analysis_workflow, _format_indicator_details, SupervisorState
from src.agent.schemas import (
    IncidentAssessment,
    MarketEvidence,
    NewsArticle,
    NewsEvidence,
    NewsSearchResult,
)
```

`class TestNewsAnalystNode:` 전체(기존 `test_success`, `test_tool_failure`)를 아래로 교체:

```python
NEWS_ARTICLE = NewsArticle(
    title="BTC ETF 승인 임박 보도",
    url="https://news.example.com/etf?id=1&lang=한글",
    source="CoinDesk",
)
NEWS_OK = NewsSearchResult(
    status="ok",
    articles=[NEWS_ARTICLE],
    attempts=[
        {"provider": "cryptopanic", "status": "unavailable"},
        {"provider": "serpapi", "status": "ok"},
    ],
)


def _human_message(mock_llm) -> str:
    """structured LLM 에 전달된 HumanMessage 본문."""
    messages = mock_llm.with_structured_output.return_value.invoke.call_args.args[0]
    return messages[1].content


class TestNewsAnalystNode:
    @patch("src.agent.news_agent.ChatOpenAI")
    @patch("src.agent.news_agent.search_news")
    def test_success(self, mock_tool, mock_llm_cls):
        mock_tool.invoke.return_value = NEWS_OK
        mock_llm = _structured_llm_mock(MOCK_NEWS_OBJ)
        mock_llm_cls.return_value = mock_llm

        result = news_analyst_node(_base_state())
        _assert_schema_enforced(mock_llm, NewsEvidence)
        assert "news_analysis" in result
        evidence = NewsEvidence.model_validate_json(result["news_analysis"])
        assert evidence.sentiment == "BULLISH"

    @patch("src.agent.news_agent.ChatOpenAI")
    @patch("src.agent.news_agent.search_news")
    def test_llm_input_is_article_json_with_url(self, mock_tool, mock_llm_cls):
        mock_tool.invoke.return_value = NEWS_OK
        mock_llm = _structured_llm_mock(MOCK_NEWS_OBJ)
        mock_llm_cls.return_value = mock_llm

        news_analyst_node(_base_state())
        human = _human_message(mock_llm)
        news_json = human.split("뉴스 검색 결과:\n", 1)[1].split("\n\n앙상블 지표:", 1)[0]
        # 상태·시도 이력은 넣지 않고 기사 목록만, URL 은 원래 문자열 그대로
        assert json.loads(news_json) == {"articles": [NEWS_ARTICLE.model_dump()]}
        assert NEWS_ARTICLE.url in human  # ensure_ascii=False — 한글이 이스케이프되지 않음
        assert "zscore: 5.2" in human  # 앙상블 지표 입력은 기존과 같다

    @pytest.mark.parametrize("status, attempt, headlines", [
        ("error", {"provider": "serpapi", "status": "error", "error_code": "timeout"}, ["[ERROR] 뉴스 조회 실패"]),
        ("empty", {"provider": "serpapi", "status": "empty"}, []),
        ("unavailable", {"provider": "serpapi", "status": "unavailable"}, []),
    ])
    def test_no_articles_skips_llm(self, status, attempt, headlines):
        with patch("src.agent.news_agent.search_news") as mock_tool, \
             patch("src.agent.news_agent.ChatOpenAI") as mock_llm_cls:
            mock_tool.invoke.return_value = NewsSearchResult(status=status, attempts=[attempt])
            result = news_analyst_node(_base_state())

        mock_llm_cls.assert_not_called()
        evidence = NewsEvidence.model_validate_json(result["news_analysis"])
        assert evidence.headlines == headlines
        assert (evidence.sentiment, evidence.relevance_score, evidence.source_quality) == (
            "NEUTRAL", 0.0, "unknown",
        )

    @patch("src.agent.news_agent.search_news")
    def test_tool_failure(self, mock_tool):
        mock_tool.invoke.side_effect = Exception("API timeout url=/search.json?api_key=SECRET")

        result = news_analyst_node(_base_state())
        evidence = NewsEvidence.model_validate_json(result["news_analysis"])
        assert evidence.sentiment == "NEUTRAL"
        assert evidence.relevance_score == 0.0
        assert evidence.headlines == ["[ERROR] 뉴스 분석 실패"]
        assert "SECRET" not in result["news_analysis"]

    def test_llm_failure_hides_exception_text(self, caplog):
        with patch("src.agent.news_agent.search_news") as mock_tool, \
             patch("src.agent.news_agent.ChatOpenAI", side_effect=Exception("upstream said: sk-SECRET")):
            mock_tool.invoke.return_value = NEWS_OK
            with caplog.at_level(logging.INFO):
                result = news_analyst_node(_base_state())

        evidence = NewsEvidence.model_validate_json(result["news_analysis"])
        assert evidence.headlines == ["[ERROR] 뉴스 분석 실패"]
        assert "sk-SECRET" not in result["news_analysis"]
        assert "sk-SECRET" not in caplog.text

    def test_prompt_describes_json_input_without_no_news_rule(self):
        assert "articles" in NEWS_SYSTEM_PROMPT and "url" in NEWS_SYSTEM_PROMPT
        assert "뉴스가 없으면" not in NEWS_SYSTEM_PROMPT  # 기사 0건은 코드가 처리한다


```

`tests/test_agent_tools.py` import에서 `from src.agent.schemas import NewsArticle, NewsProviderAttempt` 한 줄을 아래 두 줄로 교체:

```python
from src.agent.news_agent import news_analyst_node
from src.agent.schemas import NewsArticle, NewsEvidence, NewsProviderAttempt
```

`tests/test_agent_tools.py` 파일 끝에 추가:

```python


class TestSearchNewsIntoNode:
    """공급자 응답 → 도구 → 뉴스 노드의 LLM 입력까지 (requests·LLM 만 mock)."""

    def test_provider_url_reaches_llm_input(self, monkeypatch, mock_get):
        mock_get.return_value = _response(200, SERP_OK)
        monkeypatch.setattr(sn, "CRYPTOPANIC_API_KEY", "")
        monkeypatch.setattr(sn, "SERPAPI_API_KEY", "test-key")
        llm = MagicMock()
        llm.with_structured_output.return_value.invoke.return_value = NewsEvidence(
            headlines=[SERP_ITEM["title"]], sentiment="BULLISH", relevance_score=0.6, source_quality="major_media",
        )
        monkeypatch.setattr("src.agent.news_agent.ChatOpenAI", MagicMock(return_value=llm))

        news_analyst_node({"anomaly": {"coin_code": "BTC"}, "indicator_details": "zscore: 5.2"})

        human = llm.with_structured_output.return_value.invoke.call_args.args[0][1].content
        # JSON 직렬화(ensure_ascii=False)로 URL 이 원래 문자열 그대로 들어간다
        assert f'"url":"{SERP_ITEM["link"]}"' in human
        assert '"url":"https://news.example.kr/b"' in human
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_multi_agent.py tests/test_agent_tools.py -q -p no:cacheprovider`
Expected: 8 failed — `test_llm_input_is_article_json_with_url`, `test_no_articles_skips_llm` 3건,
`test_tool_failure`, `test_llm_failure_hides_exception_text`, `test_prompt_describes_json_input_without_no_news_rule`,
`test_provider_url_reaches_llm_input`. `test_success`는 기존 노드에서도 통과한다.

- [ ] **Step 3: 뉴스 노드 구현**

`src/agent/news_agent.py` 전체를 교체:

```python
"""News analysis node — 뉴스 검색 + 연관성 분석."""

import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.agent.tools.search_news import search_news
from src.agent.prompts import NEWS_SYSTEM_PROMPT
from src.agent.schemas import NewsEvidence
from src.config import setup_logging

logger = setup_logging("news-agent")

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5.6-luna")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def _neutral_evidence(headlines: list[str]) -> NewsEvidence:
    """판단할 기사가 없을 때의 고정 결과 — 모델을 부르지 않고 코드가 정한다."""
    return NewsEvidence(
        headlines=headlines,
        sentiment="NEUTRAL",
        relevance_score=0.0,
        source_quality="unknown",
    )


def news_analyst_node(state: dict) -> dict:
    """뉴스 검색 → (기사가 있을 때만) LLM 분석 → NewsEvidence JSON 반환."""
    coin_code = state["anomaly"]["coin_code"]

    try:
        result = search_news.invoke({"coin_code": coin_code})

        if result.status != "ok":
            # 기사가 없으면 모델이 분석할 자료가 없고 결과가 규칙으로 정해진다.
            # error 는 다른 노드 fallback 과 같은 [ERROR] 표기로 '뉴스 없음'과 구분한다 (R3 에서 상태 필드로 교체).
            headlines = ["[ERROR] 뉴스 조회 실패"] if result.status == "error" else []
            logger.info("News node LLM 생략: %s (status=%s)", coin_code, result.status)
            return {"news_analysis": _neutral_evidence(headlines).model_dump_json(ensure_ascii=False)}

        llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=0,
        )
        # OpenAI Structured Outputs 로 스키마를 API 층에서 강제한다.
        # invoke() 가 NewsEvidence 인스턴스를 직접 반환한다 (.content 파싱 불필요).
        # 주의: LLM_MODEL 이 gpt-3*/gpt-4-*/gpt-4 면 langchain 이 warning 만 남기고
        #       function_calling 으로 조용히 강등한다 — 강제가 풀리므로 모델 교체 시 확인할 것.
        structured_llm = llm.with_structured_output(NewsEvidence, method="json_schema")
        evidence = structured_llm.invoke([
            SystemMessage(content=NEWS_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"코인: {coin_code}\n\n"
                f"뉴스 검색 결과:\n{result.model_dump_json(include={'articles'}, ensure_ascii=False)}\n\n"
                f"앙상블 지표:\n{state.get('indicator_details', 'N/A')}"
            )),
        ])
        logger.info("News node 분석 완료: %s (sentiment=%s)", coin_code, evidence.sentiment)
        return {"news_analysis": evidence.model_dump_json(ensure_ascii=False)}

    except Exception as e:
        # 예외 메시지에는 외부 응답 원문이 섞일 수 있어 클래스 이름만 남기고 결과에도 넣지 않는다.
        logger.error("News node 실패: %s", type(e).__name__)
        return {"news_analysis": _neutral_evidence(["[ERROR] 뉴스 분석 실패"]).model_dump_json(ensure_ascii=False)}
```

- [ ] **Step 4: 프롬프트 수정**

`src/agent/prompts.py` 21~27행을 교체(“값의 톤·구체성 기준” 이하 예시는 그대로 둔다):

```python
NEWS_SYSTEM_PROMPT = """너는 암호화폐 뉴스 분석 전문가다. 한국어와 영어 뉴스 모두 분석 가능.

뉴스 검색 결과는 JSON이다. articles의 각 항목은 검색 공급자가 준 기사 1건이며
title은 제목, url은 기사 링크, source는 매체명(모르면 빈 문자열)이다. 기사 본문과 발행 시각은 제공되지 않는다.

분석 순서:
1. 제공된 뉴스가 해당 코인의 이상 징후와 직접 관련이 있는지 판단
2. 뉴스의 시장 영향 방향 (상승 요인 / 하락 요인 / 무관) 평가
3. 뉴스 소스의 신뢰도 평가 (공식 발표 > 주요 언론 > 커뮤니티)
```

- [ ] **Step 5: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_multi_agent.py tests/test_agent_tools.py -q -p no:cacheprovider`
Expected: `68 passed`

- [ ] **Step 6: 전체 회귀**

Run: `.venv/bin/python -m pytest tests -q -p no:cacheprovider`
Expected: `201 passed, 1 warning`

- [ ] **Step 7: 체크포인트 (커밋하지 않음)**

Run: `git status --short src tests`
Expected: `M src/agent/news_agent.py`, `M src/agent/prompts.py`, `M src/agent/schemas.py`, `M src/agent/tools/search_news.py`,
`M tests/test_agent_tools.py`, `M tests/test_multi_agent.py`, `?? tests/test_news_contract.py`

---

### Task 5: 회귀·커버리지·전후 비교·기록 (R1.4)

**Files:**
- Modify: `docs/agent-improvement/ROADMAP.md`, `docs/agent-improvement/LEARNING_LOG.md`, `docs/agent-improvement/CURRENT.md`

**Interfaces:**
- Consumes: Task 0 비교 스크립트, Task 1~4 결과
- Produces: R1 완료 판단과 검증 근거

- [ ] **Step 1: 전체 회귀**

Run: `.venv/bin/python -m pytest tests -q -p no:cacheprovider`
Expected: `201 passed, 1 warning`

- [ ] **Step 2: 변경 대상 코드 커버리지 (설치 없음, 표준 라이브러리 `trace`)**

```bash
COVER_DIR="${TMPDIR:-/tmp}/r1-cover"; rm -rf "$COVER_DIR"
.venv/bin/python -m trace --count --missing --coverdir="$COVER_DIR" --module pytest \
  tests/test_agent_tools.py tests/test_multi_agent.py tests/test_news_contract.py -q -p no:cacheprovider
for f in src.agent.tools.search_news src.agent.news_agent; do
  c="$COVER_DIR/$f.cover"; miss=$(grep -c '^>>>>>>' "$c"); hit=$(grep -cE '^ *[0-9]+:' "$c")
  echo "$f: $(( 100 * hit / (hit + miss) ))% (미실행 ${miss}줄)"; grep -n '^>>>>>>' "$c"
done
```

Expected: `92 passed`, 두 파일 모두 80% 이상(임시 복사본 기준 100%, 미실행 0줄).
`trace`의 줄 단위 측정이므로 기록에 측정 방법을 함께 적는다. 사용자가 `pytest-cov` 보고서를 원하면 승인을 받은 뒤
`uv pip install --python .venv/bin/python pytest-cov`로 설치하고(`requirements.txt`에는 추가하지 않음)
`.venv/bin/python -m pytest tests --cov=src/agent --cov-report=term-missing -p no:cacheprovider`로 측정한다.

- [ ] **Step 3: 변경 후 비교 출력 기록**

Run: `.venv/bin/python docs/agent-improvement/baseline/search_news_compare.py`

Expected:

```text
--- 1) SerpAPI 기사 2건 | 로그에 키 노출: False
{"status":"ok","articles":[{"title":"Bitcoin ETF inflows hit record","url":"https://news.example.com/a?id=1&lang=한글","source":"CoinDesk"},{"title":"비트코인 급등","url":"https://news.example.kr/b","source":"한경"}],"attempts":[{"provider":"cryptopanic","status":"unavailable","error_code":null},{"provider":"serpapi","status":"ok","error_code":null}]}
--- 2) SerpAPI 정상 0건 | 로그에 키 노출: False
{"status":"empty","articles":[],"attempts":[{"provider":"cryptopanic","status":"unavailable","error_code":null},{"provider":"serpapi","status":"empty","error_code":null}]}
--- 3) SerpAPI 401 | 로그에 키 노출: False
{"status":"error","articles":[],"attempts":[{"provider":"cryptopanic","status":"unavailable","error_code":null},{"provider":"serpapi","status":"error","error_code":"http_error"}]}
--- 4) SerpAPI 연결 타임아웃 | 로그에 키 노출: False
{"status":"error","articles":[],"attempts":[{"provider":"cryptopanic","status":"unavailable","error_code":null},{"provider":"serpapi","status":"error","error_code":"timeout"}]}
--- 5) 두 키 모두 없음 | 로그에 키 노출: False
{"status":"unavailable","articles":[],"attempts":[{"provider":"cryptopanic","status":"unavailable","error_code":null},{"provider":"serpapi","status":"unavailable","error_code":null}]}
--- 6) 1건만 깨짐(link 없음) | 로그에 키 노출: False
{"status":"ok","articles":[{"title":"Bitcoin ETF inflows hit record","url":"https://news.example.com/a?id=1&lang=한글","source":"CoinDesk"}],"attempts":[{"provider":"cryptopanic","status":"unavailable","error_code":null},{"provider":"serpapi","status":"ok","error_code":null}]}
```

- [ ] **Step 4: 로그 인자 점검**

Run: `grep -n "logger\." src/agent/tools/search_news.py src/agent/news_agent.py`
Expected: 인자가 공급자·상태·오류 분류·HTTP 상태 코드·제외 건수·코인·감성·`type(e).__name__`뿐이다. 예외 객체·URL·`params`를 넘기는 호출이 없다.

- [ ] **Step 5: 완료 기록**

- `ROADMAP.md` §4 체크리스트를 검증 근거와 함께 체크한다. 각 항목 옆에 근거 테스트 이름을 적는다.
  모든 항목과 커버리지 기준이 충족됐을 때만 §3의 R1을 `완료`로 바꾸고, §9 이력에 “미커밋 작업 트리, 기준 `1fc7119`, 201 passed, 커버리지 측정 방법과 수치”를 남긴다.
  미충족 항목이 있으면 `진행`으로 두고 남은 항목을 적는다.
- `LEARNING_LOG.md`에 변경 파일, 단계별 테스트 결과, 커버리지 방법·수치, 비교 출력 요약(변경 전 2~6번이 같은 문장 → 변경 후 상태 구분·키 노출 없음)을 남긴다.
  `_decide_status`를 누가 작성했는지 “사용자 작성 / 실행자 작성”으로 구분한다.
  실제 LLM·SerpAPI 호출이 없었고 모델 판단 품질은 검증하지 않았음을 명시한다.
- `CURRENT.md`의 현재 위치와 다음 행동을 갱신한다. 다음 후보는 R2 착수 전 세부 설계(본문 확보 방식 검토)다.

- [ ] **Step 6: 전체 변경 검토**

실행 방식에 따라 전체 diff를 새 검토자에게 맡긴다. 검토 범위: `git diff -- src tests`와 `tests/test_news_contract.py`, Global Constraints 준수 여부.

- [ ] **Step 7: 커밋 — 사용자가 요청한 경우에만**

사용자가 커밋을 요청하면 아래 순서로 한다. 문서(`docs/agent-improvement/`)를 함께 커밋할지는 그때 사용자에게 확인한다.

```bash
git switch -c feat/r1-news-search-result
git add src/agent/schemas.py src/agent/tools/search_news.py src/agent/news_agent.py src/agent/prompts.py \
  tests/test_agent_tools.py tests/test_multi_agent.py tests/test_news_contract.py
git commit -m "$(cat <<'EOF'
feat: 뉴스 검색 결과에 URL·조회 상태 보존 (R1)

- search_news 가 NewsSearchResult(status·articles·attempts)를 반환
- 정상 0건·조회 오류·키 미설정을 구분하고 깨진 항목만 제외
- 실패 로그·결과에서 API 키와 예외 원문 제거
- 기사 0건이면 뉴스 노드가 LLM 없이 결과를 정함

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```
