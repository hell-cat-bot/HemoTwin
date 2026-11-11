import { useMemo } from 'react'
import { THRESHOLD, type ForecastPoint, type Phase, type Sample } from '../sim/engine'

interface Props {
  samples: Sample[]
  forecast: ForecastPoint[]
  ghost: ForecastPoint[] | null
  appliedAt: number | null
  phase: Phase
  crossingAt: number | null
}

const W = 396
const H = 152
const PL = 30
const PR = 10
const PT = 12
const PB = 20
const Y_MIN = 70
const Y_MAX = 136

function smoothPath(pts: Array<{ x: number; y: number }>) {
  if (pts.length === 0) return ''
  if (pts.length === 1) return `M${pts[0].x},${pts[0].y}`
  let d = `M${pts[0].x},${pts[0].y}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[i + 2] ?? p2
    const c1x = p1.x + (p2.x - p0.x) / 6
    const c1y = p1.y + (p2.y - p0.y) / 6
    const c2x = p2.x - (p3.x - p1.x) / 6
    const c2y = p2.y - (p3.y - p1.y) / 6
    d += ` C${c1x.toFixed(2)},${c1y.toFixed(2)} ${c2x.toFixed(2)},${c2y.toFixed(2)} ${p2.x.toFixed(2)},${p2.y.toFixed(2)}`
  }
  return d
}

export default function Chart({ samples, forecast, ghost, appliedAt, phase, crossingAt }: Props) {
  const now = samples.length ? samples[samples.length - 1].t : 0
  const xMax = Math.max(36, Math.ceil((now + 6) / 6) * 6)

  const sx = (t: number) => PL + (t / xMax) * (W - PL - PR)
  const sy = (v: number) => PT + ((Y_MAX - v) / (Y_MAX - Y_MIN)) * (H - PT - PB)

  const { linePath, areaPath, last, forecastPath, conePath, ghostPath, ticks } = useMemo(() => {
    const pts = samples.map((s) => ({ x: sx(s.t), y: sy(s.v) }))
    const linePath = pts.length > 1 ? smoothPath(pts) : ''
    const areaPath = pts.length > 1 ? `${linePath} L${pts[pts.length - 1].x},${H - PB} L${pts[0].x},${H - PB} Z` : ''
    const last = samples.length ? samples[samples.length - 1] : null

    let forecastPath = ''
    let conePath = ''
    if (forecast.length && last) {
      const fpts = [{ x: sx(last.t), y: sy(last.v) }, ...forecast.map((f) => ({ x: sx(f.t), y: sy(f.mid) }))]
      forecastPath = smoothPath(fpts)
      const up = forecast.map((f) => `${sx(f.t).toFixed(2)},${sy(f.hi).toFixed(2)}`)
      const down = forecast
        .slice()
        .reverse()
        .map((f) => `${sx(f.t).toFixed(2)},${sy(f.lo).toFixed(2)}`)
      conePath = `M${sx(last.t)},${sy(last.v)} L${up.join(' L')} L${down.join(' L')} Z`
    }

    let ghostPath = ''
    if (ghost && ghost.length > 1) {
      ghostPath = smoothPath(ghost.map((g) => ({ x: sx(g.t), y: sy(g.mid) })))
    }

    const stepX = xMax <= 36 ? 12 : xMax <= 48 ? 12 : 12
    const ticks: { x: number; label: string }[] = []
    for (let t = 0; t <= xMax + 0.1; t += stepX) ticks.push({ x: sx(t), label: t === 0 ? '0' : `${t}` })

    return { linePath, areaPath, last, forecastPath, conePath, ghostPath, ticks }
  }, [samples, forecast, ghost, xMax])

  const yTicks = [80, 100, 120]
  const isAlert = phase === 'alert'
  const crossMin = crossingAt !== null ? Math.max(0, Math.round(crossingAt - now)) : null

  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Systolic blood pressure trend">
        <defs>
          <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#5eead4" stopOpacity="0.16" />
            <stop offset="100%" stopColor="#5eead4" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#5eead4" stopOpacity="0.12" />
            <stop offset="100%" stopColor="#5eead4" stopOpacity="0.02" />
          </linearGradient>
          <linearGradient id="dangerFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ff7a59" stopOpacity="0.10" />
            <stop offset="100%" stopColor="#ff7a59" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        <rect x={PL} y={sy(THRESHOLD)} width={W - PL - PR} height={H - PB - sy(THRESHOLD)} fill="url(#dangerFill)" />

        {yTicks.map((v) => (
          <g key={v}>
            <line className="gridline" x1={PL} x2={W - PR} y1={sy(v)} y2={sy(v)} />
            <text className="axis" x={PL - 7} y={sy(v) + 3} textAnchor="end">
              {v}
            </text>
          </g>
        ))}
        {ticks.map((t) => (
          <g key={t.label}>
            <line className="gridline v" x1={t.x} x2={t.x} y1={PT} y2={H - PB} />
            <text className="axis" x={t.x} y={H - 8} textAnchor="middle">
              {t.label}
            </text>
          </g>
        ))}
        <text className="axis unit" x={W - PR} y={H - 8} textAnchor="end">
          min
        </text>

        <line className="threshold" x1={PL} x2={W - PR} y1={sy(THRESHOLD)} y2={sy(THRESHOLD)} />
        <text className="threshold-label" x={W - PR} y={sy(THRESHOLD) - 5} textAnchor="end">
          90 · HYPOTENSION
        </text>

        {conePath && <path d={conePath} fill="url(#forecastFill)" />}
        {ghostPath && <path className="ghost-line" d={ghostPath} />}
        {areaPath && <path d={areaPath} fill="url(#areaFill)" />}
        {linePath && <path className={`trend-line ${isAlert ? 'alert' : ''}`} d={linePath} />}
        {forecastPath && <path className="forecast-line" d={forecastPath} />}

        {appliedAt !== null && appliedAt <= xMax && (
          <g>
            <line className="applied-line" x1={sx(appliedAt)} x2={sx(appliedAt)} y1={PT} y2={H - PB} />
            <circle className="applied-dot" cx={sx(appliedAt)} cy={PT + 5} r={2.6} />
          </g>
        )}

        {crossMin !== null && phase === 'alert' && (
          <g>
            <line
              className="crosshair"
              x1={sx(now + crossMin)}
              x2={sx(now + crossMin)}
              y1={sy(THRESHOLD)}
              y2={H - PB}
            />
            <text className="cross-label" x={sx(now + crossMin)} y={sy(THRESHOLD) + 12} textAnchor="middle">
              ~{crossMin}m
            </text>
          </g>
        )}

        {last && (
          <g>
            <circle className={`now-halo ${isAlert ? 'alert' : ''}`} cx={sx(last.t)} cy={sy(last.v)} r={7} />
            <circle className={`now-dot ${isAlert ? 'alert' : ''}`} cx={sx(last.t)} cy={sy(last.v)} r={3} />
            <g transform={`translate(${Math.min(sx(last.t) + 10, W - 58)},${Math.max(sy(last.v) - 13, PT + 4)})`}>
              <rect className="value-bg" x={0} y={0} width={46} height={17} rx={3} />
              <text className="value-text" x={23} y={12} textAnchor="middle">
                {Math.round(last.v)}
              </text>
            </g>
          </g>
        )}
      </svg>
    </div>
  )
}
