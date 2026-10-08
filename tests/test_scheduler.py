"""scheduler 사이클 — 분석 상한 (MAX_ANALYSES_PER_CYCLE)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src import scheduler
from src.scheduler import pick_for_analysis


def _result(coin, score, firing):
    return SimpleNamespace(
        coin_code=coin, ensemble_score=score, firing_count=firing, is_anomaly=True,
        severity="medium", signals=[],
    )


def test_pick_ranks_by_score_then_firing_count():
    a, b, c, d = _result("A", 0.55, 2), _result("B", 1.0, 4), _result("C", 0.55, 3), _result("D", 0.8, 3)
    picked, rest = pick_for_analysis([a, b, c, d], 2)
    assert [r.coin_code for r in picked] == ["B", "D"]
    assert [r.coin_code for r in rest] == ["C", "A"]


def test_pick_limit_larger_than_list():
    picked, rest = pick_for_analysis([_result("A", 0.5, 2)], 3)
    assert len(picked) == 1 and rest == []


@patch.object(scheduler, "MAX_ANALYSES_PER_CYCLE", 2)
@patch("src.scheduler.send_kakao_alert")
@patch("src.scheduler.send_alert")
@patch("src.scheduler.analyze_anomaly")
@patch("src.scheduler.save_incident")
@patch("src.scheduler.save_snapshots")
@patch("src.scheduler.prefilter_coins", return_value=["A", "B", "C", "D", "E"])
@patch("src.scheduler.check_warm_up", return_value=True)
@patch("src.scheduler.psycopg2.connect")
def test_cycle_analyzes_only_top_n(connect, _warm, _pre, _snap, save_incident, analyze, send_alert, send_kakao):
    results = [_result(c, s, 2) for c, s in [("A", 0.5), ("B", 1.0), ("C", 0.55), ("D", 0.8), ("E", 0.5)]]
    save_incident.side_effect = [f"id-{n}" for n in range(5)]
    with patch.object(scheduler._scorer, "score_batch", return_value=results):
        scheduler.run_cycle()

    analyzed = [call.args[0].coin_code for call in analyze.call_args_list]
    assert analyzed == ["B", "D"]
    assert send_alert.call_count == 2 and send_kakao.call_count == 2
    # 나머지 3건은 저장만 하고 skipped 로 표시
    cursor = connect.return_value.cursor.return_value.__enter__.return_value
    skipped_updates = [c for c in cursor.execute.call_args_list if "status = 'skipped'" in c.args[0]]
    assert len(skipped_updates) == 3
    assert save_incident.call_count == 5
