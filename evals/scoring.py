"""E1 채점 — 그래프 1회 실행 결과를 축별로 맞음(True)·틀림(False)·채점 제외(None)로 판정한다.

축 (evals/README.md):
- routing:  실행된 노드가 사례의 expected_nodes 와 같은가 — 코드 회귀 확인용
- judgment: recommended_action 이 분석가 라벨과 같은가 — 주 점수
- rule:     recommended_action 이 프롬프트 규칙(발동 지표 개수)과 같은가 — 지시 준수 보조 지표
- news:     뉴스 relevance_score 를 임계값으로 자른 값이 라벨 news_relevant 와 같은가
"""

AXES = ("routing", "judgment", "rule", "news")

RELEVANCE_THRESHOLD = 0.5
ALL_INDICATORS = 4  # 스케줄러에 등록된 지표 수 (zscore·bollinger_bands·rsi·vwap)


def rule_action(firing: list[str]) -> str:
    """REPORT_SYSTEM_PROMPT 규칙이 정하는 답: 단일 지표=MONITOR, 복수=ALERT, 전 지표=ESCALATE."""
    if len(firing) >= ALL_INDICATORS:
        return "ESCALATE"
    return "ALERT" if len(firing) >= 2 else "MONITOR"


def score_run(label: dict, firing: list[str], run: dict) -> dict[str, bool | None]:
    """그래프 1회 실행을 4축으로 채점한다.

    label: 사례 파일의 label — expected_nodes(list), recommended_action(str), news_relevant(bool | None)
    firing: 발동 지표 목록 (state.anomaly.firing_indicators)
    run: run_eval.run_once() 결과 — nodes(list), action(str | None), relevance_score(float | None)
         action 은 리포트 노드가 실패하면 None, relevance_score 는 뉴스 노드가 안 돌았거나 실패하면 None
    반환: {"routing": ..., "judgment": ..., "rule": ..., "news": ...}
    """
    action = run["action"]  # None(리포트 실패)은 어떤 답과도 같지 않으므로 False — 사용자는 답을 못 받았다
    expected_relevant = label["news_relevant"]
    score = run["relevance_score"]
    if expected_relevant is None:
        news = None  # 기사가 없거나 조회 실패한 사례는 관련성을 물을 수 없다
    elif score is None:
        news = False  # 기사가 있는데 뉴스 판단이 나오지 않았다
    else:
        news = (score >= RELEVANCE_THRESHOLD) == expected_relevant
    return {
        "routing": set(run["nodes"]) == set(label["expected_nodes"]),  # 병렬 노드라 완료 순서는 매번 다르다
        "judgment": action == label["recommended_action"],
        "rule": action == rule_action(firing),
        "news": news,
    }
