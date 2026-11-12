import { Suspense, useEffect, useMemo, useRef } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Environment, Lightformer, useGLTF } from '@react-three/drei'
import { Bloom, EffectComposer, Noise, SMAA, Vignette } from '@react-three/postprocessing'
import { BlendFunction } from 'postprocessing'
import * as THREE from 'three'
import { useSession } from '../store/session'
import { paintMachine, paintMonitor, type ScreenState } from './screens'

useGLTF.preload('/models/dialysis_bay.glb')

type ScreenRefs = {
  machine?: THREE.MeshBasicMaterial
  monitor?: THREE.MeshBasicMaterial
  alarm?: THREE.MeshStandardMaterial
  alarmMesh?: THREE.Object3D
  droplet?: THREE.Object3D
  dropletBase?: number
  blanket?: THREE.Object3D
}

function Model() {
  const { scene } = useGLTF('/models/dialysis_bay.glb')
  const refs = useRef<ScreenRefs>({})
  const alarmLight = useRef<THREE.PointLight>(null)
  const drawMachine = useRef(0)
  const drawMonitor = useRef(0)

  const machineCanvas = useMemo(() => {
    const c = document.createElement('canvas')
    c.width = 512
    c.height = 340
    return c
  }, [])
  const monitorCanvas = useMemo(() => {
    const c = document.createElement('canvas')
    c.width = 640
    c.height = 388
    return c
  }, [])

  const machineTex = useMemo(() => {
    const t = new THREE.CanvasTexture(machineCanvas)
    t.colorSpace = THREE.SRGBColorSpace
    t.anisotropy = 4
    return t
  }, [machineCanvas])

  const monitorTex = useMemo(() => {
    const t = new THREE.CanvasTexture(monitorCanvas)
    t.colorSpace = THREE.SRGBColorSpace
    t.anisotropy = 4
    return t
  }, [monitorCanvas])

  useEffect(() => {
    const all: THREE.Mesh[] = []
    scene.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) all.push(o as THREE.Mesh)
    })
    const meshByName = (name: string) => all.find((m) => m.name === name) ?? null

    scene.traverse((o) => {
      if (!(o as THREE.Mesh).isMesh) return
      const mesh = o as THREE.Mesh
      mesh.castShadow = !/^(SM_Wall|SM_Ceiling|SM_Floor|SM_Window|SM_Skirting|SM_Chair|SM_Cove)/.test(
        mesh.name,
      )
      mesh.receiveShadow = true
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
      mats.forEach((m) => {
        if (!m || !('envMapIntensity' in m)) return
        const std = m as THREE.MeshStandardMaterial
        std.envMapIntensity = /Plastic|Bag|Saline|Screen|Monitor/.test(m.name) ? 0.22 : 0.6
      })
      if (mesh.name === 'SM_ScreenGloss') mesh.visible = false
    })

    const screen = meshByName('SM_MachineScreen')
    if (screen) {
      const mat = new THREE.MeshBasicMaterial({ map: machineTex, toneMapped: false })
      screen.material = mat
      refs.current.machine = mat
    }
    const monitor = meshByName('SM_MonitorScreen')
    if (monitor) {
      const mat = new THREE.MeshBasicMaterial({ map: monitorTex, toneMapped: false })
      monitor.material = mat
      refs.current.monitor = mat
    }
    const alarm = meshByName('SM_AlarmLens') as THREE.Mesh | null
    if (alarm) {
      const mat = new THREE.MeshStandardMaterial({
        color: '#2a0f0a',
        emissive: new THREE.Color('#ff7a59'),
        emissiveIntensity: 0.2,
        roughness: 0.3,
      })
      alarm.material = mat
      refs.current.alarm = mat
      refs.current.alarmMesh = alarm
    }
    const droplet = meshByName('CTRL_Droplet') as THREE.Mesh | null
    if (droplet) {
      refs.current.droplet = droplet
      refs.current.dropletBase = droplet.position.y
    }
    const blanket = meshByName('SM_Blanket') as THREE.Mesh | null
    if (blanket) refs.current.blanket = blanket

    scene.updateMatrixWorld(true)

    const paintOnce = () => {
      const s = useSession.getState()
      const data: ScreenState = {
        t: s.t,
        sbp: s.sbp,
        uf: s.uf,
        inst: s.inst,
        phase: s.phase,
        samples: s.samples,
        crossingAt: s.crossingAt,
      }
      const mctx = machineCanvas.getContext('2d')
      if (mctx) {
        paintMachine(mctx, machineCanvas.width, machineCanvas.height, data)
        machineTex.needsUpdate = true
      }
      const wctx = monitorCanvas.getContext('2d')
      if (wctx) {
        paintMonitor(wctx, monitorCanvas.width, monitorCanvas.height, data)
        monitorTex.needsUpdate = true
      }
    }
    paintOnce()

    const alarmObj = refs.current.alarmMesh
    if (alarmObj && alarmLight.current) {
      const v = new THREE.Vector3()
      alarmObj.getWorldPosition(v)
      alarmLight.current.position.copy(v)
    }
  }, [scene, machineCanvas, machineTex, monitorCanvas, monitorTex])

  useFrame((state, dt) => {
    const s = useSession.getState()
    const data: ScreenState = {
      t: s.t,
      sbp: s.sbp,
      uf: s.uf,
      inst: s.inst,
      phase: s.phase,
      samples: s.samples,
      crossingAt: s.crossingAt,
    }

    drawMachine.current += dt
    if (drawMachine.current > 0.17) {
      drawMachine.current = 0
      const ctx = machineCanvas.getContext('2d')
      if (ctx) {
        paintMachine(ctx, machineCanvas.width, machineCanvas.height, data)
        machineTex.needsUpdate = true
      }
    }
    drawMonitor.current += dt
    if (drawMonitor.current > 0.36) {
      drawMonitor.current = 0
      const ctx = monitorCanvas.getContext('2d')
      if (ctx) {
        paintMonitor(ctx, monitorCanvas.width, monitorCanvas.height, data)
        monitorTex.needsUpdate = true
      }
    }

    const alert = s.phase === 'alert'
    const applied = s.phase === 'applied'
    const settle = s.phase === 'settled'
    const now = state.clock.elapsedTime
    const targetIntensity = alert ? 2.4 + Math.sin(now * 9) * 1.8 : applied ? 0.5 : settle ? 0.9 : 0.16
    const alarmMat = refs.current.alarm
    if (alarmMat) {
      alarmMat.emissiveIntensity += (targetIntensity - alarmMat.emissiveIntensity) * Math.min(1, dt * 6)
      alarmMat.emissive.set(alert ? '#ff7a59' : applied ? '#7cf5e3' : settle ? '#5eead4' : '#31150f')
    }
    if (alarmLight.current) {
      const target = alert ? 0.9 + Math.sin(now * 9) * 0.6 : settle ? 0.35 : 0.05
      alarmLight.current.intensity += (target - alarmLight.current.intensity) * Math.min(1, dt * 5)
      alarmLight.current.color.set(alert ? '#ff8a65' : '#5eead4')
    }

    if (refs.current.droplet && refs.current.dropletBase !== undefined) {
      const cycle = (now * 0.55) % 1
      refs.current.droplet.position.y = refs.current.dropletBase - cycle * 0.052
    }
    if (refs.current.blanket) {
      const breath = Math.sin(now * 0.62) * 0.0028 + Math.sin(now * 0.23) * 0.0012
      refs.current.blanket.scale.y = 1 + breath
    }
  })

  return (
    <>
      <primitive object={scene} />
      <pointLight
        ref={alarmLight}
        color="#ff8a65"
        intensity={0.05}
        distance={1.6}
        decay={2}
        position={[0.55, 1.55, -0.15]}
      />
    </>
  )
}

