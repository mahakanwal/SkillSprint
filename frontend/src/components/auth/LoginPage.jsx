import React, { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ArrowRight, Cpu, Eye, EyeOff, LoaderCircle, Lock, Mail, ShieldCheck, Sparkles,
} from 'lucide-react';
import { ease } from '../ui/primitives';
import { useAuth } from '../../context/AuthContext';
import apiClient from '../../api/apiClient';

/*
 * Install once in your frontend folder: npm install three
 * Replace the existing LoginPage.jsx with this file, keeping its current path.
 * Styles are scoped to this page; no global CSS file or backend changes needed.
 * The 3D scene is procedural: no model files, CDN scripts, or remote textures.
 */

const LOGIN_FALLBACK = 'Login failed. Check your email/password and that the backend is running.';

function getErrorMessage(error, fallback) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => (
      typeof item === 'string' ? item : item?.msg
    )).filter((message) => typeof message === 'string' && message.trim());
    if (messages.length) return messages.join(' ');
  }
  return fallback;
}

function useMotionPreference() {
  const [reducedMotion, setReducedMotion] = useState(() => (
    typeof window === 'undefined' || window.matchMedia('(prefers-reduced-motion: reduce)').matches
  ));
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  return reducedMotion;
}

/** Decorative WebGL scene. Any rendering failure leaves the CSS globe visible. */
function IntelligenceGlobe({ reducedMotion }) {
  const hostRef = useRef(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;

    let cancelled = false;
    let dispose = () => {};
    setReady(false);

    async function initialize() {
      try {
        // A separate chunk keeps the sign-in form independent of the 3D download.
        const THREE = await import('three');
        if (cancelled) return;

        const resources = new Set();
        const own = (resource) => { resources.add(resource); return resource; };
        const scene = new THREE.Scene();
        const camera = new THREE.OrthographicCamera(-3, 3, 2.6, -2.6, 0.1, 40);
        camera.position.z = 8;
        let renderer;
        let frameId = 0;
        let resizeObserver;
        let intersectionObserver;
        let disposed = false;
        let inView = true;
        let elapsed = 0;
        let lastTime = 0;
        let lastPaint = 0;
        const removeListeners = [];

        const listen = (target, event, handler, options) => {
          target.addEventListener(event, handler, options);
          removeListeners.push(() => target.removeEventListener(event, handler, options));
        };

        dispose = () => {
          if (disposed) return;
          disposed = true;
          cancelAnimationFrame(frameId);
          resizeObserver?.disconnect();
          intersectionObserver?.disconnect();
          removeListeners.forEach((remove) => remove());
          resources.forEach((resource) => resource.dispose());
          resources.clear();
          scene.clear();
          if (renderer) {
            renderer.dispose();
            renderer.forceContextLoss();
            renderer.domElement.remove();
          }
        };

        renderer = new THREE.WebGLRenderer({
          alpha: true, antialias: true, powerPreference: 'low-power',
        });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
        renderer.setClearColor(0x000000, 0);
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.domElement.setAttribute('aria-hidden', 'true');
        host.appendChild(renderer.domElement);

        const fail = () => {
          if (!cancelled) setReady(false);
          dispose();
        };
        listen(renderer.domElement, 'webglcontextlost', (event) => {
          event.preventDefault();
          fail();
        });

        scene.add(new THREE.AmbientLight(0x76bfc5, 0.65));
        const key = new THREE.DirectionalLight(0x92fff2, 1.5);
        key.position.set(-3, 4, 5);
        scene.add(key);
        const rim = new THREE.DirectionalLight(0x3795de, 1.25);
        rim.position.set(4, -1, 2);
        scene.add(rim);

        const atom = new THREE.Group();
        const globe = new THREE.Group();
        atom.add(globe);
        scene.add(atom);

        const globeGeometry = own(new THREE.IcosahedronGeometry(1.28, 3));
        globe.add(new THREE.Mesh(globeGeometry, own(new THREE.MeshPhongMaterial({
          color: 0x075b65, specular: 0x244f52, shininess: 55, flatShading: true,
        }))));

        const wire = new THREE.LineSegments(
          own(new THREE.WireframeGeometry(globeGeometry)),
          own(new THREE.LineBasicMaterial({
            color: 0x72d5d8, transparent: true, opacity: 0.075,
          })),
        );
        wire.scale.setScalar(1.003);
        globe.add(wire);

        // Small six-spoke surface marks reproduce the reference's tech texture.
        const marks = [];
        const goldenAngle = Math.PI * (3 - Math.sqrt(5));
        for (let i = 0; i < 105; i += 1) {
          const y = 1 - (i / 104) * 2;
          const radius = Math.sqrt(Math.max(0, 1 - y * y));
          const normal = new THREE.Vector3(
            Math.cos(i * goldenAngle) * radius, y, Math.sin(i * goldenAngle) * radius,
          );
          const center = normal.clone().multiplyScalar(1.289);
          const reference = Math.abs(y) > 0.95
            ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 1, 0);
          const tangent = new THREE.Vector3().crossVectors(normal, reference).normalize();
          const bitangent = new THREE.Vector3().crossVectors(normal, tangent).normalize();
          for (let spoke = 0; spoke < 3; spoke += 1) {
            const angle = spoke * Math.PI / 3;
            const direction = tangent.clone().multiplyScalar(Math.cos(angle))
              .addScaledVector(bitangent, Math.sin(angle)).multiplyScalar(0.058);
            marks.push(...center.clone().sub(direction).toArray());
            marks.push(...center.clone().add(direction).toArray());
          }
        }
        const marksGeometry = own(new THREE.BufferGeometry());
        marksGeometry.setAttribute('position', new THREE.Float32BufferAttribute(marks, 3));
        globe.add(new THREE.LineSegments(marksGeometry, own(new THREE.LineBasicMaterial({
          color: 0x8bdce0, transparent: true, opacity: 0.25,
        }))));

        const beadGeometry = own(new THREE.SphereGeometry(0.035, 12, 8));
        const beadMaterial = own(new THREE.MeshBasicMaterial({ color: 0xc9fff2 }));
        const orbitDefinitions = [
          { radius: 1.86, rotation: [1.08, 0, 0.34], color: 0xb4e2df, speed: 0.19 },
          { radius: 1.97, rotation: [0.72, 0, -1.02], color: 0x8aaebf, speed: -0.14 },
          { radius: 1.77, rotation: [1.15, 0, 1.28], color: 0xb3b9cf, speed: 0.23 },
        ];
        const orbits = orbitDefinitions.map((definition, index) => {
          const group = new THREE.Group();
          group.rotation.set(...definition.rotation, 'ZXY');
          group.add(new THREE.Mesh(
            own(new THREE.TorusGeometry(definition.radius, index === 0 ? 0.01 : 0.008, 6, 160)),
            own(new THREE.MeshBasicMaterial({
              color: definition.color, transparent: true, opacity: index === 0 ? 0.9 : 0.74,
            })),
          ));
          const bead = new THREE.Mesh(beadGeometry, beadMaterial);
          group.add(bead);
          atom.add(group);
          return { ...definition, group, bead, phase: index * 2.15 };
        });

        // Seeded positions avoid changes on every React render or remount.
        let seed = 37;
        const random = () => {
          seed = (seed * 16807) % 2147483647;
          return (seed - 1) / 2147483646;
        };
        const dust = [];
        for (let i = 0; i < 140; i += 1) {
          dust.push((random() - 0.5) * 7.4, (random() - 0.5) * 5.5, -1.8 - random() * 3);
        }
        const dustGeometry = own(new THREE.BufferGeometry());
        dustGeometry.setAttribute('position', new THREE.Float32BufferAttribute(dust, 3));
        scene.add(new THREE.Points(dustGeometry, own(new THREE.PointsMaterial({
          color: 0x66b9c3, size: 0.012, transparent: true, opacity: 0.4,
        }))));

        const pointer = { x: 0, y: 0 };
        if (!reducedMotion && window.matchMedia('(pointer: fine)').matches) {
          listen(host, 'pointermove', (event) => {
            const rect = host.getBoundingClientRect();
            pointer.x = ((event.clientX - rect.left) / rect.width - 0.5) * 0.22;
            pointer.y = ((event.clientY - rect.top) / rect.height - 0.5) * 0.16;
          }, { passive: true });
          listen(host, 'pointerleave', () => { pointer.x = 0; pointer.y = 0; });
        }

        function paint() {
          if (disposed) return;
          globe.rotation.y = elapsed * 0.075;
          globe.rotation.z = 0.09;
          atom.position.y = reducedMotion ? 0 : Math.sin(elapsed * 0.5) * 0.045;
          atom.rotation.y += (pointer.x - atom.rotation.y) * 0.045;
          atom.rotation.x += (pointer.y - atom.rotation.x) * 0.045;
          orbits.forEach(({ bead, radius, phase, speed }) => {
            const angle = phase + elapsed * speed;
            bead.position.set(Math.cos(angle) * radius, Math.sin(angle) * radius, 0);
          });
          try { renderer.render(scene, camera); } catch { fail(); }
        }

        function tick(now) {
          frameId = 0;
          if (disposed || document.hidden || !inView || reducedMotion) return;
          elapsed += lastTime ? Math.min((now - lastTime) / 1000, 0.08) : 0;
          lastTime = now;
          // 30 FPS is enough for the slow decorative motion.
          if (now - lastPaint >= 1000 / 30) { paint(); lastPaint = now; }
          if (!disposed) frameId = requestAnimationFrame(tick);
        }

        function syncAnimation() {
          cancelAnimationFrame(frameId);
          frameId = 0;
          lastTime = 0;
          if (!disposed && !document.hidden && inView && !reducedMotion) {
            frameId = requestAnimationFrame(tick);
          }
        }

        function resize() {
          if (disposed) return;
          const width = Math.max(host.clientWidth, 1);
          const height = Math.max(host.clientHeight, 1);
          const aspect = width / height;
          const halfHeight = Math.max(2.55, 2.35 / aspect);
          camera.left = -halfHeight * aspect;
          camera.right = halfHeight * aspect;
          camera.top = halfHeight;
          camera.bottom = -halfHeight;
          camera.updateProjectionMatrix();
          renderer.setSize(width, height, false);
          paint();
        }

        if (typeof ResizeObserver !== 'undefined') {
          resizeObserver = new ResizeObserver(resize);
          resizeObserver.observe(host);
        } else {
          listen(window, 'resize', resize);
        }
        if (typeof IntersectionObserver !== 'undefined') {
          intersectionObserver = new IntersectionObserver(([entry]) => {
            inView = entry.isIntersecting;
            syncAnimation();
          });
          intersectionObserver.observe(host);
        }
        listen(document, 'visibilitychange', syncAnimation);
        resize();
        if (!disposed) { setReady(true); syncAnimation(); }
      } catch {
        // Decorative errors must never block authentication.
        if (!cancelled) setReady(false);
        dispose();
      }
    }

    initialize();
    return () => { cancelled = true; dispose(); };
  }, [reducedMotion]);

  return (
    <div className={`ss-globe${ready ? ' ss-globe--ready' : ''}`} aria-hidden="true">
      <div className="ss-globe-glow" />
      <div className="ss-globe-fallback">
        <span className="ss-fallback-sphere" />
        <span className="ss-fallback-ring ss-fallback-ring--one" />
        <span className="ss-fallback-ring ss-fallback-ring--two" />
        <span className="ss-fallback-ring ss-fallback-ring--three" />
      </div>
      <div className="ss-globe-canvas" ref={hostRef} />
    </div>
  );
}

