import { useQuery } from '@tanstack/react-query'
import {
  Area,
  Bar,
  BarChart,
  ComposedChart,
  Line,
  Rectangle,
  type RectangleProps,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api, type Candle } from '../api'
import { kstTime, priceFmt } from '../format'

/** 감지 시각 앞뒤로 색을 입히는 창(분). 이 화면은 시세가 아니라 "그 순간"을 보는 화면이라 나머지는 흑백 */
const WINDOW_MIN = 3

// 색은 전부 CSS 변수 — 라이트/다크를 따라가고, 심각도 색(--sev)은 부모 .detail 에서 내려온다
const C = {
  close: 'var(--text-2)',
  vwap: 'var(--text-3)',
  band: 'var(--band-fill)',
  volume: 'var(--surface-3)',
  cursor: 'var(--text-4)',
  sev: 'var(--sev)',
  axis: 'var(--text-4)',
}

type Point = Candle & { ts: number; band: [number, number] | null; closeWin: number | null }

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
  const p = active && payload?.[0]?.payload
  if (!p) return null
  return (
    <div className="chart-tip">
      <div className="muted">{kstTime(p.t)} KST</div>
      <div>
        종가 <b className="tnum">{priceFmt(p.close)}</b>
      </div>
      {p.vwap !== null && (
        <div>
          VWAP <b className="tnum">{priceFmt(p.vwap)}</b>
        </div>
      )}
      <div>
        거래량 <b className="tnum">{p.volume.toLocaleString('ko-KR', { maximumFractionDigits: 0 })}</b>
        <span className="muted"> · {p.trades}건</span>
      </div>
    </div>
  )
}

export default function PriceChart({ id, detectedAt, now }: { id: string; detectedAt: string; now: number }) {
  // 최근 감지면 감지 이후 캔들이 계속 쌓이니 30초마다 다시 불러온다
  const recent = now - new Date(detectedAt).getTime() < 60 * 60_000
  const { data, isPending, isError } = useQuery({
    queryKey: ['candles', id],
    queryFn: () => api.candles(id),
    refetchInterval: recent ? 30_000 : false,
  })

  if (isPending) return <div className="chart chart-empty">차트 불러오는 중…</div>
  if (isError) return <div className="chart chart-empty">차트를 불러오지 못했어.</div>
  if (data.candles.length < 2) return <div className="chart chart-empty">이 시간대 1분봉 데이터가 없어.</div>

  // 감지 시각을 해당 분의 시작으로 맞춘다 (캔들 버킷과 같은 단위)
  const detectedTs = Math.floor(new Date(data.detected_at).getTime() / 60_000) * 60_000
  const winStart = detectedTs - WINDOW_MIN * 60_000
  const winEnd = detectedTs + WINDOW_MIN * 60_000

  const points: Point[] = data.candles.map((c) => {
    const ts = new Date(c.t).getTime()
    return {
      ...c,
      ts,
      band: c.bb_lower !== null && c.bb_upper !== null ? [c.bb_lower, c.bb_upper] : null,
      // 감지 창 안의 종가만 따로 — 이 구간만 심각도 색 선으로 덧그린다
      closeWin: ts >= winStart && ts <= winEnd ? c.close : null,
    }
  })
  // 방금 감지된 건은 감지 시각이 마지막 캔들보다 뒤일 수 있다 → 감지 선이 보이게 축을 넓힌다
  const xAxis = {
    dataKey: 'ts',
    type: 'number' as const,
    scale: 'time' as const,
    domain: [points[0].ts, Math.max(points[points.length - 1].ts, detectedTs)] as [number, number],
  }
  // 감지 시점이 오른쪽 끝(방금 감지)이면 라벨을 선 왼쪽에 붙여 잘리지 않게
  const nearEnd = xAxis.domain[1] - detectedTs < 10 * 60_000
  const tick = { fill: C.axis, fontSize: 10, fontFamily: 'var(--font-mono)' }

  return (
    <figure className="chart">
      <figcaption>
        <span>감지 전후 가격 · 1분봉</span>
        <span className="legend">
          <span>
            <i className="lg-close" />
            종가
          </span>
          <span>
            <i className="lg-vwap" />
            VWAP
          </span>
          <span>
            <i className="lg-band" />
            볼린저 밴드
          </span>
          <span>
            <i className="lg-detect" />
            감지 ±{WINDOW_MIN}분
          </span>
        </span>
      </figcaption>
      <ResponsiveContainer width="100%" height={164}>
        <ComposedChart data={points} syncId={id} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <XAxis {...xAxis} hide />
          <YAxis domain={['auto', 'auto']} width={60} orientation="right" tickFormatter={priceFmt} tick={tick} axisLine={false} tickLine={false} />
          {/* 차트를 바꿀 때마다 그려지는 애니메이션은 끔 — 인시던트를 자주 넘겨 보니까 */}
          <ReferenceArea x1={winStart} x2={winEnd} fill={C.sev} fillOpacity={0.07} stroke="none" />
          <Area dataKey="band" stroke="none" fill={C.band} fillOpacity={1} isAnimationActive={false} connectNulls />
          <Line dataKey="vwap" stroke={C.vwap} strokeDasharray="4 4" dot={false} strokeWidth={1.5} isAnimationActive={false} />
          <Line dataKey="close" stroke={C.close} dot={false} strokeWidth={1.5} isAnimationActive={false} />
          <Line dataKey="closeWin" stroke={C.sev} dot={false} strokeWidth={2} isAnimationActive={false} />
          <ReferenceLine
            x={detectedTs}
            stroke={C.sev}
            strokeWidth={1}
            label={{ value: `감지 ${kstTime(data.detected_at)}`, fill: C.sev, fontSize: 10, fontFamily: 'var(--font-mono)', position: nearEnd ? 'insideTopRight' : 'insideTopLeft' }}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: C.cursor, strokeDasharray: '2 2' }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
      <ResponsiveContainer width="100%" height={56}>
        <BarChart data={points} syncId={id} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <XAxis {...xAxis} tickFormatter={(v: number) => kstTime(new Date(v).toISOString())} tick={tick} axisLine={false} tickLine={false} minTickGap={48} />
          <YAxis width={60} orientation="right" scale="sqrt" tick={false} axisLine={false} tickLine={false} />
          <ReferenceArea x1={winStart} x2={winEnd} fill={C.sev} fillOpacity={0.07} stroke="none" />
          <Bar
            dataKey="volume"
            isAnimationActive={false}
            shape={(props: RectangleProps & { payload?: Point }) => <Rectangle {...props} fill={props.payload?.ts === detectedTs ? C.sev : C.volume} />}
          />
          <ReferenceLine x={detectedTs} stroke={C.sev} strokeWidth={1} />
          <Tooltip content={() => null} cursor={{ fill: C.band }} />
        </BarChart>
      </ResponsiveContainer>
    </figure>
  )
}