const BASE_POS = new THREE.Vector3(-2.15, 1.62, -1.85)
const BASE_TARGET = new THREE.Vector3(0.18, 1.08, 0.55)
const UP = new THREE.Vector3(0, 1, 0)

function Rig() {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera
  const pointer = useThree((s) => s.pointer)
  const pan = useRef(-0.42)
  const look = useRef(BASE_TARGET.clone())

  const geom = useMemo(() => {
    const dir = BASE_TARGET.clone().sub(BASE_POS).normalize()
    const right = dir.clone().cross(UP).normalize()
    const up = right.clone().cross(dir).normalize()
    return { dir, right, up }
  }, [])

  useFrame((_, dt) => {
    const phase = useSession.getState().phase
    const open = phase !== 'idle'
    const narrow = camera.aspect < 0.85
    const targetPan = open ? (narrow ? 0 : 0.52) : narrow ? -0.18 : -0.46
    const k = 1 - Math.exp(-dt * 2.0)
    pan.current += (targetPan - pan.current) * k

    const desired = BASE_TARGET.clone()
      .addScaledVector(geom.right, pan.current + pointer.x * 0.05)
      .addScaledVector(geom.up, pointer.y * 0.028)
    look.current.lerp(desired, 1 - Math.exp(-dt * 2.6))

    const dolly = narrow ? -0.55 : open ? 0.06 : 0
    camera.position.copy(BASE_POS).addScaledVector(geom.dir, dolly)
    camera.lookAt(look.current)

    const fov = narrow ? 31 : open ? 27.2 : 27.5
    if (Math.abs(camera.fov - fov) > 0.01) {
      camera.fov += (fov - camera.fov) * k
      camera.updateProjectionMatrix()
    }
  })

  return null
}

const WARM_KEY = new THREE.Color('#ffcfa3')
const RED_KEY = new THREE.Color('#ff6247')

// how far the room should have shifted toward the alarm state
function crashUrgency(phase: string, sbp: number) {
  if (phase === 'alert') return 1
  if (phase === 'applied') return Math.min(0.9, Math.max(0, (104 - sbp) / 20))
  if (phase === 'running') return Math.min(0.55, Math.max(0, (114 - sbp) / 46))
  return 0
}

