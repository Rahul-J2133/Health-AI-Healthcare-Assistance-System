'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Header from './components/Header';
import Link from 'next/link';
import { Line, Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  LineElement, LineController, PointElement, LinearScale, CategoryScale,
  ArcElement, DoughnutController, Tooltip, Legend,
} from 'chart.js';

ChartJS.register(LineElement, LineController, PointElement, LinearScale, CategoryScale, ArcElement, DoughnutController, Tooltip, Legend);

const PROFILE_KEY = 'healthai_profile';

type Profile = { name: string; age: string; gender: string };

function getProfile(): Profile | null {
  if (typeof window === 'undefined') return null;
  try { return JSON.parse(localStorage.getItem(PROFILE_KEY) || 'null'); } catch { return null; }
}
function saveProfile(p: Profile) { localStorage.setItem(PROFILE_KEY, JSON.stringify(p)); }
function clearProfile() { localStorage.removeItem(PROFILE_KEY); }

// ── Vitals config ──────────────────────────────────────────────────────────────
const metricConfig: Record<string, { max: number; unit: string; color: string; label: string }> = {
  body_temperature:         { max: 50,  unit: '°C',  color: '#e53935', label: 'Body Temp' },
  humidity:                 { max: 100, unit: '%',   color: '#1e88e5', label: 'Humidity' },
  room_temperature:         { max: 50,  unit: '°C',  color: '#43a047', label: 'Room Temp' },
  spo2_level:               { max: 100, unit: '%',   color: '#f59e0b', label: 'SpO₂' },
  average_beats_per_minute: { max: 200, unit: 'BPM', color: '#8e24aa', label: 'Heart Rate' },
};

const getGaugeData = (value: number, max: number, color: string) => ({
  labels: ['Value', 'Remaining'],
  datasets: [{ data: [Math.max(0, value), Math.max(0, max - value)], backgroundColor: [color, '#e8eef5'], borderWidth: 0 }],
});

// ── Profile Setup ──────────────────────────────────────────────────────────────
const iStyle: React.CSSProperties = {
  width: '100%', padding: '0.7rem 0.9rem',
  border: '1.5px solid var(--border)', borderRadius: '8px',
  fontFamily: 'DM Sans, sans-serif', fontSize: '0.9rem',
  color: 'var(--navy)', background: 'var(--bg)', outline: 'none', boxSizing: 'border-box',
};

