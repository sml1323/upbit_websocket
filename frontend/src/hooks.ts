import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import type { IncidentSummary } from './api'
import { ACT_KO, SEV_KO, isSkipped } from './format'

/** 상대 시간("3분 전")을 갱신하기 위한 현재 시각 */
export function useNow(intervalMs = 30_000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(t)
  }, [intervalMs])
  return now
}

/** 선택한 인시던트를 URL(?id=)에 둬서 새로고침·공유해도 유지 */
export function useSelectedId(): [string | null, (id: string) => void] {
  const [id, setId] = useState(() => new URLSearchParams(location.search).get('id'))
  const select = useCallback((next: string) => {
    setId(next)
    const url = new URL(location.href)
    url.searchParams.set('id', next)
    history.replaceState(null, '', url)
  }, [])
  return [id, select]
}

/**
 * 폴링 결과를 직전 결과와 비교해 토스트를 띄운다.
 * - 처음 본 인시던트: "이상 감지"
 * - 분석 대기 → 완료로 바뀐 인시던트: "분석 완료"
 * 첫 로드는 비교 대상이 없으니 조용히 넘어간다.
 */
export function useIncidentAlerts(incidents: IncidentSummary[] | undefined, onOpen: (id: string) => void) {
  const seen = useRef<Map<string, IncidentSummary> | null>(null)
  const [freshIds, setFreshIds] = useState<Set<string>>(() => new Set())

  useEffect(() => {
    if (!incidents) return
    const prev = seen.current
    seen.current = new Map(incidents.map((i) => [i.incident_id, i]))
    if (!prev) return

    const arrived: string[] = []
    for (const inc of incidents) {
      const before = prev.get(inc.incident_id)
      const open = { label: '보기', onClick: () => onOpen(inc.incident_id) }
      // 상한에 밀린 건은 사이클마다 수십 건이라 알리지 않는다
      if (isSkipped(inc)) continue
      if (!before) {
        arrived.push(inc.incident_id)
        toast(`${inc.coin_code} 이상 감지 · ${SEV_KO[inc.severity]}`, {
          description: inc.has_report ? inc.root_cause : 'LLM 분석 진행 중',
          action: open,
        })
      } else if (!before.has_report && inc.has_report && inc.recommended_action) {
        toast(`${inc.coin_code} 분석 완료 · ${ACT_KO[inc.recommended_action]}`, {
          description: inc.root_cause,
          action: open,
        })
      }
    }
    if (arrived.length) setFreshIds((s) => new Set([...s, ...arrived]))
  }, [incidents, onOpen])

  return freshIds
}

const isTyping = (el: EventTarget | null) =>
  el instanceof HTMLElement && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable)

export function useHotkeys(map: Record<string, (e: KeyboardEvent) => void>) {
  const ref = useRef(map)
  useEffect(() => {
    ref.current = map
  })
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const combo = (e.metaKey || e.ctrlKey ? 'mod+' : '') + e.key.toLowerCase()
      const handler = ref.current[combo]
      if (!handler) return
      // ⌘K 는 입력 중에도 열리고, 나머지 단축키는 입력 중엔 무시
      if (!combo.startsWith('mod+') && (isTyping(e.target) || e.altKey)) return
      e.preventDefault()
      handler(e)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
}
