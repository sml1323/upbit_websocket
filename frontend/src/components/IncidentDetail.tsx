import { Suspense, lazy, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Tabs } from '@base-ui/react/tabs'
import NumberFlow from '@number-flow/react'
import clsx from 'clsx'
import { api, type IncidentDetail as Detail, type IncidentSummary } from '../api'
import { ACT_KO, IND, INDICATORS, SENT_KO, SEV_KO, SRC_KO, confWord, isSkipped, kst, relTime, splitAlt } from '../format'
import { TABS, type TabKey } from '../tabs'
import { Tip } from './Tip'

// recharts 가 번들의 절반이라 차트는 따로 불러온다
const PriceChart = lazy(() => import('./PriceChart'))

const THRESHOLD = 0.5

interface Props {
  summary: IncidentSummary
  now: number
  tab: TabKey
  onTab: (t: TabKey) => void
}

/**
 * 상세는 "판정서" 순서로 읽힌다 (DESIGN.md):
 * 메타 한 줄 → 결론 헤드라인(root_cause) → 요약 → 근거 레일 5노드 → 차트 → 탭(심층)
 */
export function IncidentDetail({ summary, now, tab, onTab }: Props) {
  const id = summary.incident_id
  const { data, isError } = useQuery({
    queryKey: ['incident', id, summary.has_report],
    queryFn: () => api.incident(id),
  })

  // Evidence Chain: 분석 대기였다가 완료된 인시던트만 레일이 이어지는 연출을 한 번 한다.
  // j/k 로 넘길 때마다 움직이면 시끄러우니까 — 선택 전환은 fade(Incident Cut)뿐.
  const [sawPending, setSawPending] = useState<ReadonlySet<string>>(() => new Set())
  if (!summary.has_report && !sawPending.has(id)) setSawPending(new Set(sawPending).add(id))
  const reveal = summary.has_report && sawPending.has(id)

  const d: Partial<Detail> & IncidentSummary = { ...summary, ...data }
  const firing = d.firing_indicators.length
  const report = d.report ?? null
  const news = d.news && !d.news.headlines.some((h) => h.startsWith('[ERROR]')) ? d.news : null
  const skipped = isSkipped(summary)

  return (
    // key={id}: 선택이 바뀌면 DOM 을 새로 그려 fade 한 번(Incident Cut). 숫자 보간·슬라이드 없음
    <article key={id} className={clsx('detail', `sev-${d.severity}`)} data-cut>
      <header className="meta">
        <span className="coin">{d.coin_code}</span>
        <span className="sev-text">{SEV_KO[d.severity]}</span>
        <span className="sep">·</span>
        <span>{kst(d.detected_at)} KST</span>
        <span className="sep">·</span>
        <span>{relTime(d.detected_at, now)}</span>
        <span className="sep">·</span>
        <span className="mono">{id.slice(0, 8)}</span>
        {d.source === 'demo' && (
          <Tip content="E1 평가셋 사례를 넣은 데모 데이터. 노드 출력은 실제 실행 결과">
            <span className="badge ghost">데모</span>
          </Tip>
        )}
      </header>

      {summary.has_report && report ? (
        <>
          <h2 className="headline">{report.root_cause}</h2>
          <p className="summary">{report.summary}</p>
        </>
      ) : summary.has_report ? (
        <h2 className="headline pending">{isError ? '상세를 불러오지 못했어.' : '불러오는 중…'}</h2>
      ) : (
        <h2 className="headline pending">{skipped ? '감지만 저장됨 — 분석 생략' : '분석 대기 중'}</h2>
      )}

      {/* 근거 레일: LangGraph 노드 순서. 탐지 → 지표 → 뉴스 → 신뢰도 → 조치 */}
      <div className="rail" data-chain={reveal || undefined}>
        <div className="node">
          <Tip content={`지표 4개 가중 합산. ${THRESHOLD} 이상이면 이상으로 판정`}>
            <span className="label">앙상블 점수</span>
          </Tip>
          <span className="v num">
            {d.ensemble_score === null ? '–' : <NumberFlow value={d.ensemble_score} format={{ minimumFractionDigits: 2, maximumFractionDigits: 2 }} />}
            <small>/ 임계 {THRESHOLD.toFixed(2)}</small>
          </span>
          <span className="d">지표 4개 가중 합산</span>
        </div>

        <div className="node">
          <Tip content="임계값을 넘어 이상 신호를 낸 지표 수">
            <span className="label">발화 지표</span>
          </Tip>
          <span className="v num">
            {firing}
            <small>/ 4</small>
            <span className="segs" aria-hidden="true">
              {INDICATORS.map((k) => (
                <i key={k} data-on={d.firing_indicators.includes(k) || undefined} />
              ))}
            </span>
          </span>
          <span className="d">
            {d.firing_indicators.length
              ? d.firing_indicators
                  .map((k) => {
                    const ind = d.indicators?.find((i) => i.name === k)
                    return ind?.value != null ? `${IND[k].short} ${IND[k].fmt(ind.value)}` : IND[k].ko
                  })
                  .join(' · ')
              : '없음'}
          </span>
        </div>

        <div className="node">
          <Tip content="News 노드가 모은 헤드라인의 감성과 출처 품질">
            <span className="label">뉴스</span>
          </Tip>
          {news ? (
            <>
              <span className="v">
                {SENT_KO[news.sentiment]}
                <small>{SRC_KO[news.source_quality]}</small>
              </span>
              <span className="d">
                관련도 <b className="num">{news.relevance_score.toFixed(1)}</b> · 헤드라인 {news.headlines.length}건
              </span>
            </>
          ) : (
            <>
              <span className="v muted">–</span>
              <span className="d">{d.news ? '뉴스 검색 실패 · 중립 처리' : summary.has_report ? '뉴스 분석 안 함' : '대기'}</span>
            </>
          )}
        </div>

        <div className="node">
          <Tip content="Report 노드가 스스로 매긴 판단 확신도 (0~1). 정확도 확률이 아니다">
            <span className="label">AI 신뢰도</span>
          </Tip>
          {d.confidence !== null ? (
            <>
              <span className="v num">
                <NumberFlow value={d.confidence} format={{ style: 'percent' }} />
                <small>{confWord(d.confidence)}</small>
              </span>
              <span className="conf-track" aria-hidden="true">
                <i style={{ transform: `scaleX(${d.confidence})` }} />
              </span>
              <span className="d" style={{ marginTop: 4 }}>
                모델 자체 평가 · 정확도 확률 아님
              </span>
            </>
          ) : (
            <>
              <span className="v muted">–</span>
              <span className="d">대기</span>
            </>
          )}
        </div>

        <div className="node">
          <Tip content="에이전트의 권고. 실행 버튼이 아니다">
            <span className="label">권장 조치</span>
          </Tip>
          {d.recommended_action ? (
            <>
              <span className="v">
                <span className={clsx('badge', `act-${d.recommended_action}`)}>
                  {ACT_KO[d.recommended_action]} {d.recommended_action}
                </span>
              </span>
              <span className="d">
                근거 {report?.supporting_evidence.length ?? '–'}건
                {!!report?.alternative_hypotheses.length && <> · 대안 {report.alternative_hypotheses.length}건</>}
              </span>
            </>
          ) : (
            <>
              <span className="v muted">–</span>
              <span className="d">{skipped ? '분석 생략' : '대기'}</span>
            </>
          )}
        </div>
      </div>

      <Suspense fallback={<div className="chart chart-empty">차트 불러오는 중…</div>}>
        <PriceChart id={id} detectedAt={d.detected_at} now={now} />
      </Suspense>

      <Tabs.Root value={tab} onValueChange={(v) => onTab(v as TabKey)} className="tabs">
        <Tabs.List className="tab-list">
          {TABS.map(([k, label], n) => (
            <Tabs.Tab key={k} value={k} className="tab">
              {label}
              <kbd>{n + 1}</kbd>
            </Tabs.Tab>
          ))}
          <Tabs.Indicator className="tab-indicator" />
        </Tabs.List>

        <Tabs.Panel value="report" className="panel">
          {!summary.has_report ? (
            <Pending skipped={skipped} />
          ) : report ? (
            <>
              <h3>
                근거 <span className="muted">{report.supporting_evidence.length}</span>
              </h3>
              <ol>
                {report.supporting_evidence.map((e, n) => (
                  <li key={n}>{e}</li>
                ))}
              </ol>
              {report.alternative_hypotheses.length > 0 && (
                <>
                  <h3>다른 가능성은?</h3>
                  <ul className="alts">
                    {report.alternative_hypotheses.map((a, n) => {
                      const [h, why] = splitAlt(a)
                      return (
                        <li key={n}>
                          <b>{h}</b>
                          {why && <span>{why}</span>}
                        </li>
                      )
                    })}
                  </ul>
                </>
              )}
            </>
          ) : (
            <Loading error={isError} />
          )}
        </Tabs.Panel>

        <Tabs.Panel value="market" className="panel">
          {d.market ? (
            <>
              <h3>
                판단 <span className="muted">신뢰도 {Math.round(d.market.confidence * 100)}%</span>
              </h3>
              <p className="root">{d.market.claim}</p>
              <h3>근거</h3>
              <ol>
                {d.market.evidence.map((e, n) => (
                  <li key={n}>{e}</li>
                ))}
              </ol>
              {!!d.market.missing_data?.length && (
                <>
                  <h3>부족한 데이터</h3>
                  <ul className="missing">
                    {d.market.missing_data.map((m, n) => (
                      <li key={n}>{m}</li>
                    ))}
                  </ul>
                </>
              )}
            </>
          ) : summary.has_report ? (
            <Loading error={isError} />
          ) : (
            <Pending skipped={skipped} />
          )}
        </Tabs.Panel>

        <Tabs.Panel value="news" className="panel">
          {news && (
            <div className="tags">
              <span className="tag">감성 {SENT_KO[news.sentiment]}</span>
              <span className="tag">관련성 {Math.round(news.relevance_score * 100)}%</span>
              <span className="tag">{SRC_KO[news.source_quality]}</span>
            </div>
          )}
          <NewsList d={d} />
        </Tabs.Panel>

        <Tabs.Panel value="indicators" className="panel">
          <table className="itable">
            <thead>
              <tr>
                <th>지표</th>
                <th className="num">값</th>
                <th>상태</th>
                <th>읽는 법</th>
              </tr>
            </thead>
            <tbody>
              {INDICATORS.map((k) => {
                const ind = d.indicators?.find((i) => i.name === k)
                return (
                  <tr key={k}>
                    <td>{IND[k].ko}</td>
                    <td className="num tnum">{ind?.value != null ? IND[k].fmt(ind.value) : '–'}</td>
                    <td className={ind?.firing ? 'on' : 'off'}>{!ind ? '데이터 없음' : ind.firing ? '이상' : '정상'}</td>
                    <td className="muted">{IND[k].hint}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Tabs.Panel>
      </Tabs.Root>
    </article>
  )
}

// 뉴스 노드 출력(NewsEvidence)만 보여준다 — 노드는 제목 글자만 내놓고 링크·매체는 저장하지 않는다
function NewsList({ d }: { d: Partial<Detail> & IncidentSummary }) {
  if (!d.news) return d.has_report ? <p className="muted">이 인시던트는 뉴스 분석을 거치지 않았어.</p> : <Pending skipped={isSkipped(d)} />
  const headlines = d.news.headlines
  if (headlines.some((h) => h.startsWith('[ERROR]'))) return <p className="news-error">뉴스 검색이 실패해서 중립으로 처리됐어.</p>
  // "관련 뉴스 없음" 이 아니다 — 검색이 끝났다는 뜻이 아니라 자료가 없다는 뜻
  if (!headlines.length) return <p className="muted">뉴스 자료 없음.</p>
  return (
    <ul className="news">
      {headlines.map((h, n) => (
        <li key={n}>{h}</li>
      ))}
    </ul>
  )
}

function Pending({ skipped }: { skipped: boolean }) {
  return (
    <div className="pending-box">
      {skipped
        ? '이 사이클의 분석 상한에 들어가지 못해 감지만 저장됐어. 점수가 더 높은 인시던트가 먼저 분석돼.'
        : 'LLM 분석이 진행 중이야. 끝나면 여기 자동으로 채워져.'}
    </div>
  )
}

function Loading({ error }: { error: boolean }) {
  return <p className="muted">{error ? '상세를 불러오지 못했어.' : '불러오는 중…'}</p>
}
