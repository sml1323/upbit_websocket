import { useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from './api'
import { CommandMenu } from './components/CommandMenu'
import { IncidentDetail } from './components/IncidentDetail'
import { IncidentList } from './components/IncidentList'
import { EMPTY_FILTERS, type Filters, applyFilters } from './filters'
import { useHotkeys, useIncidentAlerts, useNow, useSelectedId } from './hooks'
import { TABS, type TabKey } from './tabs'

const POLL_MS = 5_000

export default function App() {
  const now = useNow()
  const [includeSkipped, setIncludeSkipped] = useState(false)
  const list = useQuery({
    queryKey: ['incidents', includeSkipped],
    queryFn: () => api.incidents(includeSkipped),
    refetchInterval: POLL_MS,
  })
  const [selectedId, select] = useSelectedId()
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [tab, setTab] = useState<TabKey>('report')
  const [cmdOpen, setCmdOpen] = useState(false)
  const searchRef = useRef<HTMLInputElement>(null)

  const all = useMemo(() => list.data?.incidents ?? [], [list.data])
  const visible = useMemo(() => applyFilters(all, filters), [all, filters])
  const freshIds = useIncidentAlerts(list.data?.incidents, select)

  // 선택이 없거나 필터에 가려지면 보이는 첫 항목을 보여준다
  const current = visible.find((i) => i.incident_id === selectedId) ?? visible[0]

  const move = (step: number) => {
    if (!visible.length) return
    const at = current ? visible.indexOf(current) : -1
    const next = visible[Math.min(Math.max(at + step, 0), visible.length - 1)]
    select(next.incident_id)
  }

  useHotkeys({
    j: () => move(1),
    k: () => move(-1),
    arrowdown: () => move(1),
    arrowup: () => move(-1),
    '/': () => searchRef.current?.focus(),
    'mod+k': () => setCmdOpen((o) => !o),
    ...Object.fromEntries(TABS.map(([key], n) => [String(n + 1), () => setTab(key)])),
  })

  return (
    <div className="shell">
      <IncidentList
        all={all}
        visible={visible}
        selectedId={current?.incident_id}
        onSelect={select}
        filters={filters}
        onFilters={setFilters}
        freshIds={freshIds}
        now={now}
        live={!list.isError}
        skippedCount={list.data?.skipped_count ?? 0}
        includeSkipped={includeSkipped}
        onIncludeSkipped={setIncludeSkipped}
        searchRef={searchRef}
      />
      <main className="main">
        {list.isPending ? (
          <p className="placeholder">불러오는 중…</p>
        ) : list.isError && !all.length ? (
          <p className="placeholder">
            API에 연결하지 못했어. <code>uvicorn src.api.main:app</code> 이 떠 있는지 확인해 줘.
          </p>
        ) : current ? (
          <IncidentDetail summary={current} now={now} tab={tab} onTab={setTab} />
        ) : (
          <p className="placeholder">왼쪽에서 인시던트를 골라줘.</p>
        )}
      </main>
      <CommandMenu
        open={cmdOpen}
        onOpenChange={setCmdOpen}
        incidents={all}
        filters={filters}
        onFilters={setFilters}
        onSelect={select}
        now={now}
      />
    </div>
  )
}
