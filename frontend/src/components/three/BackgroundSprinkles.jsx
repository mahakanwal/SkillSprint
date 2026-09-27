import React, { useRef, useEffect } from "react";

/**
 * Full-page fixed background sprinkles.
 * Tiny white dots that drift and twinkle across the whole landing page.
 */
export default function BackgroundSprinkles({ count = 140 }) {
  const canvasRef = useRef(null);
  const particlesRef = useRef([]);
  const rafRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;

    const resize = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      if (particlesRef.current.length === 0) {
        const arr = [];
        for (let i = 0; i < count; i++) {
          arr.push({
            x: Math.random() * w,
            y: Math.random() * h,
            r: Math.random() * 1.3 + 0.3,
            vx: (Math.random() - 0.5) * 0.18,
            vy: (Math.random() - 0.5) * 0.18,
            twinkle: Math.random() * Math.PI * 2,
            twinkleSpeed: 0.01 + Math.random() * 0.025,
          });
        }
        particlesRef.current = arr;
      }
    };

    const draw = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      ctx.clearRect(0, 0, w, h);

      const particles = particlesRef.current;

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < -10) p.x = w + 10;
        if (p.x > w + 10) p.x = -10;
        if (p.y < -10) p.y = h + 10;
        if (p.y > h + 10) p.y = -10;

        p.twinkle += p.twinkleSpeed;
        const alpha = 0.2 + Math.abs(Math.sin(p.twinkle)) * 0.6;

        // halo
        ctx.beginPath();
        ctx.fillStyle = `rgba(255,255,255,${alpha * 0.06})`;
        ctx.arc(p.x, p.y, p.r * 6, 0, Math.PI * 2);
        ctx.fill();

        // core
        ctx.beginPath();
        ctx.fillStyle = `rgba(255,255,255,${alpha})`;
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    resize();
    window.addEventListener("resize", resize);
    rafRef.current = requestAnimationFrame(draw);

    return () => {
      window.removeEventListener("resize", resize);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [count]);

  return <canvas ref={canvasRef} className="bg-sprinkles" aria-hidden="true" />;
}