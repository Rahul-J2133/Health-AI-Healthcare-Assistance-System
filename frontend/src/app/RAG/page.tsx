'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Header from '../components/Header';

const PROFILE_KEY = 'healthai_profile';

type Profile = { name: string; age: string; gender: string };
type Message = { role: 'user' | 'assistant'; text: string };

function getProfile(): Profile | null {
  if (typeof window === 'undefined') return null;
  try { return JSON.parse(localStorage.getItem(PROFILE_KEY) || 'null'); } catch { return null; }
}

export default function RAGPage() {
  const [profile, setProfile]         = useState<Profile | null>(null);
  const [messages, setMessages]       = useState<Message[]>([]);
  const [prompt, setPrompt]           = useState('');
  const [loading, setLoading]         = useState(false);
  const [patientInfo, setPatientInfo] = useState('');
  const [infoStatus, setInfoStatus]   = useState<string | null>(null);
  const [savingInfo, setSavingInfo]   = useState(false);
  const [mounted, setMounted]         = useState(false);
  const bottomRef   = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const router      = useRouter();

  // Guard: redirect to / if no profile exists
  useEffect(() => {
    const p = getProfile();
    if (!p) { router.replace('/'); return; }
    setProfile(p);
    setMounted(true);
  }, [router]);

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);


  const handleSubmit = async () => {
    if (!prompt.trim() || loading) return;
    const userMsg = prompt.trim();
    setPrompt('');
    setMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setLoading(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/get_response`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ query: userMsg }).toString(),
      });
      if (!res.ok) throw new Error('Server error');
      const data = await res.json();
      setMessages(prev => [...prev, { role: 'assistant', text: data.answer }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', text: 'Sorry, I could not get a response. Please check the backend connection.' }]);
    }
    setLoading(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
  };

  const handleSaveInfo = async () => {
    if (!patientInfo.trim()) { setInfoStatus('Please enter some information.'); return; }
    setSavingInfo(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/update_patient_info`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ patient_info: patientInfo }).toString(),
      });
      if (res.ok) setInfoStatus('✓ Patient information updated.');
      else setInfoStatus('Failed to update patient information.');
    } catch { setInfoStatus('Connection error.'); }
    setSavingInfo(false);
  };

  if (!mounted) return null;

  return (
    <>
      <Header />
      <div className="page-container">
        <div style={{ marginBottom: '1.5rem' }}>
          <h1 className="page-title">Medical Assistant</h1>
          <p className="page-subtitle">
            Ask health questions powered by your RAG knowledge base
            {profile && <span style={{ color: 'var(--teal)', fontWeight: 600 }}> · {profile.name}</span>}
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0, 320px)', gap: '1.5rem', alignItems: 'start' }}>

          {/* Chat panel */}
          <div className="card" style={{ padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 480 }}>
            <div style={{ flex: 1, overflowY: 'auto', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem', maxHeight: 420 }}>
              {messages.length === 0 && (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', textAlign: 'center', padding: '2rem' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem', opacity: 0.5 }}>💬</div>
                  <p style={{ fontSize: '0.9rem' }}>Start a conversation. Ask about symptoms, medications, or general health questions.</p>
                </div>
              )}
              {messages.map((m, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
                  <div style={{
                    maxWidth: '80%', padding: '0.75rem 1rem',
                    borderRadius: m.role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                    background: m.role === 'user' ? 'var(--navy)' : 'var(--surface-2)',
                    color: m.role === 'user' ? 'white' : 'var(--text-primary)',
                    fontSize: '0.9rem', lineHeight: 1.6,
                  }}>
                    {m.text}
                  </div>
                </div>
              ))}
              {loading && (
                <div style={{ display: 'flex' }}>
                  <div style={{ padding: '0.75rem 1rem', borderRadius: '14px 14px 14px 4px', background: 'var(--surface-2)', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                    Thinking…
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            <div style={{ borderTop: '1px solid var(--border)', padding: '1rem', display: 'flex', gap: '0.6rem', alignItems: 'flex-end' }}>
              <textarea
                ref={textareaRef}
                value={prompt}
                onChange={e => setPrompt(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a medical question… (Enter to send)"
                rows={2}
                style={{ flex: 1, border: '1.5px solid var(--border)', borderRadius: '8px', padding: '0.65rem 0.9rem', fontFamily: 'DM Sans', fontSize: '0.9rem', color: 'var(--navy)', background: 'var(--bg)', resize: 'none', outline: 'none', lineHeight: 1.5 }}
              />
              <button className="btn-primary" onClick={handleSubmit} disabled={loading || !prompt.trim()}
                style={{ padding: '0.65rem 1rem', flexShrink: 0 }}>
                Send
              </button>
            </div>
          </div>

          {/* Patient context panel */}
          <div className="card">
            <h3 style={{ fontFamily: 'Instrument Serif', fontSize: '1.1rem', color: 'var(--navy)', marginBottom: '0.25rem' }}>Patient Context</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginBottom: '1rem' }}>
              Stored per user — used to personalise responses
            </p>

            {profile && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--surface-2)', borderRadius: '7px', padding: '0.5rem 0.75rem', marginBottom: '0.9rem' }}>
                <span style={{ fontSize: '1rem' }}>{profile.gender === 'female' ? '👩' : profile.gender === 'male' ? '👨' : '🧑'}</span>
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--navy)', fontSize: '0.84rem' }}>{profile.name}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>{profile.age} yrs · {profile.gender}</div>
                </div>
              </div>
            )}

            <textarea
              value={patientInfo}
              onChange={e => setPatientInfo(e.target.value)}
              placeholder="E.g. hypertension, on lisinopril 10mg, allergic to penicillin…"
              rows={6}
              style={{ width: '100%', border: '1.5px solid var(--border)', borderRadius: '8px', padding: '0.7rem 0.9rem', fontFamily: 'DM Sans', fontSize: '0.875rem', color: 'var(--navy)', background: 'var(--bg)', resize: 'vertical', outline: 'none', lineHeight: 1.5, boxSizing: 'border-box' }}
            />
            {infoStatus && (
              <p style={{ fontSize: '0.8rem', color: infoStatus.startsWith('✓') ? 'var(--teal)' : 'var(--red)', marginTop: '0.5rem' }}>{infoStatus}</p>
            )}
            <button className="btn-primary" onClick={handleSaveInfo} disabled={savingInfo}
              style={{ width: '100%', justifyContent: 'center', marginTop: '0.75rem' }}>
              {savingInfo ? 'Saving…' : 'Update Context'}
            </button>
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 700px) {
          div[style*="gridTemplateColumns: minmax(0,1fr) minmax(0, 320px)"] {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </>
  );
}