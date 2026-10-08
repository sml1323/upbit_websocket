// /api 응답 타입 — src/api/web.py 와 짝. 노드 출력 스키마는 src/agent/schemas.py.

export type Severity = 'low' | 'medium' | 'high' | 'critical'
export type Action = 'MONITOR' | 'ALERT' | 'ESCALATE'
export type IndicatorName = 'zscore' | 'bollinger_bands' | 'rsi' | 'vwap'

export interface IncidentSummary {
  incident_id: string
  coin_code: string
  severity: Severity
  detected_at: string
  source: string | null
  status: string | null
  ensemble_score: number | null
  firing_indicators: IndicatorName[]
  confidence: number | null
  recommended_action: Action | null
  root_cause: string | null
  has_report: boolean
}

export interface MarketEvidence {
  claim: string
  evidence: string[]
  confidence: number
  missing_data?: string[]
}

export interface NewsEvidence {
  headlines: string[]
  sentiment: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
  relevance_score: number
  source_quality: 'official' | 'major_media' | 'community' | 'unknown'
}

export interface IncidentAssessment {
  root_cause: string
  confidence: number
  supporting_evidence: string[]
  alternative_hypotheses: string[]
  recommended_action: Action
  summary: string
}

export interface Indicator {
  name: IndicatorName
  value: number | null
  firing: boolean
  detail: Record<string, number | string>
}

export interface IncidentDetail extends IncidentSummary {
  indicators: Indicator[]
  market: MarketEvidence | null
  news: NewsEvidence | null
  report: IncidentAssessment | null
}

export interface Candle {
  t: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  trades: number
  vwap: number | null
  bb_mid: number | null
  bb_upper: number | null
  bb_lower: number | null
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  incidents: (includeSkipped: boolean) =>
    get<{ incidents: IncidentSummary[]; skipped_count: number }>(`/incidents?limit=100&include_skipped=${includeSkipped}`),
  incident: (id: string) => get<IncidentDetail>(`/incidents/${encodeURIComponent(id)}`),
  candles: (id: string) =>
    get<{ detected_at: string; candles: Candle[] }>(`/incidents/${encodeURIComponent(id)}/candles?before=90&after=30`),
}
