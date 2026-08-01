"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
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
    <mesh position={[0, .14, 0]} castShadow><boxGeometry args={[.34, .28, .32]} /><meshStandardMaterial color={lit ? "#c8dcae" : "#16221d"} emissive={lit ? PALETTE.accent : "#000000"} emissiveIntensity={lit ? selected ? .75 : .25 : 0} roughness={.9} /></mesh>
    <mesh position={[0, .36, 0]} rotation={[0, Math.PI / 4, 0]} castShadow><coneGeometry args={[.28, .2, 4]} /><meshStandardMaterial color={lit ? "#637756" : "#202c26"} roughness={.95} /></mesh>
    <mesh position={[-.105, .14, .165]}><planeGeometry args={[.07, .08]} /><meshBasicMaterial color={lit ? "#f0ffaf" : "#0a100d"} /></mesh>
    <mesh position={[.105, .14, .165]}><planeGeometry args={[.07, .08]} /><meshBasicMaterial color={lit ? "#f0ffaf" : "#0a100d"} /></mesh>
  </group>;
}

function MovingCar({ offset, lane, color }: { offset: number; lane: number; color: string }) {
  const car = useRef<THREE.Group>(null);
  useFrame((clock) => {
    if (!car.current) return;
    const travel = ((clock.clock.elapsedTime * .58 + offset) % 1) * 23 - 11.5;
    car.current.position.x = lane % 2 ? travel : lane;
    car.current.position.z = lane % 2 ? lane : travel;
    car.current.rotation.y = lane % 2 ? Math.PI / 2 : 0;
  });
  return <group ref={car} position={[0, .12, 0]}>
    <mesh castShadow><boxGeometry args={[.23, .11, .46]} /><meshStandardMaterial color={color} metalness={.35} roughness={.35} emissive={color} emissiveIntensity={.12} /></mesh>
    <pointLight position={[0, .02, .25]} color="#f0ffb5" intensity={.5} distance={1.4} />
  </group>;
}

function CityLife() {
  const clouds = useRef<THREE.Group>(null);
  const birds = useRef<THREE.Group>(null);
  useFrame((clock) => {
    const t = clock.clock.elapsedTime;
    if (clouds.current) clouds.current.position.x = Math.sin(t * .035) * 2;
    if (birds.current) { birds.current.position.x = Math.sin(t * .14) * 4; birds.current.position.y = 6.8 + Math.sin(t * .7) * .16; }
  });
  return <>
    <group ref={clouds} position={[-4, 8, -8]}>{[[-2, 0, 0], [-.5, .15, .3], [1.2, -.05, -.1], [3, .2, .5]].map(([x, y, z], index) => <mesh key={index} position={[x, y, z]}><sphereGeometry args={[1.05, 12, 10]} /><meshBasicMaterial color="#789198" transparent opacity={.045} /></mesh>)}</group>
    <group ref={birds}>{[-.8, 0, .8].map((x) => <mesh key={x} position={[x, 0, x * .35]} rotation={[0, 0, -.3]}><coneGeometry args={[.06, .26, 3]} /><meshBasicMaterial color="#9eb4a5" transparent opacity={.55} /></mesh>)}</group>
    <MovingCar offset={.05} lane={-5.8} color="#75e2af" /><MovingCar offset={.48} lane={2.1} color="#ffc857" /><MovingCar offset={.72} lane={-7.25} color="#70b7ff" /><MovingCar offset={.24} lane={7.25} color="#d5e4dc" />
  </>;
}