function ProfileSetup({ onSave }: { onSave: (p: Profile) => void }) {
  const [name, setName] = useState('');
  const [age, setAge] = useState('');
  const [gender, setGender] = useState('male');
  const [error, setError] = useState('');

  const handleCreate = () => {
    if (!name.trim() || !age.trim()) { setError('Please fill all fields.'); return; }
    onSave({ name: name.trim(), age, gender });
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1.5rem' }}>
      <div style={{ maxWidth: 440, width: '100%' }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.55rem', background: 'var(--navy)', color: 'white', padding: '0.55rem 1.15rem', borderRadius: '100px', marginBottom: '1.25rem' }}>
            <span>🫀</span>
            <span style={{ fontFamily: 'Instrument Serif', fontSize: '1rem' }}>HealthAI</span>
          </div>
          <h1 style={{ fontFamily: 'Instrument Serif', fontSize: 'clamp(1.6rem, 5vw, 2.1rem)', color: 'var(--navy)', lineHeight: 1.2 }}>
            Welcome to your<br />care assistant
          </h1>
          <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem', fontSize: '0.88rem' }}>Enter your details to get started.</p>
        </div>
        <div className="card">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.7rem' }}>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="Full name" style={iStyle} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.7rem' }}>
              <input type="number" value={age} onChange={e => setAge(e.target.value)} placeholder="Age" style={iStyle} min="0" max="120" />
              <select value={gender} onChange={e => setGender(e.target.value)} style={iStyle}>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </div>
            {error && <p style={{ color: 'var(--red)', fontSize: '0.8rem' }}>{error}</p>}
            <button className="btn-primary" onClick={handleCreate} style={{ width: '100%', justifyContent: 'center', padding: '0.75rem' }}>
              Get Started
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Dashboard ──────────────────────────────────────────────────────────────────
function Dashboard({ profile }: { profile: Profile }) {
  const router = useRouter();
  const [metrics, setMetrics]     = useState<any[]>([]);
  const [ecgData, setEcgData]     = useState<any>(null);
  const [approving, setApproving] = useState(false);
  const [approved, setApproved]   = useState(false);

  const fetchDashboardData = () => {
    const base = process.env.NEXT_PUBLIC_BACKEND_API_URL;

    fetch(`${base}/health-data`)
      .then(r => r.json())
      .then(data => {
        setMetrics(Object.entries(metricConfig).map(([key, cfg]) => ({
          ...cfg, key,
          value: data[key] !== undefined && data[key] !== null
            ? parseFloat(String(data[key]).replace(/[^\d.-]/g, ''))
            : 0,
        })));
      })
      .catch(() => {});

    fetch(`${base}/unlabelled-stream`)
      .then(r => r.json())
      .then((data: number[]) => {
        if (!Array.isArray(data) || data.length === 0) return;
        setEcgData({
          labels: data.map((_, i) => i),
          datasets: [{ label: 'ECG', data, fill: true, borderColor: '#0e9f8a', backgroundColor: 'rgba(14,159,138,0.07)', tension: 0.35, pointRadius: 0, borderWidth: 2 }],
        });
      })
      .catch(() => {});
  };

  // Fetch once on mount, then poll every 5s so gauges update live
  useEffect(() => {
    fetchDashboardData();
    const timer = setInterval(fetchDashboardData, 5000);

    return () => clearInterval(timer);
  }, []);

  const handleApproveEHR = async () => {
    setApproving(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/approveForEHR`, { method: 'GET' });
      if (res.ok) setApproved(true);
      else alert('Approval failed. Check backend.');
    } catch { alert('Connection error.'); }
    setApproving(false);
  };



  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>

      {/* Header */}
      <Header />

      <div className="page-container">
        {/* Welcome banner */}
        <div style={{ background: 'linear-gradient(135deg, var(--navy) 0%, var(--navy-light) 100%)', borderRadius: 'var(--radius)', padding: 'clamp(1.25rem, 4vw, 2rem)', marginBottom: '1.75rem', color: 'white' }}>
          <p style={{ color: 'rgba(255,255,255,0.55)', fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '0.3rem' }}>Good to see you</p>
          <h1 style={{ fontFamily: 'Instrument Serif', fontSize: 'clamp(1.4rem, 4vw, 2rem)', color: 'white', marginBottom: '0.2rem' }}>{profile.name}</h1>
          <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '0.86rem', marginBottom: '1.5rem' }}>{profile.age} yrs · {profile.gender}</p>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <Link href="/RAG" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'white', color: 'var(--navy)', textDecoration: 'none', borderRadius: '8px', padding: '0.6rem 1.25rem', fontFamily: 'DM Sans', fontSize: '0.9rem', fontWeight: 700 }}>
              💬 Chat
            </Link>
            <Link href="/XRAY" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(255,255,255,0.15)', color: 'white', textDecoration: 'none', border: '1.5px solid rgba(255,255,255,0.35)', borderRadius: '8px', padding: '0.6rem 1.25rem', fontFamily: 'DM Sans', fontSize: '0.9rem', fontWeight: 700 }}>
              🩻 X-Ray
            </Link>
          </div>
        </div>

        {/* ECG */}
        <div className="card" style={{ marginBottom: '1.75rem' }}>
          <div style={{ marginBottom: '1rem' }}>
            <h2 style={{ fontFamily: 'Instrument Serif', fontSize: '1.2rem', color: 'var(--navy)', marginBottom: '0.1rem' }}>ECG Monitor</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>Real-time electrocardiogram from AD8232 sensor</p>
          </div>
          {ecgData ? (
            <Line data={ecgData} options={{
              responsive: true, maintainAspectRatio: true,
              plugins: { legend: { display: false }, tooltip: { enabled: true, mode: 'index' as const, intersect: false } },
              scales: { x: { display: false }, y: { grid: { color: '#e8eef5' }, ticks: { color: '#8fa3bc', font: { size: 11 } }, border: { display: false } } },
            }} />
          ) : (
            <div style={{ height: 110, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.86rem' }}>
              No ECG data yet.
            </div>
          )}
        </div>

        {/* Vitals */}
        <div style={{ marginBottom: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1.1rem' }}>
            <div>
              <h2 style={{ fontFamily: 'Instrument Serif', fontSize: '1.2rem', color: 'var(--navy)', marginBottom: '0.1rem' }}>Vitals Overview</h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>Live IoT sensor readings</p>
            </div>
            {approved ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--teal)', fontWeight: 600, fontSize: '0.84rem', background: 'var(--teal-dim)', padding: '0.45rem 0.9rem', borderRadius: '8px' }}>
                ✓ Approved for EHR
              </div>
            ) : (
              <button className="btn-primary" onClick={handleApproveEHR} disabled={approving}
                style={{ flexShrink: 0, fontSize: '0.84rem', padding: '0.5rem 1rem' }}>
                {approving ? 'Approving…' : '✅ Approve Vitals for EHR'}
              </button>
            )}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(148px, 1fr))', gap: '0.9rem' }}>
            {metrics.length > 0 ? metrics.map((m: any) => (
              <div key={m.key} className="card" style={{ textAlign: 'center', padding: '1.1rem 0.9rem' }}>
                <p style={{ fontWeight: 600, fontSize: '0.7rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '0.65rem' }}>{m.label}</p>
                <div style={{ width: 88, margin: '0 auto' }}>
                  <Doughnut data={getGaugeData(m.value, m.max, m.color)}
                    options={{ cutout: '72%', rotation: -90, circumference: 180, plugins: { tooltip: { enabled: false }, legend: { display: false } } }} />
                </div>
                <p style={{ fontWeight: 700, color: 'var(--navy)', fontSize: '1.05rem', marginTop: '0.4rem' }}>
                  {m.value}<span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 400, marginLeft: '2px' }}>{m.unit}</span>
                </p>
              </div>
            )) : Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="card" style={{ height: 155, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.78rem' }}>Loading…</div>
            ))}
          </div>
        </div>
      </div>


    </div>
  );
}

// ── Root ───────────────────────────────────────────────────────────────────────
export default function HomePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setProfile(getProfile());
    setMounted(true);

  }, []);

  const handleSave = async (p: Profile) => {
    saveProfile(p);
    setProfile(p);
    // Auto-cleanup: wipe all previous user data across all storage layers
    // before the new user's session begins — no leftover data from anyone
    try {
      await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/new_session`, {
        method: 'POST',
      });
    } catch {
      console.warn('new_session cleanup failed — continuing anyway.');
    }
  };

  if (!mounted) return null;
  if (!profile) return <ProfileSetup onSave={handleSave} />;
  return <Dashboard profile={profile} />;
}