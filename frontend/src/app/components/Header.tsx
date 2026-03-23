'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useEffect } from 'react';

const PROFILE_KEY = 'healthai_profile';
type Profile = { name: string; age: string; gender: string };

function getProfile(): Profile | null {
  if (typeof window === 'undefined') return null;
  try { return JSON.parse(localStorage.getItem(PROFILE_KEY) || 'null'); } catch { return null; }
}

const navLinks = [
  { name: 'Home',   path: '/',     icon: '🏠' },
  { name: 'Chat',   path: '/RAG',  icon: '💬' },
  { name: 'X-Ray',  path: '/XRAY', icon: '🩻' },
] as const;

// ── EHR Modal ──────────────────────────────────────────────────────────────
function EHRModal({ profile, onClose }: { profile: Profile; onClose: () => void }) {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');

  const generate = async () => {
    setState('loading');
    const params = new URLSearchParams({ name: profile.name, gender: profile.gender, age: profile.age }).toString();
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/generate-pdf?${params}`);
      if (!res.ok) throw new Error();
      const blob = await res.blob();
      const url  = window.URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href = url; a.download = `EHR_${profile.name.replace(/\s+/g, '_')}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
      setState('done');
    } catch { setState('error'); }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,35,66,0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem', backdropFilter: 'blur(3px)' }}>
      <div className="card fade-in" style={{ maxWidth: 420, width: '100%', textAlign: 'center', padding: '2rem' }}>
        {state === 'done' ? (
          <>
            <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'var(--teal-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.8rem', margin: '0 auto 1rem' }}>✅</div>
            <h2 style={{ fontFamily: 'Instrument Serif', fontSize: '1.4rem', color: 'var(--navy)', marginBottom: '0.4rem' }}>EHR Downloaded</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', marginBottom: '1.5rem' }}>Report for <strong style={{ color: 'var(--navy)' }}>{profile.name}</strong> saved to your device.</p>
            <button className="btn-navy" onClick={onClose} style={{ width: '100%' }}>Close</button>
          </>
        ) : state === 'error' ? (
          <>
            <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>⚠️</div>
            <h2 style={{ fontFamily: 'Instrument Serif', fontSize: '1.3rem', color: 'var(--navy)', marginBottom: '0.4rem' }}>Generation Failed</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>Backend unreachable. Make sure the server is running.</p>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button className="btn-outline" onClick={onClose} style={{ flex: 1 }}>Cancel</button>
              <button className="btn-primary" onClick={generate} style={{ flex: 1 }}>Retry</button>
            </div>
          </>
        ) : (
          <>
            <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>📋</div>
            <h2 style={{ fontFamily: 'Instrument Serif', fontSize: '1.4rem', color: 'var(--navy)', marginBottom: '0.4rem' }}>Generate EHR</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginBottom: '0.5rem' }}>
              For <strong>{profile.name}</strong> · {profile.age} yrs · {profile.gender}
            </p>
            <div style={{ background: 'var(--surface-2)', borderRadius: '8px', padding: '0.65rem 1rem', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '1.5rem', textAlign: 'left', lineHeight: 1.6 }}>
              Includes: IoT vitals · ECG data · X-ray analysis · Medical history
            </div>
            {state === 'loading' ? (
              <div style={{ display: 'flex', justifyContent: 'center', gap: 6, padding: '0.75rem 0' }}>
                {[0,1,2].map(i => <div key={i} style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--teal)', animation: `ehrDot 1.2s ${i*0.2}s ease-in-out infinite` }} />)}
              </div>
            ) : (
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <button className="btn-outline" onClick={onClose} style={{ flex: 1 }}>Cancel</button>
                <button className="btn-primary" onClick={generate} style={{ flex: 1 }}>Download PDF</button>
              </div>
            )}
          </>
        )}
      </div>
      <style>{`@keyframes ehrDot{0%,80%,100%{transform:scale(0.6);opacity:.4}40%{transform:scale(1);opacity:1}}`}</style>
    </div>
  );
}

