import { useEffect, useRef } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import NumberFlow from '@number-flow/react'
import clsx from 'clsx'
import type { IncidentSummary } from '../api'
import { ACT_KO, ACTIONS, IND, INDICATORS, SEV_KO, SEVERITIES, isSkipped, pct, relTime } from '../format'
import { type Filters, filterKey, isFiltering, toggle } from '../filters'
import { Tip } from './Tip'

interface Props {
  all: IncidentSummary[]
  visible: IncidentSummary[]
  selectedId: string | undefined
  onSelect: (id: string) => void
  filters: Filters
  onFilters: (f: Filters) => void
  freshIds: Set<string>
  now: number
  live: boolean
  searchRef: React.RefObject<HTMLInputElement | null>
  skippedCount: number
  includeSkipped: boolean
  onIncludeSkipped: (v: boolean) => void
}

const EASE_OUT = [0.23, 1, 0.32, 1] as const

export function IncidentList(props: Props) {
  const { all, visible, selectedId, onSelect, filters, onFilters, freshIds, now, live, searchRef } = props
  const { skippedCount, includeSkipped, onIncludeSkipped } = props
  const listRef = useRef<HTMLUListElement>(null)

  // 키보드로 선택이 바뀌면 보이는 곳까지만 스크롤
  useEffect(() => {
    listRef.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [selectedId])

  const counts = (key: 'severity' | 'recommended_action', value: string) => all.filter((i) => i[key] === value).length

  return (
    <aside className="list">
      <div className="list-head">
        <div className="list-title">
          <h1>
            인시던트 <NumberFlow value={visible.length} className="tnum" />
            {isFiltering(filters) && <span className="muted"> / {all.length}</span>}
          </h1>
          <Tip content={live ? '5초마다 새로 불러오는 중' : 'API 연결 끊김 — 다시 시도 중'}>
            <span className={clsx('live', !live && 'off')}>
              <i />
              {live ? '실시간' : '연결 끊김'}
            </span>
          </Tip>
        </div>
        <label className="search">
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <path d="M11.5 10.5 15 14M7 12A5 5 0 1 0 7 2a5 5 0 0 0 0 10Z" fill="none" stroke="currentColor" strokeWidth="1.5" />
          </svg>
          <input
            ref={searchRef}
            value={filters.q}
            onChange={(e) => onFilters({ ...filters, q: e.target.value })}
            onKeyDown={(e) => e.key === 'Escape' && (e.currentTarget.blur(), onFilters({ ...filters, q: '' }))}
            placeholder="코인·원인 검색"
            aria-label="코인·원인 검색"
          />
          <kbd>/</kbd>
        </label>
        <div className="chips" role="group" aria-label="심각도 필터">
          {SEVERITIES.map((s) => (
            <button
              key={s}
              className={clsx('chip', `sev-${s}`)}
              aria-pressed={filters.severities.includes(s)}
              onClick={() => onFilters({ ...filters, severities: toggle(filters.severities, s) })}
            >
              <span className="dot" />
              {SEV_KO[s]} <b className="tnum">{counts('severity', s)}</b>
            </button>
          ))}
        </div>
        <div className="chips" role="group" aria-label="권장 조치 필터">
          {ACTIONS.map((a) => (
            <button
              key={a}
              className={clsx('chip', `act-${a}`)}
              aria-pressed={filters.actions.includes(a)}
              onClick={() => onFilters({ ...filters, actions: toggle(filters.actions, a) })}
            >
              {ACT_KO[a]} <b className="tnum">{counts('recommended_action', a)}</b>
            </button>
          ))}
          {skippedCount > 0 && (
            <Tip content="한 사이클에 점수 높은 몇 건만 LLM 분석하고, 나머지는 감지만 저장해">
              <button className="chip" aria-pressed={includeSkipped} onClick={() => onIncludeSkipped(!includeSkipped)}>
                분석 생략 <b className="tnum">{skippedCount}</b>
              </button>
            </Tip>
          )}
        </div>
        <div className="hint">
          <kbd>j</kbd>
          <kbd>k</kbd> 이동 · <kbd>⌘K</kbd> 바로 가기
        </div>
      </div>

      {visible.length === 0 ? (
        <div className="list-empty">
          {all.length === 0 ? (
            <>
              아직 인시던트가 없어.
              <code>uv run python scripts/seed_demo_incidents.py</code>
            </>
          ) : (
            <>
              조건에 맞는 인시던트가 없어.
              <button className="link" onClick={() => onFilters({ severities: [], actions: [], q: '' })}>
                필터 지우기
              </button>
            </>
          )}
        </div>
      ) : (
        // 필터가 바뀌면 key 가 바뀌어 새로 그린다 → 필터 조작엔 애니메이션 없음.
        // 같은 필터에서 새 인시던트가 들어올 때만 위에서 끼어들고, 나머지는 자리를 내준다.
        <ul key={filterKey(filters)} ref={listRef} className="items" role="listbox" aria-label="인시던트 목록">
          <AnimatePresence initial={false}>
            {visible.map((i) => (
              <motion.li
                key={i.incident_id}
                layout="position"
                // x/y 단축 속성 대신 transform 문자열 → 메인 스레드가 바빠도(폴링 직후) 끊기지 않음
                initial={freshIds.has(i.incident_id) ? { opacity: 0, transform: 'translateY(-8px)' } : false}
                animate={{ opacity: 1, transform: 'translateY(0px)' }}
                transition={{ duration: 0.22, ease: EASE_OUT }}
              >
                <button
                  className={clsx('item', `sev-${i.severity}`)}
                  role="option"
                  aria-selected={i.incident_id === selectedId}
                  onClick={() => onSelect(i.incident_id)}
                >
                  <span className="stripe" />
                  <span className="item-main">
                    <span className="item-top">
                      <strong>{i.coin_code}</strong>
                      <span className="sev-text">{SEV_KO[i.severity]}</span>
                      {freshIds.has(i.incident_id) && <span className="new">NEW</span>}
                    </span>
                    <span className="item-sub">
                      {i.recommended_action ? (
                        <>
                          <span className={clsx('act-text', `act-${i.recommended_action}`)}>{ACT_KO[i.recommended_action]}</span>
                          {i.confidence !== null && <> · 신뢰도 {pct(i.confidence)}</>}
                        </>
                      ) : isSkipped(i) ? (
                        <span>분석 생략</span>
                      ) : (
                        <span className="pending">
                          <i className="pulse" />
                          분석 중
                        </span>
                      )}
                    </span>
                    <span className="inds" aria-label="발화 지표">
                      {INDICATORS.map((k) => (
                        <span key={k} className="ind" data-on={i.firing_indicators.includes(k) || undefined} title={IND[k].ko}>
                          {IND[k].short}
                        </span>
                      ))}
                    </span>
                  </span>
                  <span className="item-right">
                    <b className="tnum">{i.ensemble_score?.toFixed(2) ?? '–'}</b>
                    <span>{relTime(i.detected_at, now)}</span>
                  </span>
                </button>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </aside>
  )
}
