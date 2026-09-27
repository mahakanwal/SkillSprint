import React, { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Points, PointMaterial } from "@react-three/drei";
import * as THREE from "three";

export default function HeroObject() {
  const group = useRef();
  const knotRef = useRef();
  const innerRef = useRef();

  // orbiting particle cloud
  const points = useMemo(() => {
    const arr = [];
    for (let i = 0; i < 400; i++) {
      const r = 2.4 + Math.random() * 1.8;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      arr.push(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.cos(phi),
        r * Math.sin(phi) * Math.sin(theta)
      );
    }
    return new Float32Array(arr);
  }, []);

  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    if (group.current) {
      group.current.rotation.y = t * 0.15;
      group.current.rotation.x = Math.sin(t * 0.25) * 0.15;
    }
    if (knotRef.current) {
      knotRef.current.rotation.z = t * 0.2;
    }
    if (innerRef.current) {
      const s = 1 + Math.sin(t * 1.2) * 0.08;
      innerRef.current.scale.setScalar(s);
    }
  });

  return (
    <group ref={group}>

      {/* OUTER WIREFRAME KNOT — main hero object */}
      <mesh ref={knotRef}>
        <torusKnotGeometry args={[1.05, 0.32, 220, 32, 2, 3]} />
        <meshStandardMaterial
          color="#0a1a1e"
          emissive="#2dd4c5"
          emissiveIntensity={1.6}
          wireframe
          transparent
          opacity={0.9}
        />
      </mesh>

      {/* INNER GLOWING KNOT — solid, softer */}
      <mesh ref={innerRef}>
        <torusKnotGeometry args={[1.05, 0.28, 180, 24, 2, 3]} />
        <meshStandardMaterial
          color="#2dd4c5"
          emissive="#2dd4c5"
          emissiveIntensity={2.4}
          transparent
          opacity={0.35}
        />
      </mesh>

      {/* CORE SPHERE */}
      <mesh>
        <sphereGeometry args={[0.32, 32, 32]} />
        <meshStandardMaterial
          color="#ffffff"
          emissive="#2dd4c5"
          emissiveIntensity={3}
        />
      </mesh>

      {/* ORBITING PARTICLE CLOUD */}
      <Points positions={points} stride={3} frustumCulled={false}>
        <PointMaterial
          transparent
          color="#2dd4c5"
          size={0.025}
          sizeAttenuation
          depthWrite={false}
          opacity={0.9}
        />
      </Points>

      {/* faint white dust around */}
      <Points positions={points} stride={3} frustumCulled={false}>
        <PointMaterial
          transparent
          color="#ffffff"
          size={0.008}
          sizeAttenuation
          depthWrite={false}
          opacity={0.35}
        />
      </Points>

    </group>
  );
}