// ── Reset Modal ────────────────────────────────────────────────────────────
function ResetModal({ onClose }: { onClose: () => void }) {
  const [resetting, setResetting] = useState(false);
  const [done, setDone]           = useState(false);

  const handleReset = async () => {
    setResetting(true);
    try {
      await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/reset_user_data`, { method: 'POST' });
      // Hard navigate to / — clears ALL React state on every page
      // regardless of which page the user is currently on
      localStorage.clear();
      window.location.href = '/';
    } catch { alert('Reset failed. Check backend connection.'); }
    setResetting(false);
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,35,66,0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem', backdropFilter: 'blur(3px)' }}>
      <div className="card fade-in" style={{ maxWidth: 400, width: '100%', textAlign: 'center', padding: '2rem' }}>
        {done ? (
          <>
            <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>🗑️</div>
            <h2 style={{ fontFamily: 'Instrument Serif', fontSize: '1.3rem', color: 'var(--navy)', marginBottom: '0.4rem' }}>Data Cleared</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>All patient data has been reset.</p>
            <button className="btn-navy" onClick={onClose} style={{ width: '100%' }}>Close</button>
          </>
        ) : (
          <>
            <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>⚠️</div>
            <h2 style={{ fontFamily: 'Instrument Serif', fontSize: '1.3rem', color: 'var(--navy)', marginBottom: '0.4rem' }}>Reset All Data?</h2>
            <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: '8px', padding: '0.75rem 1rem', fontSize: '0.8rem', color: '#dc2626', marginBottom: '1.5rem', textAlign: 'left', lineHeight: 1.7 }}>
              • Vitals history (ECG, sensor readings)<br />
              • Chat conversation history<br />
              • Medical notes
            </div>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button className="btn-outline" onClick={onClose} style={{ flex: 1 }} disabled={resetting}>Cancel</button>
              <button onClick={handleReset} disabled={resetting}
                style={{ flex: 1, padding: '0.65rem 1rem', borderRadius: '8px', background: '#dc2626', color: 'white', border: 'none', fontFamily: 'DM Sans', fontWeight: 600, fontSize: '0.9rem', cursor: resetting ? 'not-allowed' : 'pointer', opacity: resetting ? 0.7 : 1 }}>
                {resetting ? 'Resetting…' : 'Yes, Reset'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── Header ─────────────────────────────────────────────────────────────────
export default function Header() {
  const pathname            = usePathname();
  const [open, setOpen]     = useState(false);
  const [showEHR, setShowEHR]     = useState(false);
  const [showReset, setShowReset] = useState(false);
  const [profile, setProfile]     = useState<Profile | null>(null);

  useEffect(() => { setProfile(getProfile()); }, [pathname]);

  const btnBase: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: '0.35rem',
    padding: '0.38rem 0.88rem', borderRadius: '7px',
    cursor: 'pointer', fontSize: '0.84rem',
    fontFamily: 'DM Sans', fontWeight: 500, border: 'none',
  };

  return (
    <>
      {showEHR   && profile && <EHRModal   profile={profile} onClose={() => setShowEHR(false)} />}
      {showReset && <ResetModal onClose={() => setShowReset(false)} />}

      <header style={{ background: 'var(--navy)', color: 'white', padding: '0 1.25rem', height: 60, display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'sticky', top: 0, zIndex: 200, boxShadow: '0 2px 12px rgba(15,35,66,0.25)' }}>

        {/* Left: logo */}
        <Link href="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.45rem', color: 'white', flexShrink: 0 }}>
          <span style={{ fontSize: '1.15rem' }}>🫀</span>
          <span style={{ fontFamily: 'Instrument Serif', fontSize: '1.05rem' }}>HealthAI</span>
        </Link>

        {/* Centre: nav links */}
        <nav style={{ display: 'flex', gap: '0.25rem' }} className="desktop-nav">
          {navLinks.map(n => (
            <Link key={n.path} href={n.path} style={{ textDecoration: 'none' }}>
              <span style={{
                display: 'flex', alignItems: 'center', gap: '0.3rem',
                padding: '0.38rem 0.82rem', borderRadius: '7px',
                fontSize: '0.84rem', fontWeight: 500, fontFamily: 'DM Sans',
                background: pathname === n.path ? 'rgba(255,255,255,0.15)' : 'transparent',
                color: pathname === n.path ? 'white' : 'rgba(255,255,255,0.65)',
                transition: 'all 0.15s', cursor: 'pointer',
              }}>
                {n.icon} {n.name}
              </span>
            </Link>
          ))}
        </nav>

        {/* Right: action buttons — always visible when profile exists */}
        {profile && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }} className="desktop-nav">
            <button onClick={() => setShowEHR(true)} style={{ ...btnBase, background: 'rgba(255,255,255,0.12)', color: 'white' }}>
              📋 Generate EHR
            </button>
            <button onClick={() => setShowReset(true)} style={{ ...btnBase, background: 'rgba(220,38,38,0.18)', color: '#fca5a5' }}>
              🗑️ Reset Data
            </button>
          </div>
        )}

        {/* Mobile hamburger */}
        <button onClick={() => setOpen(o => !o)} className="hamburger" aria-label="Menu"
          style={{ background: 'none', border: 'none', color: 'white', cursor: 'pointer', fontSize: '1.4rem', display: 'none', padding: 4 }}>
          {open ? '✕' : '☰'}
        </button>
      </header>

      {/* Mobile drawer */}
      {open && (
        <div className="mobile-nav" style={{ position: 'fixed', top: 60, left: 0, right: 0, background: 'var(--navy)', zIndex: 199, padding: '0.9rem', display: 'flex', flexDirection: 'column', gap: '0.35rem', boxShadow: '0 8px 24px rgba(0,0,0,0.3)' }}>
          {navLinks.map(n => (
            <Link key={n.path} href={n.path} style={{ textDecoration: 'none' }} onClick={() => setOpen(false)}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', padding: '0.7rem 1rem', borderRadius: '8px', background: pathname === n.path ? 'rgba(255,255,255,0.12)' : 'transparent', color: 'white', fontSize: '0.93rem', fontFamily: 'DM Sans' }}>
                {n.icon} {n.name}
              </div>
            </Link>
          ))}
          {profile && (
            <>
              <button onClick={() => { setShowEHR(true); setOpen(false); }}
                style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', padding: '0.7rem 1rem', borderRadius: '8px', color: 'white', fontSize: '0.93rem', fontFamily: 'DM Sans', background: 'rgba(255,255,255,0.1)', border: 'none', cursor: 'pointer' }}>
                📋 Generate EHR
              </button>
              <button onClick={() => { setShowReset(true); setOpen(false); }}
                style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', padding: '0.7rem 1rem', borderRadius: '8px', color: '#fca5a5', fontSize: '0.93rem', fontFamily: 'DM Sans', background: 'rgba(220,38,38,0.12)', border: 'none', cursor: 'pointer' }}>
                🗑️ Reset Data
              </button>
            </>
          )}
        </div>
      )}

      <style>{`
        @media (max-width: 640px) { .desktop-nav { display: none !important; } .hamburger { display: flex !important; } }
        @media (min-width: 641px) { .mobile-nav { display: none !important; } .hamburger { display: none !important; } }
      `}</style>
    </>
  );
}