function CivicAssets() {
  const tank = useRef<THREE.Group>(null);
  useFrame((clock) => { if (tank.current) tank.current.rotation.y = Math.sin(clock.clock.elapsedTime * .12) * .03; });
  return <>
    <group position={[7.5, 0, 4.8]}>{[0, 1, 2].map((x) => <mesh key={x} position={[x * .34, .36, 0]}><boxGeometry args={[.28, .72, .4]} /><meshStandardMaterial color="#42534d" emissive="#16422e" emissiveIntensity={.25} /></mesh>)}<mesh position={[.34, .77, 0]}><planeGeometry args={[.78, .36]} /><meshBasicMaterial color="#75e2af" transparent opacity={.75} /></mesh></group>
    <group position={[-7.8, 0, 4.65]}><mesh position={[0, .55, 0]}><boxGeometry args={[1.55, 1.1, .8]} /><meshStandardMaterial color="#c6d4c4" emissive="#75e2af" emissiveIntensity={.1} /></mesh><mesh position={[0, 1.17, 0]}><coneGeometry args={[.75, .35, 4]} /><meshStandardMaterial color="#4b6060" /></mesh><mesh position={[0, .55, .41]}><boxGeometry args={[.14, .68, .02]} /><meshBasicMaterial color="#75e2af" /></mesh></group>
    <group position={[-7.9, 0, -3.4]}><mesh position={[0, .5, 0]}><boxGeometry args={[1.9, 1, .9]} /><meshStandardMaterial color="#9aadb1" emissive="#70b7ff" emissiveIntensity={.12} /></mesh><mesh position={[0, 1.12, 0]}><boxGeometry args={[2.05, .12, 1.04]} /><meshStandardMaterial color="#47615f" /></mesh>{[-.6, 0, .6].map((x) => <mesh key={x} position={[x, .58, .46]}><planeGeometry args={[.32, .36]} /><meshBasicMaterial color="#70b7ff" transparent opacity={.8} /></mesh>)}</group>
    <group ref={tank} position={[7.4, 0, -4.2]}><mesh position={[0, 1.05, 0]}><cylinderGeometry args={[.5, .5, .76, 16]} /><meshStandardMaterial color="#8da5a1" metalness={.5} roughness={.35} /></mesh><mesh position={[0, 1.48, 0]}><sphereGeometry args={[.51, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2]} /><meshStandardMaterial color="#b7cfca" /></mesh>{[-.28, .28].flatMap((x) => [-.28, .28].map((z) => <mesh key={`${x}-${z}`} position={[x, .38, z]}><cylinderGeometry args={[.045, .045, .76, 6]} /><meshStandardMaterial color="#5d6e68" /></mesh>))}</group>
  </>;
}

function Tree({ x, z, scale = 1 }: { x: number; z: number; scale?: number }) {
  return <group position={[x, 0, z]} scale={scale}>
    <mesh position={[0, .16, 0]} castShadow><cylinderGeometry args={[.035, .05, .32, 6]} /><meshStandardMaterial color="#6b5636" roughness={1} /></mesh>
    <mesh position={[0, .44, 0]} rotation={[0, 0, (x + z) * .03]} castShadow><coneGeometry args={[.22, .38, 7]} /><meshStandardMaterial color="#244b32" emissive="#102b1b" emissiveIntensity={.3} roughness={.9} /></mesh>
  </group>;
}

function CityGround() {
  const trees = useMemo(() => Array.from({ length: 54 }, (_, index) => {
    const column = index % 9;
    const row = Math.floor(index / 9);
    return { x: -8.6 + column * 2.15 + (row % 2 ? .38 : 0), z: -4.5 + row * 2.1, scale: .65 + (index % 4) * .1 };
  }), []);
  return <>
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -.05, 0]} receiveShadow><planeGeometry args={[29, 23]} /><meshStandardMaterial color="#0a1711" roughness={1} /></mesh>
    {[-5.8, -1.85, 2.1, 6.05].map((z) => <mesh key={`road-x-${z}`} position={[0, -.025, z]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[29, .5]} /><meshBasicMaterial color="#17221e" /></mesh>)}
    {[-7.25, -2.4, 2.4, 7.25].map((x) => <mesh key={`road-z-${x}`} position={[x, -.024, 0]} rotation={[-Math.PI / 2, 0, Math.PI / 2]}><planeGeometry args={[.45, 23]} /><meshBasicMaterial color="#17221e" /></mesh>)}
    {trees.map((tree, index) => <Tree key={index} {...tree} />)}
    {[-7.25, -2.4, 2.4, 7.25].flatMap((x) => [-4.7, -2.55, -.4, 1.75, 3.9].map((z) => <group key={`${x}-${z}`} position={[x, 0, z]}><mesh position={[0, .45, 0]}><cylinderGeometry args={[.025, .035, .9, 6]} /><meshStandardMaterial color="#53635b" metalness={.6} /></mesh><mesh position={[0, .92, 0]}><sphereGeometry args={[.075, 8, 6]} /><meshBasicMaterial color="#fff2bb" /></mesh><pointLight position={[0, .92, 0]} color="#dfffa8" intensity={.35} distance={1.25} /></group>))}
  </>;
}