export const LoginPage = () => {
  const { login } = useAuth();
  const reducedMotion = useMotionPreference();
  const requestInFlight = useRef(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showBootstrap, setShowBootstrap] = useState(false);
  const [bootstrapEmail, setBootstrapEmail] = useState('');
  const [bootstrapPassword, setBootstrapPassword] = useState('');
  const [isBootstrapping, setIsBootstrapping] = useState(false);
  const [bootstrapError, setBootstrapError] = useState(null);
  const [notice, setNotice] = useState(null);
  const busy = isLoading || isBootstrapping;

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (requestInFlight.current) return;
    requestInFlight.current = true;
    setError(null);
    setIsLoading(true);
    try {
      // Same AuthContext flow: token storage and navigation stay in your context.
      await login(email, password);
    } catch (err) {
      setError(getErrorMessage(err, LOGIN_FALLBACK));
    } finally {
      requestInFlight.current = false;
      setIsLoading(false);
    }
  };

  const handleBootstrap = async (event) => {
    event.preventDefault();
    if (requestInFlight.current) return;
    requestInFlight.current = true;
    setBootstrapError(null);
    setError(null);
    setNotice(null);
    setIsBootstrapping(true);
    let accountCreated = false;
    try {
      // Same endpoint and payload. The backend enforces one-time availability.
      await apiClient.post('/auth/bootstrap-first-admin', {
        email: bootstrapEmail,
        password: bootstrapPassword,
      });
      accountCreated = true;
      await login(bootstrapEmail, bootstrapPassword);
    } catch (err) {
      if (accountCreated) {
        // If only automatic login fails, retry sign-in, not account creation.
        setEmail(bootstrapEmail);
        setPassword('');
        setBootstrapPassword('');
        setShowBootstrap(false);
        setNotice('Admin account created. Enter your password below to sign in.');
        setError(getErrorMessage(err, 'Automatic sign-in failed. Please sign in below.'));
      } else {
        setBootstrapError(getErrorMessage(err, 'Could not create the first admin account.'));
      }
    } finally {
      requestInFlight.current = false;
      setIsBootstrapping(false);
    }
  };

  return (
    <main className="ss-login">
      <style>{styles}</style>
      <section className="ss-auth-side" aria-labelledby="ss-login-title">
        <div className="ss-brand">
          <span className="ss-brand-icon"><Cpu size={20} aria-hidden="true" /></span>
          <span>SkillSprint <span className="ss-accent">AI</span></span>
        </div>

        <motion.div
          className="ss-auth-content"
          initial={reducedMotion ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease }}
        >
          <header className="ss-intro">
            <p className="ss-eyebrow"><span className="ss-status-dot" />Your workspace awaits</p>
            <h1 id="ss-login-title">Welcome back<span className="ss-accent">.</span></h1>
            <p className="ss-intro-description">Sign in to continue your learning journey with SkillSprint AI.</p>
          </header>

          <div className="ss-auth-card">
            <div className="ss-card-heading">
              <span className="ss-card-icon"><ShieldCheck size={20} aria-hidden="true" /></span>
              <div><h2>Sign in to your account</h2><p>Enter your details below to get started</p></div>
            </div>

            {notice && <p className="ss-notice" role="status">{notice}</p>}
            {error && <p className="ss-error" id="ss-login-error" role="alert">{error}</p>}

            <form onSubmit={handleSubmit} aria-busy={isLoading} aria-describedby={error ? 'ss-login-error' : undefined}>
              <div className="ss-field">
                <label htmlFor="login-email">Email address</label>
                <div className="ss-input-wrap">
                  <Mail size={17} aria-hidden="true" className="ss-input-icon" />
                  <input
                    id="login-email" name="email" type="email" required autoComplete="email"
                    autoCapitalize="none" spellCheck={false} disabled={busy}
                    value={email} onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@company.com"
                  />
                </div>
              </div>

              <div className="ss-field">
                <label htmlFor="login-password">Password</label>
                <div className="ss-input-wrap ss-input-wrap--password">
                  <Lock size={17} aria-hidden="true" className="ss-input-icon" />
                  <input
                    id="login-password" name="password" type={showPassword ? 'text' : 'password'}
                    required autoComplete="current-password" disabled={busy}
                    value={password} onChange={(event) => setPassword(event.target.value)}
                    placeholder="Enter your password"
                  />
                  <button
                    className="ss-password-toggle" type="button" disabled={busy}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    aria-controls="login-password" aria-pressed={showPassword}
                    onClick={() => setShowPassword((visible) => !visible)}
                  >
                    {showPassword ? <EyeOff size={17} aria-hidden="true" /> : <Eye size={17} aria-hidden="true" />}
                  </button>
                </div>
              </div>

              <button type="submit" className="ss-submit" disabled={busy}>
                <span>{isLoading ? 'Signing in…' : 'Sign in'}</span>
                {isLoading ? <LoaderCircle size={17} className="ss-spinner" aria-hidden="true" /> : <ArrowRight size={17} aria-hidden="true" />}
              </button>
            </form>

            <p className="ss-account-help">No account? Your admin creates it and shares a temporary password with you.</p>
          </div>

          <div className="ss-bootstrap">
            <button
              type="button" className="ss-bootstrap-toggle" disabled={busy}
              onClick={() => setShowBootstrap((visible) => !visible)}
              aria-expanded={showBootstrap} aria-controls="ss-bootstrap-panel"
            >
              <ShieldCheck size={15} aria-hidden="true" />
              <span>New install? Set up the first admin account</span>
            </button>
            <AnimatePresence initial={false}>
              {showBootstrap && (
                <motion.div
                  id="ss-bootstrap-panel" className="ss-bootstrap-panel"
                  initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: reducedMotion ? 0 : 0.22, ease }}
                >
                  <form onSubmit={handleBootstrap} className="ss-bootstrap-form" aria-busy={isBootstrapping}>
                    <p className="ss-bootstrap-info">First-time setup only. This works before any account exists. If your organization already has an account, ask your admin for access.</p>
                    {bootstrapError && <p className="ss-error" role="alert">{bootstrapError}</p>}
                    <div className="ss-field">
                      <label htmlFor="boot-email">Admin email</label>
                      <div className="ss-input-wrap">
                        <Mail size={17} className="ss-input-icon" aria-hidden="true" />
                        <input
                          id="boot-email" name="admin-email" type="email" required autoComplete="email"
                          autoCapitalize="none" spellCheck={false} disabled={busy} placeholder="admin@company.com"
                          value={bootstrapEmail} onChange={(event) => setBootstrapEmail(event.target.value)}
                        />
                      </div>
                    </div>
                    <div className="ss-field">
                      <label htmlFor="boot-password">Password</label>
                      <div className="ss-input-wrap">
                        <Lock size={17} className="ss-input-icon" aria-hidden="true" />
                        <input
                          id="boot-password" name="admin-password" type="password" required minLength={6}
                          autoComplete="new-password" disabled={busy} placeholder="Choose a strong password"
                          value={bootstrapPassword} onChange={(event) => setBootstrapPassword(event.target.value)}
                        />
                      </div>
                    </div>
                    <button type="submit" className="ss-submit ss-submit--secondary" disabled={busy}>
                      {isBootstrapping && <LoaderCircle size={17} className="ss-spinner" aria-hidden="true" />}
                      <span>{isBootstrapping ? 'Creating…' : 'Create first admin account'}</span>
                    </button>
                  </form>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      </section>

      <aside className="ss-showcase" aria-label="Learn with SkillSprint AI">
        <div className="ss-showcase-grid" aria-hidden="true" />
        <div className="ss-showcase-inner">
          <IntelligenceGlobe reducedMotion={reducedMotion} />
          <div className="ss-showcase-copy">
            <p className="ss-eyebrow"><Sparkles size={16} aria-hidden="true" />Powered by intelligence</p>
            <h2>Grow your skills.<br /><span>Shape what’s next.</span></h2>
            <p className="ss-showcase-description">A smarter, more personal way to learn, grow, and reach your potential.</p>
          </div>
          <footer className="ss-showcase-footer">
            <span>Learn · Evolve · Excel</span>
            <span>SkillSprint AI © {new Date().getFullYear()}</span>
          </footer>
        </div>
      </aside>
    </main>
  );
};

