# upbit_websocket

## 실행·테스트
- 의존성은 uv로 관리한다(`pyproject.toml` + `uv.lock`). 실행은 `uv run …`, 추가는 `uv add`(테스트 도구는 `uv add --dev`), 환경 맞추기는 `uv sync`. `.venv`에 pip로 직접 설치하지 않는다.
- 테스트는 `uv run pytest -q -p no:cacheprovider`(`pyproject.toml`의 `testpaths`로 `tests/`만 수집). `pytest .`이나 `scratch/` 경로를 직접 주지 않는다 — `scratch/`의 test 파일은 import만으로 실제 OpenAI를 호출한다.
- Docker는 `requirements.txt`로 설치한다. 의존성을 바꾸면 `uv export --no-dev --no-hashes --no-emit-project -o requirements.txt`로 다시 만든다.
- `src/config.py`가 import 때 `.env`를 읽어 실제 API 키가 로드된다. 테스트는 키 상수와 `requests.get`을 반드시 patch한다.

## 코드 주의
- requests 예외 메시지에는 쿼리 문자열의 API 키(SerpAPI `api_key`, CryptoPanic `auth_token`)가 들어 있다. 로그·결과에는 오류 분류만 남긴다(`search_news.py`의 `_ProviderError`).
- CryptoPanic v1 엔드포인트는 폐기(404)됐고 키도 비어 있어, 실제 뉴스 공급자는 SerpAPI 하나다.

## 작업 재개
- Agent 개선 트랙은 `docs/agent-improvement/CURRENT.md`부터 읽는다(진행 방식·다음 행동).

## Design System
Always read DESIGN.md before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.
