import type { Action, IncidentSummary, Severity } from './api'

export interface Filters {
  severities: Severity[]
  actions: Action[]
  q: string
}

export const EMPTY_FILTERS: Filters = { severities: [], actions: [], q: '' }

export const isFiltering = (f: Filters) => f.severities.length > 0 || f.actions.length > 0 || f.q.trim() !== ''

export function applyFilters(list: IncidentSummary[], f: Filters): IncidentSummary[] {
  const q = f.q.trim().toLowerCase()
  return list.filter(
    (i) =>
      (f.severities.length === 0 || f.severities.includes(i.severity)) &&
      (f.actions.length === 0 || (i.recommended_action !== null && f.actions.includes(i.recommended_action))) &&
      (q === '' || i.coin_code.toLowerCase().includes(q) || (i.root_cause ?? '').toLowerCase().includes(q)),
  )
}

export function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

/** 필터가 바뀌면 목록을 새로 그리기 위한 키 (필터 변경엔 레이아웃 애니메이션을 안 쓴다) */
export const filterKey = (f: Filters) => `${f.severities.join()}|${f.actions.join()}|${f.q}`
