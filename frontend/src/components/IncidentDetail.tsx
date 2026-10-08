import { Suspense, lazy, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Tabs } from '@base-ui/react/tabs'
import { motion } from 'motion/react'
import NumberFlow, { type Format } from '@number-flow/react'
import clsx from 'clsx'
import { api, type IncidentDetail as Detail, type IncidentSummary } from '../api'
import { ACT_KO, IND, INDICATORS, SENT_KO, SEV_KO, SRC_KO, confWord, isSkipped, kst, relTime, splitAlt } from '../format'
import { TABS, type TabKey } from '../tabs'
import { Tip } from './Tip'


const EASE_OUT = [0.23, 1, 0.32, 1] as const

// recharts 가 번들의 절반이라 차트는 따로 불러온다
const PriceChart = lazy(() => import('./PriceChart'))

interface Props {
  summary: IncidentSummary
  now: number
  tab: TabKey
  onTab: (t: TabKey) => void
}

export function IncidentDetail({ summary, now, tab, onTab }: Props) {
  const id = summary.incident_id
  const { data, isError } = useQuery({
    queryKey: ['incident', id, summary.has_report],
    queryFn: () => api.incident(id),
  })

  // 분석 대기였다가 완료된 인시던트만 결과를 드러내는 애니메이션을 준다.
  // j/k 로 넘길 때마다 움직이면 시끄러우니까.
  const [sawPending, setSawPending] = useState<ReadonlySet<string>>(() => new Set())
  if (!summary.has_report && !sawPending.has(id)) setSawPending(new Set(sawPending).add(id))
  const reveal = summary.has_report && sawPending.has(id)


  const d: Partial<Detail> & IncidentSummary = { ...summary, ...data }
  const firing = d.firing_indicators.length

  return (
    <article className={clsx('detail', `sev-${d.severity}`)}>
      <header className="d-head">
        <h2>{d.coin_code}</h2>
        <span className="pill">{SEV_KO[d.severity]}</span>
        {d.recommended_action && <span className={clsx('pill', 'act', `act-${d.recommended_action}`)}>{ACT_KO[d.recommended_action]}</span>}
        {d.source === 'demo' && (
          <Tip content="E1 평가셋 사례를 넣은 데모 데이터. 노드 출력은 실제 실행 결과">
            <span className="pill ghost">데모</span>
          </Tip>
        )}
      </header>
      <div className="d-meta">
        {kst(d.detected_at)} KST · {relTime(d.detected_at, now)} · <span className="mono">{id.slice(0, 8)}</span>
      </div>

      <div className="meters">
        {/* key={id}: 선택이 바뀌면 새로 그려서 즉시 교체, 같은 인시던트 값이 바뀔 때만 숫자·막대가 움직인다 */}
        <Meter key={`score-${id}`} label="앙상블 점수" hint="지표 4개 가중 합산. 0.5 이상이면 이상으로 판정" value={d.ensemble_score}
          format={{ minimumFractionDigits: 2, maximumFractionDigits: 2 }} fill="var(--sev)" />
        <Meter key={`conf-${id}`} label="AI 신뢰도" hint="Report 노드가 스스로 매긴 판단 확신도 (0~1)" value={d.confidence}
          format={{ style: 'percent' }} suffix={d.confidence !== null ? confWord(d.confidence) : undefined} fill="var(--accent)" />
        <div className="meter">
          <Tip content="임계값을 넘어 이상 신호를 낸 지표 수">
            <span className="m-label">발화 지표</span>
          </Tip>
          <div className="m-value">
            <NumberFlow key={id} value={firing} />
            <small>/ 4</small>
          </div>
          <div className="segs">
            {INDICATORS.map((k) => (
              <i key={k} data-on={d.firing_indicators.includes(k) || undefined} />
            ))}
          </div>
          <p>{d.firing_indicators.map((k) => IND[k].ko).join(' · ') || '없음'}</p>
        </div>
      </div>

      <Suspense fallback={<div className="chart chart-empty">차트 불러오는 중…</div>}>
        <PriceChart id={id} severity={d.severity} detectedAt={d.detected_at} now={now} />
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
            <Pending skipped={isSkipped(summary)} />
          ) : d.report ? (
            <motion.div
              key={id}
              initial={reveal ? { opacity: 0, filter: 'blur(4px)' } : false}
              animate={{ opacity: 1, filter: 'blur(0px)' }}
              transition={{ duration: 0.28, ease: EASE_OUT }}
            >
              <h3>원인 추정</h3>
              <p className="root">{d.report.root_cause}</p>
              <h3>요약</h3>
              <p>{d.report.summary}</p>
              <h3>근거 <span className="muted">{d.report.supporting_evidence.length}</span></h3>
              <ol>{d.report.supporting_evidence.map((e, n) => <li key={n}>{e}</li>)}</ol>
              {d.report.alternative_hypotheses.length > 0 && (
                <>
                  <h3>다른 가능성은?</h3>
                  <ul className="alts">
                    {d.report.alternative_hypotheses.map((a, n) => {
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
            </motion.div>
          ) : (
            <Loading error={isError} />
          )}
        </Tabs.Panel>

        <Tabs.Panel value="market" className="panel">
          {d.market ? (
            <>
              <h3>판단 <span className="muted">신뢰도 {Math.round(d.market.confidence * 100)}%</span></h3>
              <p className="root">{d.market.claim}</p>
              <h3>근거</h3>
              <ol>{d.market.evidence.map((e, n) => <li key={n}>{e}</li>)}</ol>
              {!!d.market.missing_data?.length && (
                <>
                  <h3>부족한 데이터</h3>
                  <ul className="missing">{d.market.missing_data.map((m, n) => <li key={n}>{m}</li>)}</ul>
                </>
              )}
            </>
          ) : summary.has_report ? <Loading error={isError} /> : <Pending skipped={isSkipped(summary)} />}
        </Tabs.Panel>

        <Tabs.Panel value="news" className="panel">
          {d.news && !d.news.headlines.some((h) => h.startsWith('[ERROR]')) && (
            <div className="tags">
              <span className="tag">감성 {SENT_KO[d.news.sentiment]}</span>
              <span className="tag">관련성 {Math.round(d.news.relevance_score * 100)}%</span>
              <span className="tag">{SRC_KO[d.news.source_quality]}</span>
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

function Meter(props: {
  label: string
  hint: string
  value: number | null
  format: Format
  suffix?: string
  fill: string
}) {
  const { label, hint, value, format, suffix, fill } = props
  return (
    <div className="meter">
      <Tip content={hint}>
        <span className="m-label">{label}</span>
      </Tip>
      <div className="m-value">
        {value === null ? '–' : <NumberFlow value={value} format={format} />}
        {suffix && <small>{suffix}</small>}
      </div>
      <div className="track">
        <i style={{ transform: `scaleX(${value ?? 0})`, background: fill }} />
      </div>
      <p>{hint}</p>
    </div>
  )
}

// 뉴스 노드 출력(NewsEvidence)만 보여준다 — 노드는 제목 글자만 내놓고 링크·매체는 저장하지 않는다
function NewsList({ d }: { d: Partial<Detail> & IncidentSummary }) {
  if (!d.news) return d.has_report ? <p className="muted">이 인시던트는 뉴스 분석을 거치지 않았어.</p> : <Pending skipped={isSkipped(d)} />
  const headlines = d.news.headlines
  const failed = headlines.some((h) => h.startsWith('[ERROR]'))
  if (failed) return <p className="news-error">뉴스 검색이 실패해서 중립으로 처리됐어.</p>
  if (!headlines.length) return <p className="muted">관련 뉴스를 찾지 못했어.</p>
  return (
    <ul className="news">
      {headlines.map((h, n) => (
        <li key={n}>{h}</li>
      ))}
    </ul>
  )
}

function Pending({ skipped }: { skipped: boolean }) {
  if (skipped)
    return (
      <div className="pending-box">
        이 사이클의 분석 상한에 들어가지 못해 감지만 저장됐어. 점수가 더 높은 인시던트가 먼저 분석돼.
      </div>
    )
  return (
    <div className="pending-box">
      <i className="pulse" />
      LLM 분석이 진행 중이야. 끝나면 여기 자동으로 채워져.
    </div>
  )
}

function Loading({ error }: { error: boolean }) {
  return <p className="muted">{error ? '상세를 불러오지 못했어.' : '불러오는 중…'}</p>
}
