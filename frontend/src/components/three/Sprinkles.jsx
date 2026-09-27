import React, { useRef, useEffect, useCallback } from "react";

/**
 * Interactive white sprinkles background.
 * Tiny white dots that drift and repel smoothly near the mouse cursor.
 * Pure canvas 2D — lightweight, no extra deps.
 */
export default function Sprinkles({
  count = 90,
  radius = 150,
}) {
  const canvasRef = useRef(null);
  const particlesRef = useRef([]);
  const mouseRef = useRef({ x: -9999, y: -9999 });
  const rafRef = useRef(null);

  const initParticles = useCallback(
    (w, h) => {
      const arr = [];
      for (let i = 0; i < count; i++) {
        arr.push({
          x: Math.random() * w,
          y: Math.random() * h,
          r: Math.random() * 1.4 + 0.4,
          vx: (Math.random() - 0.5) * 0.25,
          vy: (Math.random() - 0.5) * 0.25,
          ox: 0,
          oy: 0,
          twinkle: Math.random() * Math.PI * 2,
          twinkleSpeed: 0.015 + Math.random() * 0.03,
        });
      }
      particlesRef.current = arr;
    },
    [count]
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    const bg = canvas.parentElement;       // .validation-bg
    const host = bg ? bg.parentElement : canvas.parentElement; // .validation-section

    const resize = () => {
      const rect = host.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      canvas.style.width = rect.width + "px";
      canvas.style.height = rect.height + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      if (particlesRef.current.length === 0) {
        initParticles(rect.width, rect.height);
      } else {
        particlesRef.current.forEach((p) => {
          if (p.x > rect.width) p.x = Math.random() * rect.width;
          if (p.y > rect.height) p.y = Math.random() * rect.height;
        });
      }
    };

    const handleMouseMove = (e) => {
      const rect = host.getBoundingClientRect();
      mouseRef.current.x = e.clientX - rect.left;
      mouseRef.current.y = e.clientY - rect.top;
    };

    const handleMouseLeave = () => {
      mouseRef.current.x = -9999;
      mouseRef.current.y = -9999;
    };

    const draw = () => {
      const rect = host.getBoundingClientRect();
      const w = rect.width;
      const h = rect.height;

      ctx.clearRect(0, 0, w, h);

      const mx = mouseRef.current.x;
      const my = mouseRef.current.y;

      const particles = particlesRef.current;

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];

        p.x += p.vx;
        p.y += p.vy;

        if (p.x < -10) p.x = w + 10;
        if (p.x > w + 10) p.x = -10;
        if (p.y < -10) p.y = h + 10;
        if (p.y > h + 10) p.y = -10;

        const dx = p.x - mx;
        const dy = p.y - my;
        const distSq = dx * dx + dy * dy;
        const dist = Math.sqrt(distSq) || 0.0001;

        if (dist < radius) {
          const force = (radius - dist) / radius;
          const angle = Math.atan2(dy, dx);
          const push = force * 22;
          p.ox += Math.cos(angle) * push * 0.15;
          p.oy += Math.sin(angle) * push * 0.15;
        }

        p.ox *= 0.9;
        p.oy *= 0.9;

        p.twinkle += p.twinkleSpeed;
        const alpha = 0.35 + Math.abs(Math.sin(p.twinkle)) * 0.65;

        const px = p.x + p.ox;
        const py = p.y + p.oy;

        // soft halo
        ctx.beginPath();
        ctx.fillStyle = `rgba(255,255,255,${alpha * 0.08})`;
        ctx.arc(px, py, p.r * 6, 0, Math.PI * 2);
        ctx.fill();

        // core dot
        ctx.beginPath();
        ctx.fillStyle = `rgba(255,255,255,${alpha})`;
        ctx.arc(px, py, p.r, 0, Math.PI * 2);
        ctx.fill();
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    resize();
    window.addEventListener("resize", resize);
    host.addEventListener("mousemove", handleMouseMove);
    host.addEventListener("mouseleave", handleMouseLeave);

    rafRef.current = requestAnimationFrame(draw);

    return () => {
      window.removeEventListener("resize", resize);
      host.removeEventListener("mousemove", handleMouseMove);
      host.removeEventListener("mouseleave", handleMouseLeave);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [initParticles, radius]);

  return <canvas ref={canvasRef} className="sprinkle-canvas" aria-hidden="true" />;
}