function Locality({ placed, intervened, onHover, onSelect, selected }: { placed: Placed; intervened: boolean; onHover: (dt: DtSnapshot | null) => void; onSelect: (id: string) => void; selected: boolean }) {
  const body = useRef<THREE.Mesh>(null);
  const ring = useRef<THREE.Mesh>(null);
  const fan = useRef<THREE.Mesh>(null);
  const servicePulse = useRef<THREE.Mesh>(null);
  const { dt, position, side } = placed;
  const state = stateOf(dt.loading_pct, dt.energized);
  const target = useMemo(() => new THREE.Color(PALETTE[state]), [state]);
  const darkRatio = Math.min(1, dt.households_dark / 70);
  const houseOffsets: [number, number][] = [[-side * .48, -.31], [-side * .78, -.06], [-side * .55, .25], [-side * .86, .37]];

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
    if (fan.current) fan.current.rotation.z = clock.clock.elapsedTime * (2 + dt.loading_pct / 18);
    if (servicePulse.current) {
      const travel = (clock.clock.elapsedTime * .15 + position[2] * .05) % 1;
      servicePulse.current.position.x = -side * (1.12 - travel * 1.08);
      (servicePulse.current.material as THREE.MeshBasicMaterial).opacity = dt.energized ? Math.sin(travel * Math.PI) * .9 : 0;
    }
  });

  return <group position={position} onPointerOver={(event) => { event.stopPropagation(); onHover(dt); document.body.style.cursor = "pointer"; }} onPointerOut={() => { onHover(null); document.body.style.cursor = "auto"; }} onClick={(event) => { event.stopPropagation(); onSelect(dt.id); }}>
    <mesh position={[0, .05, 0]}><cylinderGeometry args={[.34, .42, .1, 8]} /><meshStandardMaterial color="#203029" roughness={.8} /></mesh>
    <mesh ref={body} position={[0, .38, 0]} castShadow><boxGeometry args={[.34, .62, .34]} /><meshStandardMaterial color={PALETTE[state]} emissive={PALETTE[state]} emissiveIntensity={.4} metalness={.35} roughness={.3} /></mesh>
    <mesh position={[0, .75, 0]}><cylinderGeometry args={[.045, .045, .35, 8]} /><meshStandardMaterial color="#73847b" metalness={.6} /></mesh>
    <mesh ref={fan} position={[.18, .39, .18]} rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[.11, .025, 6, 12]} /><meshStandardMaterial color="#9fb2a7" metalness={.7} /></mesh>
    <mesh ref={ring} position={[0, .035, 0]} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[.43, .58, 28]} /><meshBasicMaterial transparent opacity={0} side={THREE.DoubleSide} /></mesh>
    <mesh position={[-side * .56, .055, 0]} rotation={[-Math.PI / 2, 0, Math.PI / 2]}><planeGeometry args={[.035, 1.12]} /><meshBasicMaterial color={PALETTE[state]} transparent opacity={dt.energized ? .5 : .14} /></mesh>
    <mesh ref={servicePulse} position={[-side * 1.1, .064, 0]} rotation={[-Math.PI / 2, 0, Math.PI / 2]}><planeGeometry args={[.09, .2]} /><meshBasicMaterial color={PALETTE.accent} transparent opacity={0} /></mesh>
    {houseOffsets.map(([offsetX, offsetZ], index) => <group key={index}><mesh position={[offsetX / 2, .05, offsetZ / 2]} rotation={[-Math.PI / 2, Math.atan2(offsetX, offsetZ), 0]}><planeGeometry args={[.018, Math.hypot(offsetX, offsetZ)]} /><meshBasicMaterial color={dt.energized ? "#7cab79" : "#293b32"} transparent opacity={.5} /></mesh><House x={offsetX} z={offsetZ} lit={dt.energized && index / 4 >= darkRatio} selected={selected} /></group>)}
    {selected && <Html center position={[0, 1.2, 0]} distanceFactor={13}><div className="twin-selected-tag"><span>{dt.id}</span><strong>{dt.loading_pct.toFixed(0)}%</strong></div></Html>}
  </group>;
}

