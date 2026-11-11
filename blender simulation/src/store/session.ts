import { create } from 'zustand'
import {
  advance,
  createCore,
  crossing,
  forecastFrom,
  INTERVENTIONS,
  reading,
  recommend,
  type Core,
  type ForecastPoint,
  type InterventionId,
  type Phase,
  type Sample,
} from '../sim/engine'

export interface LogEntry {
  id: number
  t: number
  text: string
  tone: 'muted' | 'watch' | 'alert' | 'good'
}

interface Snapshot {
  phase: Phase
  t: number
  sbp: number
  target: number
  inst: number
  uf: number
  samples: Sample[]
  forecast: ForecastPoint[]
  ghost: ForecastPoint[] | null
  rec: InterventionId
  chosen: InterventionId | null
  appliedAt: number | null
  crossingAt: number | null
  log: LogEntry[]
}

interface Actions {
  start: () => void
  reset: () => void
  apply: (id: InterventionId) => void
  step: (dtReal: number) => void
}

export type SessionStore = Snapshot & Actions

let core: Core = createCore()
let samples: Sample[] = []
let ghost: ForecastPoint[] | null = null
let logId = 1
let acc = 0
let sinceEmit = 0
let alerted = false
let autoRescued = false
let settledAt: number | null = null
let notedRefill = false

const initial: Snapshot = {
  phase: 'idle',
  t: 0,
  sbp: 125,
  target: 125,
  inst: 0.04,
  uf: 0.42,
  samples: [],
  forecast: [],
  ghost: null,
  rec: 'taper',
  chosen: null,
  appliedAt: null,
  crossingAt: null,
  log: [],
}

function entry(t: number, text: string, tone: LogEntry['tone']): LogEntry {
  return { id: logId++, t, text, tone }
}

const EMPTY_ACTIONS = {
  start: () => undefined,
  reset: () => undefined,
  apply: () => undefined,
  step: () => undefined,
}

export const useSession = create<SessionStore>((set, get) => ({
  ...initial,
  ...EMPTY_ACTIONS,

  start: () => {
    core = createCore()
    samples = [{ t: 0, v: reading(core) }]
    ghost = null
    acc = 0
    sinceEmit = 0
    alerted = false
    autoRescued = false
    settledAt = null
    notedRefill = false
    set({
      ...initial,
      phase: 'running',
      sbp: reading(core),
      t: 0,
      log: [entry(0, 'Session started · UF 0.42 L/h', 'muted')],
    })
  },

  reset: () => {
    core = createCore()
    samples = []
    ghost = null
    alerted = false
    autoRescued = false
    settledAt = null
    notedRefill = false
    set({ ...initial })
  },

  apply: (id) => {
    const state = get()
    if (state.phase !== 'alert' || state.chosen) return
    const opt = INTERVENTIONS.find((i) => i.id === id)
    if (!opt) return

    ghost = [{ t: core.t, mid: core.sbp, lo: core.sbp, hi: core.sbp }, ...forecastFrom({ ...core, intervened: false })]
    core.intervened = true
    core.instCmd = opt.instCmd
    core.ufFactor = opt.ufFactor
    core.bolus = opt.bolus

    const label =
      id === 'taper' ? 'UF reduced 40%' : id === 'hold' ? 'UF paused · hold 10 min' : 'UF paused · 250 mL saline bolus'

    set({
      phase: 'applied',
      chosen: id,
      appliedAt: core.t,
      ghost,
      uf: 0.42 * opt.ufFactor,
      log: [entry(core.t, label, 'good'), ...state.log],
    })
  },

  step: (dtReal) => {
    const state = get()
    if (state.phase === 'idle' || state.phase === 'settled') return

    const rate = state.phase === 'alert' ? 0.3 : state.phase === 'applied' ? 0.46 : 0.36
    const dt = Math.min(dtReal, 0.25)
    acc += dt * rate
    advance(core, acc)
    acc = 0

    sinceEmit += dt
    if (sinceEmit < 0.085) return
    sinceEmit = 0

    const value = reading(core)
    samples.push({ t: core.t, v: value })
    if (samples.length > 4000) samples.splice(0, samples.length - 4000)

    const forecast = forecastFrom(core)
    const crossAt = crossing(forecast)
    const fresh: LogEntry[] = []

    let phase: Phase = state.phase
    let rec = state.rec

    if (phase === 'running' && !notedRefill && core.t > 8) {
      notedRefill = true
      fresh.push(entry(core.t, 'Refill reserve trending down', 'watch'))
    }

    if (phase === 'running' && !alerted && crossAt !== null && crossAt - core.t <= 8) {
      alerted = true
      phase = 'alert'
      rec = recommend(value)
      fresh.push(
        entry(
          core.t,
          `Hypotension predicted in ${Math.max(1, Math.round(crossAt - core.t))} min`,
          'alert',
        ),
      )
    }

    if (phase === 'alert' && value < 90 && rec !== 'bolus') {
      rec = 'bolus'
    }

    if (
      (phase === 'running' || phase === 'alert') &&
      !autoRescued &&
      core.t > 30 &&
      core.sbp < 86
    ) {
      autoRescued = true
      const opt = INTERVENTIONS.find((i) => i.id === 'bolus')!
      ghost = [{ t: core.t, mid: core.sbp, lo: core.sbp, hi: core.sbp }, ...forecastFrom({ ...core, intervened: false })]
      core.intervened = true
      core.instCmd = opt.instCmd
      core.ufFactor = opt.ufFactor
      core.bolus = opt.bolus
      phase = 'applied'
      fresh.push(entry(core.t, 'Safety protocol engaged · UF paused', 'alert'))
      set({ chosen: 'bolus', appliedAt: core.t, ghost, uf: 0, rec: 'bolus' })
    }

    if (phase === 'applied') {
      const sinceApply = core.t - (get().appliedAt ?? core.t)
      if (settledAt === null && sinceApply > 9 && core.sbp > 99) {
        settledAt = core.t
        phase = 'settled'
        fresh.push(entry(core.t, `Recovered · SBP ${Math.round(value)} mmHg`, 'good'))
      }
    }

    set({
      phase,
      t: core.t,
      sbp: value,
      target: core.sbp,
      inst: core.inst,
      uf: 0.42 * core.ufFactor,
      samples: samples.slice(),
      forecast,
      ghost,
      rec,
      crossingAt: crossAt,
      log: fresh.length ? [...fresh.reverse(), ...state.log].slice(0, 24) : state.log,
    })
  },
}))

export const interventionById = (id: InterventionId) => INTERVENTIONS.find((i) => i.id === id)!
