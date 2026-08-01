"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import { useReducedMotion } from "framer-motion";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";
import type { ArmSnapshot, DtSnapshot } from "../types";

const PALETTE = {
  stable: "#75e2af",
  strained: "#ffc857",
  overloaded: "#ff754c",
  offline: "#26332d",
  accent: "#c9f04d",
};

const FEEDER_X = [-4.8, 0, 4.8];

function stateOf(loading: number, energized: boolean) {
  if (!energized) return "offline" as const;
  if (loading >= 100) return "overloaded" as const;
  if (loading >= 90) return "strained" as const;
  return "stable" as const;
}

type Placed = { dt: DtSnapshot; position: [number, number, number]; side: number };

function layout(dts: DtSnapshot[]): Placed[] {
  return dts.map((dt) => {
    const feeder = Number(dt.id[1]) - 1;
    const index = Number(dt.id.slice(-2)) - 1;
    const row = index % 10;
    const side = Math.floor(index / 10) === 0 ? -1 : 1;
    return { dt, side, position: [FEEDER_X[feeder] + side * 1.12, 0, -4.7 + row * 1.08] };
  });
}

function House({ x, z, lit, selected }: { x: number; z: number; lit: boolean; selected: boolean }) {
  return <group position={[x, 0, z]}>
    <mesh position={[0, .13, 0]} castShadow><boxGeometry args={[.3, .25, .28]} /><meshStandardMaterial color={lit ? "#d7edb9" : "#16221d"} emissive={lit ? PALETTE.accent : "#000000"} emissiveIntensity={lit ? selected ? .75 : .32 : 0} roughness={.9} /></mesh>
    <mesh position={[0, .31, 0]} rotation={[0, Math.PI / 4, 0]} castShadow><coneGeometry args={[.25, .2, 4]} /><meshStandardMaterial color={lit ? "#849368" : "#202c26"} roughness={.95} /></mesh>
    <mesh position={[0, .14, .145]}><planeGeometry args={[.1, .08]} /><meshBasicMaterial color={lit ? "#e9ff9b" : "#0a100d"} /></mesh>
  </group>;
}

function Locality({ placed, intervened, onHover, onSelect, selected }: { placed: Placed; intervened: boolean; onHover: (dt: DtSnapshot | null) => void; onSelect: (id: string) => void; selected: boolean }) {
  const body = useRef<THREE.Mesh>(null);
  const ring = useRef<THREE.Mesh>(null);
  const { dt, position, side } = placed;
  const state = stateOf(dt.loading_pct, dt.energized);
  const target = useMemo(() => new THREE.Color(PALETTE[state]), [state]);
  const darkRatio = Math.min(1, dt.households_dark / 70);

  useFrame((clock) => {
    if (body.current) {
      const material = body.current.material as THREE.MeshStandardMaterial;
      material.color.lerp(target, .12);
      material.emissive.lerp(target, .12);
      material.emissiveIntensity = dt.energized ? selected ? 1 : .42 : .02;
    }
    if (ring.current) {
      const material = ring.current.material as THREE.MeshBasicMaterial;
      const alarm = state === "overloaded" ? .48 + Math.sin(clock.clock.elapsedTime * 5) * .2 : intervened ? .28 + Math.sin(clock.clock.elapsedTime * 3) * .08 : selected ? .32 : 0;
      material.opacity += (alarm - material.opacity) * .13;
      material.color.set(state === "overloaded" ? PALETTE.overloaded : PALETTE.accent);
      ring.current.scale.setScalar(1 + alarm * .45);
    }
  });

  return <group position={position} onPointerOver={(event) => { event.stopPropagation(); onHover(dt); document.body.style.cursor = "pointer"; }} onPointerOut={() => { onHover(null); document.body.style.cursor = "auto"; }} onClick={(event) => { event.stopPropagation(); onSelect(dt.id); }}>
    <mesh position={[0, .05, 0]}><cylinderGeometry args={[.34, .42, .1, 8]} /><meshStandardMaterial color="#203029" roughness={.8} /></mesh>
    <mesh ref={body} position={[0, .38, 0]} castShadow><boxGeometry args={[.34, .62, .34]} /><meshStandardMaterial color={PALETTE[state]} emissive={PALETTE[state]} emissiveIntensity={.4} metalness={.35} roughness={.3} /></mesh>
    <mesh position={[0, .75, 0]}><cylinderGeometry args={[.045, .045, .35, 8]} /><meshStandardMaterial color="#73847b" metalness={.6} /></mesh>
    <mesh ref={ring} position={[0, .035, 0]} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[.43, .58, 28]} /><meshBasicMaterial transparent opacity={0} side={THREE.DoubleSide} /></mesh>
    {[[-side * .52, -.27], [-side * .78, .02], [-side * .52, .31]].map(([offsetX, offsetZ], index) => <House key={index} x={offsetX} z={offsetZ} lit={dt.energized && index / 3 >= darkRatio} selected={selected} />)}
    {selected && <Html center position={[0, 1.2, 0]} distanceFactor={13}><div className="twin-selected-tag"><span>{dt.id}</span><strong>{dt.loading_pct.toFixed(0)}%</strong></div></Html>}
  </group>;
}