function Feeder({ x, loading, id }: { x: number; loading: number; id: string }) {
  const flow = useRef<THREE.Mesh>(null);
  const state = stateOf(loading, true);
  useFrame((clock) => {
    if (!flow.current) return;
    const t = (clock.clock.elapsedTime * (.045 + loading / 950)) % 1;
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

function CameraRig({ sceneIndex }: { sceneIndex: number }) {
  const { camera, mouse } = useThree();
  const target = useRef(new THREE.Vector3());
  const paths: [number, number, number][] = [[1.2, 10.8, 14.4], [-3.9, 9.4, 13.6], [4.6, 9.2, 13.4], [2.8, 8.1, 11.8], [-3.5, 8.2, 12.2], [.8, 10.5, 14.2], [3.5, 8.8, 12.8], [1.2, 11.2, 15]];
  useFrame((clock, delta) => {
    const p = paths[sceneIndex % paths.length];
    const breath = Math.sin(clock.clock.elapsedTime * .32) * .08;
    const desired = new THREE.Vector3(p[0] + mouse.x * .35, p[1] + breath + mouse.y * .2, p[2]);
    camera.position.lerp(desired, 1 - Math.exp(-delta * 1.1));
    target.current.lerp(new THREE.Vector3(-1.65, .22, sceneIndex === 3 ? .9 : 0), 1 - Math.exp(-delta * 1.3));
    camera.lookAt(target.current);
  });
  return null;
}

function Scene({ snapshot, activeTargets, selectedDt, onSelect, onHover, reduced, presentation, sceneIndex }: { snapshot: ArmSnapshot; activeTargets: Set<string>; selectedDt: string; onSelect: (id: string) => void; onHover: (dt: DtSnapshot | null) => void; reduced: boolean; presentation: boolean; sceneIndex: number }) {
  const placed = useMemo(() => layout(snapshot.dts), [snapshot.dts]);
  const presentationPlaced = presentation ? placed.filter((_, index) => index % 4 === 0) : placed;
  return <>
    <fog attach="fog" args={[sceneIndex === 3 ? "#4f493e" : "#334039", 17, 42]} />
    <ambientLight intensity={.82} />
    <hemisphereLight args={["#c8d5cf", "#102b1d", .72]} />
    <directionalLight position={[5, 13, 7]} intensity={1.45} />
    <pointLight position={[0, 5, -6]} intensity={30} color={PALETTE.accent} distance={18} />
    <Substation />
    <CriticalFacility uptime={snapshot.metrics.critical_uptime_pct} />
    <CivicAssets />
    <CityLife />
    {FEEDER_X.map((x, index) => <Feeder key={x} x={x} loading={snapshot.feeders[index]?.loading_pct ?? 0} id={snapshot.feeders[index]?.id ?? `F${index + 1}`} />)}
    {presentationPlaced.map((item) => <Locality key={item.dt.id} placed={item} intervened={activeTargets.has(item.dt.id)} selected={selectedDt === item.dt.id} onSelect={onSelect} onHover={onHover} />)}
    <CityGround />
    <gridHelper args={[29, 29, "#183127", "#102019"]} position={[0, -.02, 0]} />
    {presentation && <CameraRig sceneIndex={sceneIndex} />}
    {!presentation && <OrbitControls enablePan={false} enableDamping dampingFactor={.06} minDistance={8} maxDistance={24} minPolarAngle={.25} maxPolarAngle={Math.PI / 2.18} autoRotate={!reduced} autoRotateSpeed={.07} />}
  </>;
}

export function Network3D({ snapshot, label, selectedDt, onSelect, activeTargets = new Set<string>(), presentation = false, sceneIndex = 0 }: { snapshot: ArmSnapshot; label: string; selectedDt: string; onSelect: (id: string) => void; activeTargets?: Set<string>; presentation?: boolean; sceneIndex?: number }) {
  const [hovered, setHovered] = useState<DtSnapshot | null>(null);
  const reduced = Boolean(useReducedMotion());
  const selected = snapshot.dts.find((dt) => dt.id === selectedDt);
  const inspected = hovered ?? selected;
  return <div className={`twin-stage ${presentation ? "presentation" : ""}`}>
    <Canvas camera={{ position: [1.2, 10.8, 14.4], fov: 39 }} dpr={[1, 1.2]} gl={{ alpha: true, antialias: true, powerPreference: "high-performance" }}>
      <Scene snapshot={snapshot} activeTargets={activeTargets} selectedDt={selectedDt} onSelect={onSelect} onHover={setHovered} reduced={reduced} presentation={presentation} sceneIndex={sceneIndex} />
    </Canvas>
    <div className="twin-readout">{inspected ? <><span>{inspected.energized ? "LOCALITY ENERGISED" : "LOCALITY OFFLINE"}</span><strong>{inspected.id}</strong><small>{inspected.loading_pct.toFixed(1)}% of limit · {inspected.households_dark} homes dark</small></> : <><span>SPATIAL NETWORK</span><strong>{label}</strong><small>Select a locality to inspect its transformer and homes.</small></>}</div>
    <div className="twin-key">{(["stable", "strained", "overloaded", "offline"] as const).map((state) => <span key={state}><i style={{ background: PALETTE[state] }} />{state}</span>)}</div>
    {!presentation && <div className="twin-help">DRAG TO ORBIT · SCROLL TO ZOOM · SELECT A LOCALITY</div>}
  </div>;
}
