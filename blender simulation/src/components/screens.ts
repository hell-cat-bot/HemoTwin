import type { Phase, Sample } from '../sim/engine'

export interface ScreenState {
  t: number
  sbp: number
  uf: number
  inst: number
  phase: Phase
  samples: Sample[]
  crossingAt: number | null
}

const TEAL = '#7cf5e3'
const TEAL_DIM = '#3f8f88'
const AMBER = '#ffb27a'
const INK = '#04090b'

function clock(t: number) {
  const m = Math.floor(t)
  const s = Math.floor((t % 1) * 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function bg(ctx: CanvasRenderingContext2D, w: number, h: number) {
  const g = ctx.createLinearGradient(0, 0, 0, h)
  g.addColorStop(0, '#081215')
  g.addColorStop(1, INK)
  ctx.fillStyle = g
  ctx.fillRect(0, 0, w, h)
  ctx.fillStyle = 'rgba(124,245,227,0.035)'
  for (let y = 0; y < h; y += 3) ctx.fillRect(0, y, w, 1)
}

function status(s: ScreenState) {
  if (s.phase === 'alert') return { label: 'PREDICT', color: AMBER }
  if (s.phase === 'applied') return { label: 'RECOVERING', color: TEAL }
  if (s.phase === 'settled') return { label: 'STABLE', color: TEAL }
  return { label: 'MONITOR', color: TEAL_DIM }
}

export function paintMachine(ctx: CanvasRenderingContext2D, w: number, h: number, s: ScreenState) {
  bg(ctx, w, h)
  const accent = s.phase === 'alert' ? AMBER : TEAL

  ctx.fillStyle = accent
  ctx.fillRect(0, 0, w, 3)

  ctx.font = '600 15px "IBM Plex Mono", monospace'
  ctx.fillStyle = TEAL_DIM
  ctx.fillText('HEMO 04', 22, 34)
  const st = status(s)
  ctx.fillStyle = st.color
  ctx.textAlign = 'right'
  ctx.fillText(`T+${clock(s.t)}`, w - 22, 34)
  ctx.textAlign = 'left'

  ctx.strokeStyle = 'rgba(124,245,227,0.14)'
  ctx.beginPath()
  ctx.moveTo(22, 48)
  ctx.lineTo(w - 22, 48)
  ctx.stroke()

  ctx.font = '500 12px "IBM Plex Mono", monospace'
  ctx.fillStyle = TEAL_DIM
  ctx.fillText('SBP', 24, 78)
  ctx.fillStyle = accent
  ctx.fillRect(24, 86, 3, 74)

  ctx.font = '600 82px "IBM Plex Mono", monospace'
  ctx.fillStyle = s.phase === 'alert' ? AMBER : '#eafffb'
  ctx.fillText(Math.round(s.sbp).toString(), 40, 158)
  ctx.font = '500 14px "IBM Plex Mono", monospace'
  ctx.fillStyle = TEAL_DIM
  ctx.fillText('mmHg', 42, 182)

  ctx.font = '600 13px "IBM Plex Mono", monospace'
  ctx.fillStyle = st.color
  ctx.fillText(st.label, 24, 214)
  if (s.phase === 'alert' && s.crossingAt !== null) {
    ctx.font = '500 12px "IBM Plex Mono", monospace'
    ctx.fillStyle = AMBER
    ctx.fillText(`<90 in ${Math.max(1, Math.round(s.crossingAt - s.t))}m`, 118, 214)
  }

  const rx = 292
  ctx.font = '500 12px "IBM Plex Mono", monospace'
  ctx.fillStyle = TEAL_DIM
  ctx.fillText('UF RATE', rx, 78)
  ctx.font = '600 40px "IBM Plex Mono", monospace'
  ctx.fillStyle = '#d7fbf4'
  ctx.fillText(s.uf.toFixed(2), rx, 120)
  ctx.font = '500 13px "IBM Plex Mono", monospace'
  ctx.fillStyle = TEAL_DIM
  ctx.fillText('L/h', rx + 104, 120)

  ctx.fillStyle = 'rgba(124,245,227,0.12)'
  ctx.fillRect(rx, 140, 190, 2)
  ctx.fillStyle = accent
  ctx.fillRect(rx, 140, 190 * Math.max(0, Math.min(1, s.uf / 0.42)), 2)
  ctx.font = '500 12px "IBM Plex Mono", monospace'
  ctx.fillStyle = TEAL_DIM
  ctx.fillText('REFILL', rx, 166)
  ctx.fillStyle = '#d7fbf4'
  ctx.fillText(`${Math.round(100 - 78 * s.inst)}%`, rx + 70, 166)

  ctx.fillStyle = '#d7fbf4'
  ctx.fillText('TMP', rx, 190)
  ctx.fillStyle = TEAL_DIM
  ctx.fillText('36.6 C', rx + 70, 190)

  const gy = 236
  const gh = h - gy - 18
  ctx.fillStyle = 'rgba(3,8,10,0.7)'
  ctx.fillRect(22, gy, w - 44, gh)
  ctx.strokeStyle = 'rgba(124,245,227,0.10)'
  ctx.strokeRect(22, gy, w - 44, gh)

  const win = 10
  const recent = s.samples.filter((p) => p.t > s.t - win)
  const x0 = 26
  const x1 = w - 26
  const vMin = 78
  const vMax = 138
  const px = (t: number) => x0 + ((t - (s.t - win)) / win) * (x1 - x0)
  const py = (v: number) => gy + gh - ((v - vMin) / (vMax - vMin)) * gh

  ctx.setLineDash([3, 4])
  ctx.strokeStyle = 'rgba(255,122,89,0.4)'
  ctx.beginPath()
  ctx.moveTo(x0, py(90))
  ctx.lineTo(x1, py(90))
  ctx.stroke()
  ctx.setLineDash([])

  if (recent.length > 1) {
    ctx.beginPath()
    recent.forEach((p, i) => {
      const X = px(p.t)
      const Y = py(p.v)
      if (i === 0) ctx.moveTo(X, Y)
      else ctx.lineTo(X, Y)
    })
    ctx.strokeStyle = accent
    ctx.lineWidth = 1.6
    ctx.stroke()
    ctx.lineTo(px(recent[recent.length - 1].t), gy + gh)
    ctx.lineTo(px(recent[0].t), gy + gh)
    ctx.closePath()
    ctx.fillStyle = 'rgba(124,245,227,0.07)'
    ctx.fill()
  }

  if (s.phase === 'alert') {
    const blink = 0.55 + 0.45 * Math.sin(performance.now() / 180)
    ctx.fillStyle = `rgba(255,178,122,${blink})`
    ctx.beginPath()
    ctx.arc(w - 154, 30, 4, 0, Math.PI * 2)
    ctx.fill()
  }
}

export function paintMonitor(ctx: CanvasRenderingContext2D, w: number, h: number, s: ScreenState) {
  bg(ctx, w, h)
  const accent = s.phase === 'alert' ? AMBER : TEAL

  ctx.fillStyle = accent
  ctx.fillRect(0, 0, w, 3)
  ctx.font = '600 17px "IBM Plex Mono", monospace'
  ctx.fillStyle = TEAL_DIM
  ctx.fillText('HEMOTWIN', 26, 38)
  ctx.fillStyle = 'rgba(124,245,227,0.35)'
  ctx.fillText('/ 04', 130, 38)

  const st = status(s)
  ctx.textAlign = 'right'
  ctx.font = '500 13px "IBM Plex Mono", monospace'
  ctx.fillStyle = st.color
  ctx.fillText(`● ${st.label}`, w - 26, 38)
  ctx.textAlign = 'left'

  ctx.strokeStyle = 'rgba(124,245,227,0.14)'
  ctx.beginPath()
  ctx.moveTo(26, 54)
  ctx.lineTo(w - 26, 54)
  ctx.stroke()

  const gx = 26
  const gy = 92
  const gw = w - 52
  const gh = 150
  ctx.strokeStyle = 'rgba(124,245,227,0.08)'
  ctx.strokeRect(gx, gy, gw, gh)

  const win = 26
  const t0 = Math.max(0, s.t - win)
  const vMin = 76
  const vMax = 136
  const px = (t: number) => gx + ((t - t0) / Math.max(6, s.t - t0)) * gw
  const py = (v: number) => gy + gh - ((v - vMin) / (vMax - vMin)) * gh

  ctx.setLineDash([4, 5])
  ctx.strokeStyle = 'rgba(255,122,89,0.45)'
  ctx.beginPath()
  ctx.moveTo(gx, py(90))
  ctx.lineTo(gx + gw, py(90))
  ctx.stroke()
  ctx.setLineDash([])
  ctx.font = '500 11px "IBM Plex Mono", monospace'
  ctx.fillStyle = 'rgba(255,122,89,0.6)'
  ctx.fillText('90', gx + 6, py(90) - 6)

  const recent = s.samples.filter((p) => p.t >= t0)
  if (recent.length > 1) {
    ctx.beginPath()
    recent.forEach((p, i) => {
      const X = px(p.t)
      const Y = py(p.v)
      if (i === 0) ctx.moveTo(X, Y)
      else ctx.lineTo(X, Y)
    })
    ctx.strokeStyle = accent
    ctx.lineWidth = 2
    ctx.stroke()
    ctx.lineTo(px(recent[recent.length - 1].t), gy + gh)
    ctx.lineTo(px(recent[0].t), gy + gh)
    ctx.closePath()
    ctx.fillStyle = 'rgba(124,245,227,0.06)'
    ctx.fill()
  }

  const big = Math.round(s.sbp)
  ctx.font = '600 76px "IBM Plex Mono", monospace'
  ctx.fillStyle = s.phase === 'alert' ? AMBER : '#eafffb'
  ctx.fillText(String(big), 24, 310)
  ctx.font = '500 14px "IBM Plex Mono", monospace'
  ctx.fillStyle = TEAL_DIM
  ctx.fillText('SBP / mmHg', 26, 332)

  const cols = [240, 390, 530]
  const labels = ['UF L/h', 'REFILL %', 'SESSION']
  const values = [s.uf.toFixed(2), `${Math.round(100 - 78 * s.inst)}`, clock(s.t)]
  ctx.font = '500 12px "IBM Plex Mono", monospace'
  cols.forEach((cx, i) => {
    ctx.fillStyle = TEAL_DIM
    ctx.fillText(labels[i], cx, 274)
    ctx.font = '600 34px "IBM Plex Mono", monospace'
    ctx.fillStyle = '#d7fbf4'
    ctx.fillText(values[i], cx, 312)
    ctx.font = '500 12px "IBM Plex Mono", monospace'
  })

  ctx.font = '500 12px "IBM Plex Mono", monospace'
  ctx.fillStyle = 'rgba(124,245,227,0.35)'
  ctx.fillText('PREDICTIVE SURVEILLANCE · 250 HZ', 26, h - 18)

  if (s.phase === 'alert') {
    const blink = 0.5 + 0.5 * Math.sin(performance.now() / 200)
    ctx.fillStyle = `rgba(255,178,122,${blink})`
    ctx.fillRect(w - 116, h - 26, 90, 2)
  }
}
