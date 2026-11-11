export type Phase = 'idle' | 'running' | 'alert' | 'applied' | 'settled'
export type InterventionId = 'taper' | 'hold' | 'bolus'

export interface Sample {
  t: number
  v: number
}

export interface ForecastPoint {
  t: number
  mid: number
  lo: number
  hi: number
}

export interface Intervention {
  id: InterventionId
  key: string
  title: string
  sub: string
  instCmd: number
  ufFactor: number
  bolus: number
  cost: string
}

export const UF_BASE = 0.42

export const INTERVENTIONS: Intervention[] = [
  {
    id: 'taper',
    key: '1',
    title: 'Taper ultrafiltration',
    sub: 'Reduce UF rate by 40%',
    instCmd: 0.6,
    ufFactor: 0.6,
    bolus: 0,
    cost: 'No volume',
  },
  {
    id: 'hold',
    key: '2',
    title: 'Hold ultrafiltration',
    sub: 'Pause UF for 10 minutes',
    instCmd: 0.34,
    ufFactor: 0,
    bolus: 0,
    cost: 'Delays UF',
  },
  {
    id: 'bolus',
    key: '3',
    title: 'Hold + saline bolus',
    sub: 'Pause UF, give 250 mL',
    instCmd: 0.28,
    ufFactor: 0,
    bolus: 8,
    cost: '+250 mL',
  },
]

export const THRESHOLD = 90

export interface Core {
  t: number
  sbp: number
  inst: number
  instCmd: number
  bolus: number
  intervened: boolean
  ufFactor: number
}

const TAU_SBP = 1.3
const TAU_INST = 4.0
const TAU_BOLUS = 6.0

// instability command: slow drift, a baroreflex plateau, then the crash
const DRIFT_KEYS: Array<[number, number]> = [
  [0, 0.09],
  [3, 0.13],
  [6.5, 0.3],
  [9.5, 0.16],
  [12, 0.34],
  [15.5, 0.72],
  [19, 1.06],
  [23, 1.16],
  [80, 1.16],
]

function driftCmd(t: number) {
  if (t <= DRIFT_KEYS[0][0]) return DRIFT_KEYS[0][1]
  for (let i = 1; i < DRIFT_KEYS.length; i++) {
    const [t1, v1] = DRIFT_KEYS[i]
    if (t <= t1) {
      const [t0, v0] = DRIFT_KEYS[i - 1]
      const s = 0.5 - 0.5 * Math.cos((Math.PI * (t - t0)) / (t1 - t0))
      return v0 + (v1 - v0) * s
    }
  }
  return DRIFT_KEYS[DRIFT_KEYS.length - 1][1]
}

export function createCore(): Core {
  return { t: 0, sbp: 125.6, inst: 0.04, instCmd: 0.12, bolus: 0, intervened: false, ufFactor: 1 }
}

export function advance(c: Core, dtMin: number) {
  if (dtMin <= 0) return
  const n = Math.max(1, Math.ceil(dtMin / 0.04))
  const h = dtMin / n
  for (let i = 0; i < n; i++) {
    c.t += h
    if (!c.intervened) c.instCmd = driftCmd(c.t)
    c.inst += (c.instCmd - c.inst) * (1 - Math.exp(-h / TAU_INST))
    const wobble = 1.05 * Math.sin(0.62 * c.t + 0.4) + 0.55 * Math.sin(1.75 * c.t + 1.9)
    const target = 127 - 42 * c.inst + c.bolus + wobble
    c.sbp += (target - c.sbp) * (1 - Math.exp(-h / TAU_SBP))
    c.bolus *= Math.exp(-h / TAU_BOLUS)
  }
}

export function reading(c: Core) {
  return (
    c.sbp +
    0.8 * Math.sin(c.t * 0.83 + 0.2) +
    0.45 * Math.sin(c.t * 2.1 + 0.7) +
    0.28 * Math.sin(c.t * 3.7 + 2.1) +
    0.14 * Math.sin(c.t * 9.7 + 0.5)
  )
}

export function forecastFrom(c: Core, horizon = 12): ForecastPoint[] {
  const shadow: Core = { ...c }
  const out: ForecastPoint[] = []
  for (let m = 1; m <= horizon; m++) {
    advance(shadow, 1)
    const spread = 0.9 + m * 0.5
    out.push({ t: shadow.t, mid: shadow.sbp, lo: shadow.sbp - spread, hi: shadow.sbp + spread })
  }
  return out
}

export function crossing(points: ForecastPoint[], threshold = THRESHOLD): number | null {
  for (let i = 0; i < points.length; i++) {
    if (points[i].mid < threshold) {
      const prev = i === 0 ? threshold + 1 : points[i - 1].mid
      const span = Math.max(0.001, prev - points[i].mid)
      const frac = Math.min(1, Math.max(0, (prev - threshold) / span))
      return points[i].t - 1 + frac
    }
  }
  return null
}

export function recommend(sbp: number): InterventionId {
  return sbp < 93 ? 'bolus' : 'taper'
}

export function refillReserve(inst: number) {
  return Math.round(100 - 78 * inst)
}
