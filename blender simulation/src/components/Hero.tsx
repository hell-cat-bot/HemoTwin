import { useSession } from '../store/session'

export default function Hero() {
  const phase = useSession((s) => s.phase)
  const start = useSession((s) => s.start)
  const idle = phase === 'idle'

  return (
    <section className="hero" data-hidden={!idle} aria-hidden={!idle}>
      <div className="hero-eyebrow">
        <span className="eyebrow-dot" />
        Intradialytic hypotension · live forecast
      </div>
      <h1>
        See the drop
        <br />
        before it lands.
      </h1>
      <p className="hero-sub">
        A real-time twin of the dialysis bay. Start a session and watch HemoTwin call the crash from the refill
        curve — then correct the ultrafiltration before SBP reaches 90.
      </p>
      <div className="hero-actions">
        <button className="start-btn" onClick={start} disabled={!idle}>
          <span>Start session</span>
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M3 9h11M10 4.5L14.5 9 10 13.5" stroke="currentColor" strokeWidth="1.5" />
          </svg>
        </button>
        <span className="hero-note">Runs live in your browser</span>
      </div>
      <div className="hero-meta">
        <div>
          <span>Prediction lead</span>
          <b>≈ 8 min</b>
        </div>
        <div>
          <span>Threshold</span>
          <b>90 mmHg</b>
        </div>
        <div>
          <span>Session</span>
          <b>~ 90 s</b>
        </div>
      </div>
    </section>
  )
}
