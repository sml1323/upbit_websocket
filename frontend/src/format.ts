import type { Action, IndicatorName, NewsEvidence, Severity } from './api'

export const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low']
export const ACTIONS: Action[] = ['ESCALATE', 'ALERT', 'MONITOR']
export const INDICATORS: IndicatorName[] = ['zscore', 'bollinger_bands', 'rsi', 'vwap']

export const SEV_KO: Record<Severity, string> = { critical: '심각', high: '높음', medium: '보통', low: '낮음' }
export const ACT_KO: Record<Action, string> = { ESCALATE: '즉시 대응', ALERT: '알림', MONITOR: '관찰' }
export const SENT_KO: Record<NewsEvidence['sentiment'], string> = { BULLISH: '긍정', BEARISH: '부정', NEUTRAL: '중립' }
export const SRC_KO: Record<NewsEvidence['source_quality'], string> = {
  official: '공식 발표',
  major_media: '주요 언론',
  community: '커뮤니티',
  unknown: '출처 불명',
}

export const IND: Record<IndicatorName, { ko: string; short: string; fmt: (v: number) => string; hint: string }> = {
  zscore: { ko: 'Z-Score', short: 'Z', fmt: (v) => `${v.toFixed(2)}σ`, hint: '평균에서 표준편차 몇 배 벗어났나 (가격·거래량 중 큰 쪽)' },
  bollinger_bands: { ko: '볼린저 %B', short: 'B', fmt: (v) => v.toFixed(2), hint: '밴드 안 위치. 1 초과면 상단 밖, 0 미만이면 하단 밖' },
  rsi: { ko: 'RSI', short: 'R', fmt: (v) => v.toFixed(1), hint: '70 이상 과매수, 30 이하 과매도' },
  vwap: { ko: 'VWAP 괴리', short: 'V', fmt: (v) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%`, hint: '거래량 가중 평균가 대비 현재가 차이' },
}

/** 사이클 분석 상한(scheduler MAX_ANALYSES_PER_CYCLE)에 밀려 감지만 저장된 건 */
export const isSkipped = (i: { status: string | null; has_report: boolean }) => !i.has_report && i.status === 'skipped'

export const pct = (v: number) => `${Math.round(v * 100)}%`
export const confWord = (c: number) => (c >= 0.8 ? '높음' : c >= 0.5 ? '보통' : '낮음')

export function relTime(iso: string, now: number): string {
  const m = Math.round((now - new Date(iso).getTime()) / 60000)
  if (m < 1) return '방금'
  if (m < 60) return `${m}분 전`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}시간 전`
  return `${Math.floor(h / 24)}일 전`
}

const kstFmt = new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul',
  month: 'numeric',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})
function parts(iso: string) {
  const p: Record<string, string> = {}
  for (const x of kstFmt.formatToParts(new Date(iso))) p[x.type] = x.value
  return p
}
export const kst = (iso: string) => {
  const p = parts(iso)
  return `${p.month}월 ${p.day}일 ${p.hour}:${p.minute}`
}
export const kstTime = (iso: string) => {
  const p = parts(iso)
  return `${p.hour}:${p.minute}`
}

/** "가설 — 왜 아닌지" 를 둘로 */
export function splitAlt(text: string): [string, string] {
  const i = text.indexOf(' — ')
  return i > 0 ? [text.slice(0, i), text.slice(i + 3)] : [text, '']
}

export const priceFmt = (v: number) =>
  v >= 1000 ? v.toLocaleString('ko-KR', { maximumFractionDigits: 0 }) : v.toLocaleString('ko-KR', { maximumFractionDigits: 4 })
