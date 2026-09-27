import React, { useRef, useEffect, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Stars } from "@react-three/drei";

function GalaxyInner() {
  const group = useRef();
  const mouse = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const handle = (e) => {
      mouse.current.x = (e.clientX / window.innerWidth) * 2 - 1;
      mouse.current.y = -((e.clientY / window.innerHeight) * 2 - 1);
    };
    window.addEventListener("mousemove", handle);
    return () => window.removeEventListener("mousemove", handle);
  }, []);

  useFrame(({ clock }) => {
    if (!group.current) return;
    const t = clock.elapsedTime;
    const targetY = t * 0.02 + mouse.current.x * 0.4;
    const targetX = mouse.current.y * 0.3 + Math.sin(t * 0.15) * 0.05;
    group.current.rotation.y += (targetY - group.current.rotation.y) * 0.05;
    group.current.rotation.x += (targetX - group.current.rotation.x) * 0.05;
  });

  return (
    <group ref={group}>
      <Stars radius={60} depth={50} count={4000} factor={4} saturation={0} fade speed={0.6} />
      <Stars radius={100} depth={70} count={1500} factor={6} saturation={0} fade speed={0.3} />
    </group>
  );
}

export default function HeroGalaxy() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  return (
    <div className="hero-galaxy" aria-hidden="true">
      <Canvas camera={{ position: [0, 0, 1] }} gl={{ antialias: true, alpha: true }} dpr={[1, 1.5]}>
        <ambientLight intensity={0.6} />
        <GalaxyInner />
      </Canvas>
    </div>
  );
}