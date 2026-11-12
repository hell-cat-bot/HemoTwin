import Chart from './Chart'
import { INTERVENTIONS, refillReserve } from '../sim/engine'
import { useSession } from '../store/session'

const pad = (n: number) => String(n).padStart(2, '0')
const clock = (t: number) => `${pad(Math.floor(t))}:${pad(Math.floor((t % 1) * 60))}`

function StatusChip({ phase }: { phase: string }) {
  const map: Record<string, [string, string]> = {
    running: ['Monitoring', 'teal'],
    alert: ['Prediction', 'amber'],
    applied: ['Recovering', 'teal'],
    settled: ['Stable', 'teal'],
  }
  const [label, tone] = map[phase] ?? ['Idle', 'dim']
  return (
    <span className={`chip chip-${tone}`}>
      <i />
      {label}
    </span>
  )
}

export default function Panel() {
  const s = useSession()
  const open = s.phase !== 'idle'
  const delta = Math.round(s.sbp - 125.6)
  const current = INTERVENTIONS.find((i) => i.id === s.chosen)
  const recOpt = INTERVENTIONS.find((i) => i.id === s.rec)

  const alertLead =
    s.crossingAt !== null ? Math.max(1, Math.round(s.crossingAt - s.t)) : null

  return (
    <aside className="panel" data-open={open} data-tone={s.phase} aria-hidden={!open}>
      <div className="panel-scroll">
        <div className="panel-top">
          <div className="panel-id">
            <span className="live-dot" />
            <span>Bay 04 · Session</span>
          </div>
          <div className="panel-clock">
            <div className="speed" role="group" aria-label="Simulation speed">
              {[1, 2, 3, 4].map((n) => (
                <button
                  key={n}
                  className={`speed-btn${s.speed === n ? ' on' : ''}`}
                  onClick={() => s.setSpeed(n)}
                  aria-pressed={s.speed === n}
                  aria-label={`${n}x speed`}
                >
                  {n}×
                </button>
              ))}
            </div>
            <span>{clock(s.t)}</span>
            <button className="icon-btn" onClick={s.reset} aria-label="End session">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.4" />
              </svg>
            </button>
          </div>
        </div>

        <div className="vitals">
          <div className="vitals-label">
            <span>Systolic pressure</span>
            <StatusChip phase={s.phase} />
          </div>
          <div className="vitals-main">
            <span className="big">{Math.round(s.sbp)}</span>
            <div className="vitals-side">
              <span className="unit">mmHg</span>
              <span className={`delta ${delta < -8 ? 'down' : ''}`}>
                {delta === 0 ? '±0' : delta > 0 ? `+${delta}` : delta} from baseline
              </span>
            </div>
          </div>
          <div className="vitals-meta">
            <span>
              UF <b>{s.uf.toFixed(2)}</b> L/h
            </span>
            <span>
              Refill reserve <b>{refillReserve(s.inst)}%</b>
            </span>
          </div>
        </div>

        <div className="chart-card">
          <div className="chart-head">
            <span>Trend · mmHg</span>
            <span className="chart-win">0 → {Math.round(s.t)} min</span>
          </div>
          <Chart
            samples={s.samples}
            forecast={s.forecast}
            ghost={s.ghost}
            appliedAt={s.appliedAt}
            phase={s.phase}
            crossingAt={s.crossingAt}
          />
          <div className="legend">
            <span className="lg now">Now</span>
            <span className="lg forecast">Forecast</span>
            {s.ghost && <span className="lg ghost">Untreated</span>}
            <span className="lg threshold">90 limit</span>
          </div>
        </div>

        {s.phase !== 'running' && (
          <div className={`predict predict-${s.phase}`}>
            <div className="predict-icon">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="6.2" stroke="currentColor" strokeWidth="1.1" opacity=".45" />
                <circle cx="8" cy="8" r="2.4" fill="currentColor" />
                <circle cx="8" cy="8" r="6.2" stroke="currentColor" strokeWidth="1.1" strokeDasharray="2 3" />
              </svg>
            </div>
            <div>
              {s.phase === 'alert' && (
                <>
                  <h4>
                    {s.sbp <= 90 ? 'Hypotension active' : `Crash predicted · ~${alertLead} min`}
                  </h4>
                  <p>
                    Recommended: {recOpt?.title.toLowerCase()}. Untreated SBP keeps falling.
                  </p>
                </>
              )}
            {s.phase === 'applied' && (
              <>
                <h4>Intervention applied</h4>
                <p>
                  {current?.title} · SBP {Math.round(s.sbp)} mmHg, {Math.abs(delta)} below
                  baseline.
                </p>
              </>
            )}
            {s.phase === 'settled' && (
              <>
                <h4>Session recovered</h4>
                <p>SBP stable above 90 mmHg. Session can resume at a reduced rate.</p>
              </>
            )}
          </div>
        </div>
        )}

        <div className="section-label">
          {s.phase === 'alert' ? 'Interventions · predicted event' : 'Interventions'}
        </div>

        <div className="options" data-state={s.phase}>
          {s.phase === 'running' && (
            <div className="options-locked">
              <div className="scanline" />
              <span>Options appear if the forecast crosses 90 mmHg.</span>
            </div>
          )}

          {s.phase !== 'running' &&
            INTERVENTIONS.map((opt) => {
              const rec = s.rec === opt.id && (s.phase === 'alert' || s.phase === 'applied')
              const chosen = s.chosen === opt.id
              return (
                <button
                  key={opt.id}
                  className={`option ${rec && !s.chosen ? 'rec' : ''} ${chosen ? 'chosen' : ''} ${
                    s.chosen && !chosen ? 'dim' : ''
                  }`}
                  onClick={() => s.apply(opt.id)}
                  disabled={s.phase !== 'alert'}
                >
                  <span className="key">{chosen ? '✓' : opt.key}</span>
                  <span className="opt-body">
                    <span className="opt-title">
                      {opt.title}
                      {rec && !s.chosen && <em className="badge">Recommended</em>}
                      {chosen && <em className="badge applied">Applied {clock(s.appliedAt ?? 0)}</em>}
                    </span>
                    <span className="opt-sub">{opt.sub}</span>
                  </span>
                  <span className="opt-cost">{opt.cost}</span>
                </button>
              )
            })}

          {(s.phase === 'applied' || s.phase === 'settled') && (
            <div className="applied-note">
              <span className="check">✓</span>
              <span>
                {current?.title} at {clock(s.appliedAt ?? 0)}. UF now {s.uf.toFixed(2)} L/h.
              </span>
            </div>
          )}
        </div>

        <div className="section-label">Session log</div>
        <ul className="log">
          {s.log.slice(0, s.phase === 'alert' ? 3 : 5).map((l) => (
            <li key={l.id} className={`log-${l.tone}`}>
              <span className="log-time">{clock(l.t)}</span>
              <span className="log-dot" />
              <span className="log-text">{l.text}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="panel-foot">
        <button className="ghost-btn" onClick={s.reset}>
          End session
        </button>
        <span className="kbd-hint">
          {s.phase === 'alert' ? (
            <>
              Press <kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd> to choose
            </>
          ) : s.phase === 'settled' ? (
            <>Simulation complete</>
          ) : (
            <>HemoTwin IDH·4</>
          )}
        </span>
      </div>
    </aside>
  )
}
