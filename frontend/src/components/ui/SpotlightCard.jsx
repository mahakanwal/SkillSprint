import React, { useRef } from 'react';

/* ==========================================================================
   SpotlightCard — adapted from React Bits (reactbits.dev, "SpotlightCard",
   MIT + Commons Clause, David Haz).

   Changes from the original: the pointer position is written to CSS custom
   properties instead of React state, so moving the mouse never re-renders
   the card's children; the glow is toned down for a calm dashboard; and it
   renders as any element (`as`) so it can be a real <button> when the card
   is interactive (keyboard + screen-reader friendly).
   ========================================================================== */
export const SpotlightCard = ({
  as: Tag = 'div',
  className = '',
  spotlightColor = 'rgba(108, 201, 180, 0.10)',
  children,
  ...rest
}) => {
  const ref = useRef(null);

  const handleMove = (e) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    el.style.setProperty('--spot-x', `${e.clientX - rect.left}px`);
    el.style.setProperty('--spot-y', `${e.clientY - rect.top}px`);
  };

  return (
    <Tag
      ref={ref}
      onMouseMove={handleMove}
      className={`group relative overflow-hidden ${className}`}
      {...rest}
    >
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100 group-focus-visible:opacity-100"
        style={{
          background: `radial-gradient(420px circle at var(--spot-x, 50%) var(--spot-y, 0%), ${spotlightColor}, transparent 70%)`,
        }}
      />
      {children}
    </Tag>
  );
};

export default SpotlightCard;