function KeyLight() {
  const ref = useRef<THREE.SpotLight>(null)
  const urgency = useRef(0)
  useEffect(() => {
    const l = ref.current
    if (!l) return
    l.target.position.set(0.15, 0.95, 0.35)
    l.target.updateMatrixWorld()
    l.shadow.bias = -0.0006
    l.shadow.normalBias = 0.02
    l.shadow.mapSize.set(1024, 1024)
    l.shadow.camera.near = 0.4
    l.shadow.camera.far = 9
  }, [])
  useFrame((_, dt) => {
    const s = useSession.getState()
    const target = crashUrgency(s.phase, s.sbp)
    urgency.current += (target - urgency.current) * Math.min(1, dt * 2.4)
    const l = ref.current
    if (!l) return
    l.color.copy(WARM_KEY).lerp(RED_KEY, urgency.current * 0.85)
    l.intensity = 47 - urgency.current * 5
  })
  return (
    <spotLight
      ref={ref}
      position={[-1.55, 2.5, -1.15]}
      angle={0.7}
      penumbra={0.85}
      intensity={47}
      color="#ffcfa3"
      distance={11}
      decay={1.7}
      castShadow
    />
  )
}

// red wash over the bed that ramps up as the crash approaches and fades
// once the intervention is working
function CrashWash() {
  const ref = useRef<THREE.PointLight>(null)
  const urgency = useRef(0)
  useFrame((state, dt) => {
    const s = useSession.getState()
    const target = crashUrgency(s.phase, s.sbp)
    urgency.current += (target - urgency.current) * Math.min(1, dt * 2.4)
    const l = ref.current
    if (!l) return
    const pulse = s.phase === 'alert' ? 1 + Math.sin(state.clock.elapsedTime * 5.2) * 0.18 : 1
    l.intensity = urgency.current * 15 * pulse
  })
  return (
    <pointLight
      ref={ref}
      position={[0.35, 2.35, 0.05]}
      color="#ff4636"
      intensity={0}
      distance={6.5}
      decay={1.7}
    />
  )
}

function Lights() {
  const { scene } = useThree()
  useEffect(() => {
    scene.environmentIntensity = 0.7
  }, [scene])
  return (
    <>
      <ambientLight intensity={0.22} color="#ffd9bb" />
      <hemisphereLight args={['#25404f', '#0a0c0e', 0.36]} />
      <KeyLight />
      <CrashWash />
      <pointLight position={[2.7, 1.85, -0.9]} intensity={6} color="#8fb8ff" distance={8} decay={1.8} />
      <spotLight
        position={[0.7, 2.4, 1.9]}
        angle={0.8}
        penumbra={1}
        intensity={34}
        color="#8fb4ff"
        distance={9}
        decay={1.6}
      />
      <pointLight position={[0.82, 1.32, -0.05]} intensity={2.8} color="#5eead4" distance={2.6} decay={2} />
      <pointLight position={[-1.95, 1.7, 2.0]} intensity={4.5} color="#9ec8ff" distance={5.5} decay={2} />
      <pointLight position={[-1.5, 1.05, 1.5]} intensity={1.4} color="#ffb98a" distance={4.5} decay={2} />
      <Environment resolution={128} frames={1}>
        <Lightformer
          form="rect"
          intensity={3.2}
          color="#ffd7b0"
          position={[-2, 2.6, -2.4]}
          scale={[4, 2.4, 1]}
        />
        <Lightformer form="rect" intensity={1.6} color="#88b7ff" position={[2.6, 1.7, 1.2]} scale={[2, 1.6, 1]} />
        <Lightformer form="ring" intensity={0.9} color="#4fd8c8" position={[0.4, 1.4, 2.6]} scale={[1.4, 1.4, 1]} />
      </Environment>
    </>
  )
}

export default function Bay() {
  return (
    <Canvas
      shadows
      dpr={[1, 1.5]}
      gl={{ antialias: false, alpha: false, powerPreference: 'high-performance' }}
      camera={{ position: [-2.15, 1.62, -1.85], fov: 27, near: 0.1, far: 40 }}
      onCreated={({ gl }) => {
        gl.toneMapping = THREE.ACESFilmicToneMapping
        gl.toneMappingExposure = 1.06
        gl.setClearColor('#05080b')
      }}
    >
      <fog attach="fog" args={['#05080b', 7, 16]} />
      <Suspense fallback={null}>
        <Model />
        <Lights />
      </Suspense>
      <Rig />
      <EffectComposer multisampling={0}>
        <Bloom intensity={0.6} luminanceThreshold={0.7} luminanceSmoothing={0.3} mipmapBlur />
        <Vignette offset={0.2} darkness={0.75} />
        <Noise opacity={0.032} blendFunction={BlendFunction.SOFT_LIGHT} />
        <SMAA />
      </EffectComposer>
    </Canvas>
  )
}
