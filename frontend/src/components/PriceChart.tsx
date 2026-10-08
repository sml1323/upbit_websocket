import { useQuery } from '@tanstack/react-query'
import {
  Area,
  Bar,
  BarChart,
  ComposedChart,
  Line,
  Rectangle,
  type RectangleProps,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api, type Candle, type Severity } from '../api'
import { kstTime, priceFmt } from '../format'

const SEV_COLOR: Record<Severity, string> = {
  low: '#3fb950',
  medium: '#d29922',
  high: '#f0883e',
  critical: '#f85149',
}

type Point = Candle & { ts: number; band: [number, number] | null }

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

export default function PriceChart({ id, severity, detectedAt, now }: { id: string; severity: Severity; detectedAt: string; now: number }) {
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

  const points: Point[] = data.candles.map((c) => ({
    ...c,
    ts: new Date(c.t).getTime(),
    band: c.bb_lower !== null && c.bb_upper !== null ? [c.bb_lower, c.bb_upper] : null,
  }))
  // 감지 시각을 해당 분의 시작으로 맞춘다 (캔들 버킷과 같은 단위)
  const detectedTs = Math.floor(new Date(data.detected_at).getTime() / 60_000) * 60_000
  const color = SEV_COLOR[severity]
  // 방금 감지된 건은 감지 시각이 마지막 캔들보다 뒤일 수 있다 → 감지 선이 보이게 축을 넓힌다
  const xAxis = {
    dataKey: 'ts',
    type: 'number' as const,
    scale: 'time' as const,
    domain: [points[0].ts, Math.max(points[points.length - 1].ts, detectedTs)] as [number, number],
  }
  // 감지 시점이 오른쪽 끝(방금 감지)이면 라벨을 선 왼쪽에 붙여 잘리지 않게
  const nearEnd = xAxis.domain[1] - detectedTs < 10 * 60_000

  return (
    <figure className="chart">
      <figcaption>
        <span>감지 전후 가격 · 1분봉</span>
        <span className="legend">
          <i className="lg-close" />
          종가
          <i className="lg-vwap" />
          VWAP
          <i className="lg-band" />
          볼린저 밴드
          <i className="lg-detect" style={{ background: color }} />
          감지
        </span>
      </figcaption>
      <ResponsiveContainer width="100%" height={200}>
        <ComposedChart data={points} syncId={id} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <XAxis {...xAxis} hide />
          <YAxis
            domain={['auto', 'auto']}
            width={64}
            tickFormatter={priceFmt}
            tick={{ fill: '#8b949e', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          {/* 차트를 바꿀 때마다 그려지는 애니메이션은 끔 — 인시던트를 자주 넘겨 보니까 */}
          <Area dataKey="band" stroke="none" fill="#8b949e" fillOpacity={0.12} isAnimationActive={false} connectNulls />
          <Line dataKey="vwap" stroke="#58a6ff" strokeDasharray="4 3" dot={false} strokeWidth={1.25} isAnimationActive={false} />
          <Line dataKey="close" stroke="#e6edf3" dot={false} strokeWidth={1.5} isAnimationActive={false} />
          <ReferenceLine x={detectedTs} stroke={color} strokeWidth={1.5} label={{ value: '감지', fill: color, fontSize: 11, position: nearEnd ? 'insideTopRight' : 'insideTopLeft' }} />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: '#6e7681', strokeDasharray: '2 2' }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
      <ResponsiveContainer width="100%" height={56}>
        <BarChart data={points} syncId={id} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <XAxis {...xAxis} tickFormatter={(v: number) => kstTime(new Date(v).toISOString())} tick={{ fill: '#8b949e', fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={48} />
          <YAxis width={64} scale="sqrt" tick={false} axisLine={false} tickLine={false} />
          <Bar
            dataKey="volume"
            isAnimationActive={false}
            shape={(props: RectangleProps & { payload?: Point }) => (
              <Rectangle {...props} fill={props.payload?.ts === detectedTs ? color : '#30363d'} />
            )}
          />
          <ReferenceLine x={detectedTs} stroke={color} strokeWidth={1.5} />
          <Tooltip content={() => null} cursor={{ fill: 'rgba(110,118,129,0.15)' }} />
        </BarChart>
      </ResponsiveContainer>
    </figure>
  )
}
