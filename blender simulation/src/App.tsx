import { useEffect, useRef, useState } from 'react'
import { useProgress } from '@react-three/drei'
import Bay from './components/Bay'
import Hero from './components/Hero'
import Panel from './components/Panel'
import { useSession } from './store/session'

function TopBar() {
  const phase = useSession((s) => s.phase)
  const t = useSession((s) => s.t)
  const live = phase !== 'idle'
  const clock = `${String(Math.floor(t)).padStart(2, '0')}:${String(Math.floor((t % 1) * 60)).padStart(2, '0')}`

  return (
    <header className="topbar">
      <div className="brand">
        <span className="mark">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path
              d="M1 10h3.2l1.6-4.4L8.6 13l2-7 1.5 4h4.9"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          </svg>
        </span>
        <span className="brand-name">HemoTwin</span>
        <span className="brand-div" />
        <span className="brand-tag">Simulation</span>
      </div>
      <div className="top-status">
        {live ? (
          <>
            <span className="live-pill">
              <i />
              Live
            </span>
            <span className="top-clock">{clock}</span>
          </>
        ) : (
          <span className="top-idle">Bay 04 · ready</span>
        )}
      </div>
    </header>
  )
}

function LoadPortal() {
  const { active, progress, loaded } = useProgress()
  const [ready, setReady] = useState(false)
  const [gone, setGone] = useState(false)
  const mount = useRef(performance.now())

  useEffect(() => {
    if (!active && loaded > 0) {
      const wait = Math.max(0, 900 - (performance.now() - mount.current))
      const id = window.setTimeout(() => setReady(true), wait)
      return () => window.clearTimeout(id)
    }
  }, [active, loaded])

  useEffect(() => {
    if (!ready) return
    const id = window.setTimeout(() => setGone(true), 1400)
    return () => window.clearTimeout(id)
  }, [ready])

  return (
    <>
      <div className="poster" data-ready={ready} aria-hidden="true">
        <img src="/models/poster.jpg" alt="" />
      </div>
      <div className="boot" data-ready={ready} data-gone={gone}>
        <div className="boot-line">
          <span>Preparing bay 04</span>
          <span className="mono">{Math.min(100, Math.round(progress))}%</span>
        </div>
        <div className="boot-track">
          <i style={{ width: `${Math.max(6, progress)}%` }} />
        </div>
      </div>
    </>
  )
}

export default function App() {
  const step = useSession((s) => s.step)
  const apply = useSession((s) => s.apply)
  const phase = useSession((s) => s.phase)
  const embed = new URLSearchParams(window.location.search).has('embed')

  useEffect(() => {
    let raf = 0
    let last = performance.now()
    const loop = (now: number) => {
      const dt = (now - last) / 1000
      last = now
      step(dt)
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [step])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === '1') apply('taper')
      else if (e.key === '2') apply('hold')
      else if (e.key === '3') apply('bolus')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [apply])

  return (
    <div className="app" data-live={phase !== 'idle'}>
      <div className="bay-canvas">
        <Bay />
      </div>
      <div className="scrim" aria-hidden="true" />
      <LoadPortal />
      {!embed && <TopBar />}
      <Hero />
      <Panel />
      {!embed && (
        <div className="hint">
          <span className="hint-dot" />
          Move your cursor to look around
        </div>
      )}
    </div>
  )
}