function Feeder({ x, loading, id }: { x: number; loading: number; id: string }) {
  const flow = useRef<THREE.Mesh>(null);
  const state = stateOf(loading, true);
  useFrame((clock) => {
    if (!flow.current) return;
    const t = (clock.clock.elapsedTime * (.14 + loading / 180)) % 1;
    flow.current.position.z = -5.5 + t * 11;
    (flow.current.material as THREE.MeshBasicMaterial).opacity = Math.sin(t * Math.PI) * .8;
  });
  return <group>
    <mesh position={[x, .014, 0]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[.075, 11.2]} /><meshBasicMaterial color={PALETTE[state]} transparent opacity={.58} /></mesh>
    <mesh ref={flow} position={[x, .026, -5.5]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[.22, .72]} /><meshBasicMaterial color={PALETTE.accent} transparent opacity={0} /></mesh>
    {[-4.7, -2.55, -.4, 1.75, 3.9].map((z) => <mesh key={z} position={[x, .02, z]} rotation={[-Math.PI / 2, 0, Math.PI / 2]}><planeGeometry args={[.035, 2.3]} /><meshBasicMaterial color="#365047" transparent opacity={.62} /></mesh>)}
    <Html center position={[x, .08, 5.65]} distanceFactor={15}><div className="twin-tag">{id} <b>{loading.toFixed(0)}%</b></div></Html>
  </group>;
}

function Substation() {
  const core = useRef<THREE.Mesh>(null);
  useFrame((clock) => { if (core.current) core.current.rotation.y = clock.clock.elapsedTime * .28; });
  return <group position={[0, 0, -6.35]}>
    <mesh position={[0, .08, 0]}><cylinderGeometry args={[.72, .9, .16, 8]} /><meshStandardMaterial color="#1c3128" /></mesh>
    <mesh ref={core} position={[0, .63, 0]}><octahedronGeometry args={[.48, 0]} /><meshStandardMaterial color={PALETTE.accent} emissive={PALETTE.accent} emissiveIntensity={1.15} wireframe /></mesh>
    {FEEDER_X.map((x) => <mesh key={x} position={[x / 2, .035, 3.15]} rotation={[-Math.PI / 2, 0, Math.atan2(x, 6.3)]}><planeGeometry args={[.055, Math.sqrt(x * x + 39.7)]} /><meshBasicMaterial color="#4f6c5f" transparent opacity={.7} /></mesh>)}
    <Html center position={[0, 1.45, 0]} distanceFactor={14}><div className="twin-tag substation-tag">PRIMARY SUBSTATION</div></Html>
  </group>;
}

function CriticalFacility({ uptime }: { uptime: number }) {
  const lit = uptime >= 100;
  return <group position={[-7.3, 0, 1.7]}>
    <mesh position={[0, .32, 0]} castShadow><boxGeometry args={[1.1, .64, .8]} /><meshStandardMaterial color={lit ? "#e5eddf" : "#27322d"} emissive={lit ? PALETTE.stable : "#000000"} emissiveIntensity={lit ? .23 : 0} /></mesh>
    <mesh position={[0, .66, 0]}><boxGeometry args={[.22, .22, .05]} /><meshBasicMaterial color={lit ? PALETTE.stable : PALETTE.offline} /></mesh>
    <mesh position={[0, .66, .026]}><boxGeometry args={[.07, .18, .02]} /><meshBasicMaterial color="#07110e" /></mesh>
    <mesh position={[0, .66, .027]}><boxGeometry args={[.18, .07, .02]} /><meshBasicMaterial color="#07110e" /></mesh>
    <Html center position={[0, 1.08, 0]} distanceFactor={13}><div className={`critical-tag ${lit ? "protected" : ""}`}><i>+</i><span>CRITICAL FACILITY<b>{uptime.toFixed(0)}% UPTIME</b></span></div></Html>
  </group>;
}