const styles = `
  .ss-login {
    --ss-bg: #030b11; --ss-panel: #061017; --ss-line: #203039;
    --ss-text: #f1f7fb; --ss-muted: #8fa9b8; --ss-accent: #2dd4c5;
    box-sizing: border-box; display: grid; grid-template-columns: 46.5% 53.5%;
    width: 100%; min-height: 100vh; min-height: 100dvh; isolation: isolate;
    background: var(--ss-bg); color: var(--ss-text); color-scheme: dark;
    font-size: 14px; line-height: 1.5; text-align: left;
  }
  .ss-login *, .ss-login *::before, .ss-login *::after { box-sizing: border-box; }
  .ss-login h1, .ss-login h2, .ss-login p { margin: 0; }
  .ss-login button, .ss-login input { font: inherit; }
  .ss-login button { cursor: pointer; }
  .ss-login button:disabled { cursor: wait; opacity: .65; }
  .ss-login svg { flex-shrink: 0; }
  .ss-login button:focus-visible { outline: 2px solid var(--ss-accent); outline-offset: 4px; }
  .ss-login .ss-accent { color: var(--ss-accent); }
  .ss-login .ss-auth-side { display: flex; flex-direction: column; min-width: 0; padding: 30px clamp(24px, 3.5vw, 66px) 42px; }
  .ss-login .ss-brand { display: inline-flex; align-items: center; align-self: flex-start; gap: 12px; font-size: 18px; font-weight: 650; letter-spacing: -.5px; }
  .ss-login .ss-brand-icon { display: grid; place-items: center; width: 38px; height: 38px; color: var(--ss-accent); background: #092024; border: 1px solid #16454a; border-radius: 9px; }
  .ss-login .ss-auth-content { width: 100%; max-width: 420px; margin: auto; padding-top: 38px; }
  .ss-login .ss-eyebrow { display: flex; align-items: center; gap: 9px; color: var(--ss-accent); font-size: 11px; line-height: 1.6; font-weight: 600; text-transform: uppercase; letter-spacing: .15px; }
  .ss-login .ss-status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--ss-accent); }
  .ss-login .ss-intro h1 { margin-top: 17px; font-size: clamp(32px, 2.45vw, 42px); line-height: 1.2; font-weight: 650; letter-spacing: -1.25px; }
  .ss-login .ss-intro-description { margin-top: 17px; color: var(--ss-muted); font-size: 13px; line-height: 1.8; }
  .ss-login .ss-auth-card { margin-top: 34px; padding: 32px; background: var(--ss-panel); border: 1px solid var(--ss-line); border-radius: 9px; box-shadow: 0 20px 65px #0000001a; }
  .ss-login .ss-card-heading { display: flex; align-items: center; gap: 12px; padding-bottom: 24px; margin-bottom: 28px; border-bottom: 1px solid var(--ss-line); }
  .ss-login .ss-card-icon { display: grid; place-items: center; width: 40px; height: 40px; flex-shrink: 0; border-radius: 7px; border: 1px solid #15454b; color: var(--ss-accent); background: #092127; }
  .ss-login .ss-card-heading h2 { font-size: 14px; font-weight: 650; line-height: 1.5; letter-spacing: -.15px; }
  .ss-login .ss-card-heading p { margin-top: 2px; font-size: 12px; line-height: 1.6; color: var(--ss-muted); }
  .ss-login .ss-field + .ss-field { margin-top: 20px; }
  .ss-login .ss-field label { display: block; margin-bottom: 8px; color: var(--ss-text); font-size: 12px; font-weight: 550; }
  .ss-login .ss-input-wrap { position: relative; }
  .ss-login .ss-input-icon { position: absolute; top: 50%; left: 13px; transform: translateY(-50%); color: #8ba0aa; pointer-events: none; }
  .ss-login .ss-input-wrap input { display: block; width: 100%; min-width: 0; height: 45px; margin: 0; padding: 0 13px 0 41px; border: 1px solid #24333d; border-radius: 7px; outline: none; background: #0a151c; color: var(--ss-text); box-shadow: none; font-size: 13px; transition: border-color .18s, box-shadow .18s; }
  .ss-login .ss-input-wrap input::placeholder { color: #7c93a3; opacity: 1; }
  .ss-login .ss-input-wrap input:focus { border-color: var(--ss-accent); box-shadow: 0 0 0 3px #2dd4c51a; }
  .ss-login .ss-input-wrap input:disabled { opacity: .7; }
  .ss-login .ss-input-wrap input:-webkit-autofill { -webkit-text-fill-color: var(--ss-text); box-shadow: 0 0 0 100px #0a151c inset; caret-color: var(--ss-text); }
  .ss-login .ss-input-wrap--password input { padding-right: 46px; }
  .ss-login .ss-password-toggle { position: absolute; top: 1px; right: 1px; display: grid; place-items: center; width: 43px; height: 43px; padding: 0; border: 0; border-radius: 6px; color: #8ba0aa; background: transparent; }
  .ss-login .ss-password-toggle:hover { color: var(--ss-accent); }
  .ss-login .ss-submit { display: flex; align-items: center; justify-content: center; gap: 10px; width: 100%; min-height: 45px; margin-top: 24px; padding: 11px 16px; border: 1px solid transparent; border-radius: 7px; background: var(--ss-accent); color: #032125; font-size: 13px; font-weight: 650; line-height: 1.5; transition: background .18s, transform .18s; }
  .ss-login .ss-submit:hover:not(:disabled) { background: #55e5d7; }
  .ss-login .ss-submit:active:not(:disabled) { transform: translateY(1px); }
  .ss-login .ss-account-help { margin-top: 24px; text-align: center; color: var(--ss-muted); font-size: 12px; line-height: 1.8; }
  .ss-login .ss-bootstrap { margin-top: 18px; }
  .ss-login .ss-bootstrap-toggle { display: flex; align-items: center; justify-content: center; gap: 9px; width: 100%; min-height: 40px; padding: 6px 4px; border: 0; border-radius: 5px; color: var(--ss-muted); background: transparent; font-size: 11.5px; line-height: 1.6; text-align: center; }
  .ss-login .ss-bootstrap-toggle:hover { color: var(--ss-accent); }
  .ss-login .ss-bootstrap-panel { overflow: hidden; }
  .ss-login .ss-bootstrap-form { margin-top: 9px; padding: 22px; border: 1px solid var(--ss-line); border-radius: 9px; background: var(--ss-panel); }
  .ss-login .ss-bootstrap-info { margin-bottom: 20px; color: #ddc390; font-size: 12px; line-height: 1.75; }
  .ss-login .ss-submit--secondary { background: #103331; border-color: #246059; color: #b7f7e9; }
  .ss-login .ss-submit--secondary:hover:not(:disabled) { background: #17433f; }
  .ss-login .ss-error, .ss-login .ss-notice { margin-bottom: 20px; padding: 12px 14px; border-radius: 7px; font-size: 12px; line-height: 1.7; overflow-wrap: anywhere; }
  .ss-login .ss-error { border: 1px solid #783640; background: #33171f; color: #fec9ce; }
  .ss-login .ss-notice { border: 1px solid #246059; background: #103331; color: #b7f7e9; }
  .ss-login .ss-spinner { animation: ss-login-spin .9s linear infinite; }
  .ss-login .ss-showcase { position: relative; min-width: 0; overflow: hidden; border-left: 1px solid #1d3038; background: radial-gradient(ellipse at 53% 40%, #07353a55 0%, transparent 60%), #031018; }
  .ss-login .ss-showcase-grid { position: absolute; inset: 0; pointer-events: none; opacity: .4; background-image: linear-gradient(#37586425 1px, transparent 1px), linear-gradient(90deg, #37586425 1px, transparent 1px); background-size: 44px 44px; mask-image: radial-gradient(ellipse at 50% 45%, #000 10%, transparent 72%); -webkit-mask-image: radial-gradient(ellipse at 50% 45%, #000 10%, transparent 72%); }
  .ss-login .ss-showcase-inner { position: relative; display: flex; flex-direction: column; width: 100%; min-height: 100%; padding: 22px clamp(32px, 3.5vw, 66px) 40px; }
  .ss-login .ss-globe { position: relative; width: 100%; height: clamp(300px, 52vh, 490px); flex: 1 0 300px; min-height: 300px; max-height: 590px; }
  .ss-login .ss-globe-glow { position: absolute; top: 10%; left: 8%; width: 84%; height: 90%; border-radius: 50%; pointer-events: none; background: radial-gradient(ellipse, #28d8c322, #28d8c309 40%, transparent 69%); filter: blur(18px); }
  .ss-login .ss-globe-canvas { position: absolute; inset: 0; z-index: 1; opacity: 0; transition: opacity .45s; }
  .ss-login .ss-globe-canvas canvas { display: block; width: 100%; height: 100%; }
  .ss-login .ss-globe--ready .ss-globe-canvas { opacity: 1; }
  .ss-login .ss-globe-fallback { position: absolute; left: 50%; top: 50%; width: min(75%, 340px); aspect-ratio: 1; transform: translate(-50%, -50%); opacity: 1; transition: opacity .3s; }
  .ss-login .ss-globe--ready .ss-globe-fallback { opacity: 0; }
  .ss-login .ss-fallback-sphere { position: absolute; inset: 18%; border-radius: 50%; background: radial-gradient(circle at 33% 24%, #168584, #064453 49%, #071d2c 85%); box-shadow: inset -12px -14px 32px #0006, 0 0 55px #2dd4c511; }
  .ss-login .ss-fallback-ring { position: absolute; inset: 2%; border: 1.5px solid #acd9d4bb; border-radius: 50%; }
  .ss-login .ss-fallback-ring--one { transform: rotate(-25deg) scaleY(.56); }
  .ss-login .ss-fallback-ring--two { transform: rotate(58deg) scaleY(.65); border-color: #82aabb; }
  .ss-login .ss-fallback-ring--three { transform: rotate(-72deg) scaleY(.6); border-color: #b3b9cfaa; }
  .ss-login .ss-showcase-copy { position: relative; padding-top: 19px; }
  .ss-login .ss-showcase-copy h2 { margin-top: 19px; color: #b9dce3; font-size: clamp(31px, 2.55vw, 43px); font-weight: 600; line-height: 1.3; letter-spacing: -.8px; }
  .ss-login .ss-showcase-copy h2 span { color: var(--ss-accent); }
  .ss-login .ss-showcase-description { max-width: 390px; margin-top: 22px; color: #94aeb8; font-size: 13px; line-height: 2; }
  .ss-login .ss-showcase-footer { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; margin-top: 36px; padding-top: 21px; border-top: 1px solid #203039; color: #809ba8; font-size: 10px; line-height: 1.6; text-transform: uppercase; }
  @keyframes ss-login-spin { to { transform: rotate(360deg); } }
  @media (min-width: 1600px) { .ss-login .ss-showcase-inner { padding-top: 26px; padding-bottom: 48px; } .ss-login .ss-auth-content { padding-bottom: 18px; } }
  @media (max-width: 1100px) and (min-width: 861px) { .ss-login .ss-auth-side { padding-left: 26px; padding-right: 26px; } .ss-login .ss-auth-card { padding: 25px; } .ss-login .ss-showcase-inner { padding-left: 30px; padding-right: 30px; } }
  @media (max-width: 860px) {
    .ss-login { grid-template-columns: 1fr; }
    .ss-login .ss-auth-side { padding: 24px 24px 40px; }
    .ss-login .ss-auth-content { padding-top: 48px; }
    .ss-login .ss-showcase { border-left: 0; border-top: 1px solid #1d3038; }
    .ss-login .ss-showcase-inner { max-width: 660px; margin: 0 auto; padding: 10px 28px 28px; }
    .ss-login .ss-globe { height: 310px; min-height: 260px; flex: none; }
    .ss-login .ss-showcase-copy { padding-top: 0; }
    .ss-login .ss-showcase-copy h2 { font-size: clamp(30px, 5vw, 40px); }
    .ss-login .ss-showcase-description { margin-top: 18px; }
    .ss-login .ss-showcase-footer { margin-top: 28px; }
    .ss-login .ss-input-wrap input { font-size: 16px; }
  }
  @media (max-width: 420px) {
    .ss-login .ss-auth-side { padding: 20px 18px 32px; }
    .ss-login .ss-auth-content { padding-top: 36px; }
    .ss-login .ss-auth-card { margin-top: 26px; padding: 24px 20px; }
    .ss-login .ss-card-heading { gap: 10px; }
    .ss-login .ss-card-heading h2 { font-size: 13px; }
    .ss-login .ss-card-heading p { font-size: 11px; }
    .ss-login .ss-bootstrap-toggle { font-size: 11px; }
    .ss-login .ss-showcase-inner { padding-left: 22px; padding-right: 22px; }
    .ss-login .ss-globe { height: 275px; }
  }
  @media (prefers-reduced-motion: reduce) { .ss-login *, .ss-login *::before, .ss-login *::after { animation: none !important; transition: none !important; } }
`;

export default LoginPage;
