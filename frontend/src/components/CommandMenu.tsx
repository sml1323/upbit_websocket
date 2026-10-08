import { Command } from 'cmdk'
import clsx from 'clsx'
import type { IncidentSummary } from '../api'
import { ACT_KO, ACTIONS, SEV_KO, SEVERITIES, relTime } from '../format'
import { type Filters, EMPTY_FILTERS, isFiltering, toggle } from '../filters'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  incidents: IncidentSummary[]
  filters: Filters
  onFilters: (f: Filters) => void
  onSelect: (id: string) => void
  now: number
}

// 하루에 수십 번 여닫는 팔레트라 열고 닫는 애니메이션은 일부러 없다.
export function CommandMenu({ open, onOpenChange, incidents, filters, onFilters, onSelect, now }: Props) {
  const run = (fn: () => void) => () => {
    fn()
    onOpenChange(false)
  }

  return (
    <Command.Dialog open={open} onOpenChange={onOpenChange} label="바로 가기" className="cmdk" overlayClassName="cmdk-overlay">
      <Command.Input placeholder="코인, 원인, 필터 검색…" />
      <Command.List>
        <Command.Empty>결과 없음</Command.Empty>
        <Command.Group heading="인시던트">
          {incidents.map((i) => (
            <Command.Item
              key={i.incident_id}
              value={`${i.coin_code} ${i.incident_id}`}
              keywords={[i.root_cause ?? '', SEV_KO[i.severity], i.recommended_action ? ACT_KO[i.recommended_action] : '분석 중']}
              onSelect={run(() => onSelect(i.incident_id))}
              className={clsx(`sev-${i.severity}`)}
            >
              <span className="dot" />
              <strong>{i.coin_code}</strong>
              <span className="cmdk-sub">{i.root_cause ?? '분석 중'}</span>
              <span className="cmdk-meta">{relTime(i.detected_at, now)}</span>
            </Command.Item>
          ))}
        </Command.Group>
        <Command.Group heading="필터">
          {SEVERITIES.map((s) => (
            <Command.Item key={s} value={`심각도 ${SEV_KO[s]}`} onSelect={run(() => onFilters({ ...filters, severities: toggle(filters.severities, s) }))} className={`sev-${s}`}>
              <span className="dot" />
              심각도 {SEV_KO[s]} {filters.severities.includes(s) ? '끄기' : '만 보기'}
            </Command.Item>
          ))}
          {ACTIONS.map((a) => (
            <Command.Item key={a} value={`권장 조치 ${ACT_KO[a]} ${a}`} onSelect={run(() => onFilters({ ...filters, actions: toggle(filters.actions, a) }))}>
              권장 조치 {ACT_KO[a]} {filters.actions.includes(a) ? '끄기' : '만 보기'}
            </Command.Item>
          ))}
          {isFiltering(filters) && (
            <Command.Item value="필터 초기화 reset" onSelect={run(() => onFilters(EMPTY_FILTERS))}>
              필터 모두 지우기
            </Command.Item>
          )}
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  )
}