function Scene({ snapshot, activeTargets, selectedDt, onSelect, onHover, reduced, presentation }: { snapshot: ArmSnapshot; activeTargets: Set<string>; selectedDt: string; onSelect: (id: string) => void; onHover: (dt: DtSnapshot | null) => void; reduced: boolean; presentation: boolean }) {
  const placed = useMemo(() => layout(snapshot.dts), [snapshot.dts]);
  return <>
    <fog attach="fog" args={["#07110e", 11, 28]} />
    <ambientLight intensity={.72} />
    <directionalLight position={[4, 12, 5]} intensity={1.45} castShadow />
    <pointLight position={[0, 5, -6]} intensity={30} color={PALETTE.accent} distance={18} />
    <Substation />
    <CriticalFacility uptime={snapshot.metrics.critical_uptime_pct} />
    {FEEDER_X.map((x, index) => <Feeder key={x} x={x} loading={snapshot.feeders[index]?.loading_pct ?? 0} id={snapshot.feeders[index]?.id ?? `F${index + 1}`} />)}
    {placed.map((item) => <Locality key={item.dt.id} placed={item} intervened={activeTargets.has(item.dt.id)} selected={selectedDt === item.dt.id} onSelect={onSelect} onHover={onHover} />)}
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -.03, 0]} receiveShadow><planeGeometry args={[22, 17]} /><meshStandardMaterial color="#08130e" roughness={1} /></mesh>
    {[-6.9, -2.4, 2.2].map((z) => <mesh key={z} position={[0, -.015, z]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[17, .45]} /><meshBasicMaterial color="#101d18" /></mesh>)}
    <gridHelper args={[22, 22, "#1b2f26", "#102019"]} position={[0, -.02, 0]} />
    <OrbitControls enablePan={false} enableDamping minDistance={8} maxDistance={22} minPolarAngle={.25} maxPolarAngle={Math.PI / 2.18} autoRotate={!reduced} autoRotateSpeed={presentation ? .22 : .12} />
  </>;
}

export function Network3D({ snapshot, label, selectedDt, onSelect, activeTargets = new Set<string>(), presentation = false }: { snapshot: ArmSnapshot; label: string; selectedDt: string; onSelect: (id: string) => void; activeTargets?: Set<string>; presentation?: boolean }) {
  const [hovered, setHovered] = useState<DtSnapshot | null>(null);
  const reduced = Boolean(useReducedMotion());
  const selected = snapshot.dts.find((dt) => dt.id === selectedDt);
  const inspected = hovered ?? selected;
  return <div className={`twin-stage ${presentation ? "presentation" : ""}`}>
    <Canvas camera={{ position: [0, 10.5, 13.5], fov: 42 }} dpr={[1, 1.5]} shadows gl={{ antialias: true, powerPreference: "high-performance" }}>
      <Scene snapshot={snapshot} activeTargets={activeTargets} selectedDt={selectedDt} onSelect={onSelect} onHover={setHovered} reduced={reduced} presentation={presentation} />
    </Canvas>
    <div className="twin-readout">{inspected ? <><span>{inspected.energized ? "LOCALITY ENERGISED" : "LOCALITY OFFLINE"}</span><strong>{inspected.id}</strong><small>{inspected.loading_pct.toFixed(1)}% of limit · {inspected.households_dark} homes dark</small></> : <><span>SPATIAL NETWORK</span><strong>{label}</strong><small>Select a locality to inspect its transformer and homes.</small></>}</div>
    <div className="twin-key">{(["stable", "strained", "overloaded", "offline"] as const).map((state) => <span key={state}><i style={{ background: PALETTE[state] }} />{state}</span>)}</div>
    {!presentation && <div className="twin-help">DRAG TO ORBIT · SCROLL TO ZOOM · SELECT A LOCALITY</div>}
  </div>;
}
