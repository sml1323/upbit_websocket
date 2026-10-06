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
