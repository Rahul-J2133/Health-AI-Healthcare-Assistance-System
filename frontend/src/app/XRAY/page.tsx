'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Header from '../components/Header';
import Link from 'next/link';

const PROFILE_KEY = 'healthai_profile';
function getProfile() {
  if (typeof window === 'undefined') return null;
  try { return JSON.parse(localStorage.getItem(PROFILE_KEY) || 'null'); } catch { return null; }
}

type ResponseData = {
  result: string;
  probability: number;
  combined_img_base64?: string;
};

export default function XRayPage() {
  const [mounted, setMounted] = useState(false);
  const router = useRouter();

  // Guard: redirect to / if no profile exists
  useEffect(() => {
    if (!getProfile()) { router.replace('/'); return; }
    setMounted(true);
  }, [router]);

  const [response, setResponse] = useState<ResponseData | null>(null);
  const [mode, setMode] = useState<'idle' | 'camera' | 'preview'>('idle');
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Start camera
  const startCamera = useCallback(async () => {
    setCameraError(null);
    setMode('camera');
    setCapturedImage(null);
    setSelectedFile(null);
    setPreviewUrl(null);
    setResponse(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } } });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }
    } catch {
      setCameraError('Camera access denied or not available. Please allow camera access or use file upload.');
      setMode('idle');
    }
  }, []);

  // Stop camera stream
  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]);

  // Capture frame
  const capturePhoto = () => {
    const video = videoRef.current;
    if (!video) return;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    canvas.getContext('2d')!.drawImage(video, 0, 0);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
    setCapturedImage(dataUrl);
    setPreviewUrl(dataUrl);
    setMode('preview');
    stopCamera();
  };

  // Browse file
  const handleFileBrowse = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    stopCamera();
    setMode('preview');
    setSelectedFile(file);
    setCapturedImage(null);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    setResponse(null);
  };

  // Analyze
  const handleAnalyze = async () => {
    setLoading(true);
    setResponse(null);
    try {
      const formData = new FormData();
      if (selectedFile) {
        formData.append('file', selectedFile);
      } else if (capturedImage) {
        const res = await fetch(capturedImage);
        const blob = await res.blob();
        formData.append('file', blob, 'xray_capture.jpg');
      } else {
        setLoading(false); return;
      }
      const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/predict`, { method: 'POST', body: formData });
      if (!res.ok) throw new Error('Server error');
      const data = await res.json();
      setResponse(data);
    } catch {
      alert('Failed to analyze image. Check backend connection.');
    }
    setLoading(false);
  };

  const handleApproval = async () => {
    if (!response?.combined_img_base64) return;
    setApproving(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/approveForEHR`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: response.combined_img_base64 }),
      });
      if (res.ok) alert('Approved for EHR successfully!');
      else alert('Approval failed.');
    } catch { alert('Error during approval.'); }
    setApproving(false);
  };

  const reset = () => {
    stopCamera();
    setMode('idle');
    setCapturedImage(null);
    setSelectedFile(null);
    setPreviewUrl(null);
    setResponse(null);
    setCameraError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const isInfected = response?.result === 'INFECTED';
  if (!mounted) return null;

  return (
    <>
      <Header />
      <div className="page-container">
        <div style={{ marginBottom: '1.75rem' }}>
          <h1 className="page-title">X-Ray Analysis</h1>
          <p className="page-subtitle">Capture or upload a chest X-ray for AI-powered medical image segmentation</p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem', alignItems: 'start' }}>
          {/* Left: capture panel */}
          <div>
            {/* Mode buttons */}
            {mode === 'idle' && !cameraError && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div className="card" style={{ textAlign: 'center', padding: '2rem 1.5rem' }}>
                  <div style={{ fontSize: '3rem', marginBottom: '0.75rem' }}>📷</div>
                  <h3 style={{ fontFamily: 'Instrument Serif', fontSize: '1.15rem', color: 'var(--navy)', marginBottom: '0.4rem' }}>Use Camera</h3>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.83rem', marginBottom: '1.25rem' }}>Capture an X-ray image using your device camera</p>
                  <button className="btn-primary" onClick={startCamera} style={{ width: '100%', justifyContent: 'center' }}>
                    Open Camera
                  </button>
                </div>
                <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem', padding: '0.25rem 0' }}>— or —</div>
                <div className="card" style={{ textAlign: 'center', padding: '1.5rem' }}>
                  <div style={{ fontSize: '2rem', marginBottom: '0.6rem' }}>📁</div>
                  <h3 style={{ fontFamily: 'Instrument Serif', fontSize: '1.1rem', color: 'var(--navy)', marginBottom: '0.4rem' }}>Browse File</h3>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.83rem', marginBottom: '1rem' }}>Upload an X-ray image from your device</p>
                  <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileBrowse} style={{ display: 'none' }} id="xray-file" />
                  <label htmlFor="xray-file" className="btn-outline" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', padding: '0.65rem 1.4rem', width: '100%', justifyContent: 'center', boxSizing: 'border-box' }}>
                    Choose File
                  </label>
                </div>
              </div>
            )}

            {/* Camera error */}
            {cameraError && (
              <div className="card" style={{ borderColor: '#fca5a5', background: '#fef2f2', marginBottom: '1rem' }}>
                <p style={{ color: '#dc2626', fontSize: '0.88rem', marginBottom: '0.75rem' }}>⚠️ {cameraError}</p>
                <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileBrowse} style={{ display: 'none' }} id="xray-file-err" />
                <label htmlFor="xray-file-err" className="btn-outline" style={{ display: 'inline-flex', cursor: 'pointer', padding: '0.6rem 1rem', fontSize: '0.85rem' }}>
                  Browse Image Instead
                </label>
              </div>
            )}

            {/* Live camera */}
            {mode === 'camera' && (
              <div className="card" style={{ padding: '1rem' }}>
                <video ref={videoRef} autoPlay playsInline muted style={{ width: '100%', borderRadius: '8px', background: '#000', display: 'block', maxHeight: 340, objectFit: 'cover' }} />
                <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
                  <button className="btn-outline" onClick={reset} style={{ flex: 1 }}>Cancel</button>
                  <button className="btn-primary" onClick={capturePhoto} style={{ flex: 2, justifyContent: 'center', fontSize: '1rem' }}>
                    📸 Capture
                  </button>
                </div>
                <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileBrowse} style={{ display: 'none' }} id="xray-file-cam" />
                <label htmlFor="xray-file-cam" style={{ display: 'block', textAlign: 'center', marginTop: '0.75rem', color: 'var(--teal)', fontSize: '0.82rem', cursor: 'pointer', textDecoration: 'underline' }}>
                  Or browse from device instead
                </label>
              </div>
            )}

            {/* Preview */}
            {mode === 'preview' && previewUrl && (
              <div className="card" style={{ padding: '1rem' }}>
                <img src={previewUrl} alt="X-Ray preview" style={{ width: '100%', borderRadius: '8px', display: 'block', maxHeight: 340, objectFit: 'contain', background: '#f8fafc' }} />
                <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
                  <button className="btn-outline" onClick={reset} style={{ flex: 1 }}>Retake</button>
                  <button className="btn-primary" onClick={handleAnalyze} disabled={loading} style={{ flex: 2, justifyContent: 'center' }}>
                    {loading ? 'Analyzing…' : '🔬 Analyze X-Ray'}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Right: results */}
          <div>
            {!response && !loading && (
              <div className="card" style={{ textAlign: 'center', padding: '3rem 1.5rem', color: 'var(--text-muted)' }}>
                <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem', opacity: 0.4 }}>🩻</div>
                <p style={{ fontSize: '0.9rem' }}>Analysis results will appear here after you capture or upload an X-ray and click Analyze.</p>
              </div>
            )}

            {loading && (
              <div className="card" style={{ textAlign: 'center', padding: '3rem 1.5rem', color: 'var(--text-muted)' }}>
                <div style={{ fontSize: '2rem', marginBottom: '0.75rem', animation: 'spin 1s linear infinite', display: 'inline-block' }}>⚙️</div>
                <p>Analyzing image with AI…</p>
              </div>
            )}

            {response && !loading && (
              <div className="card fade-in">
                <h3 style={{ fontFamily: 'Instrument Serif', fontSize: '1.2rem', color: 'var(--navy)', marginBottom: '1.25rem' }}>Analysis Result</h3>
                <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
                  <div style={{ flex: 1, minWidth: 120, background: isInfected ? '#fef2f2' : '#f0fdf4', borderRadius: '10px', padding: '1rem', textAlign: 'center' }}>
                    <p style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: isInfected ? '#dc2626' : '#16a34a', marginBottom: '0.3rem' }}>Result</p>
                    <p style={{ fontWeight: 700, fontSize: '1.2rem', color: isInfected ? '#dc2626' : '#16a34a' }}>{response.result}</p>
                  </div>
                  <div style={{ flex: 1, minWidth: 120, background: 'var(--surface-2)', borderRadius: '10px', padding: '1rem', textAlign: 'center' }}>
                    <p style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>Probability</p>
                    <p style={{ fontWeight: 700, fontSize: '1.2rem', color: 'var(--navy)' }}>{Number(response.probability).toFixed(2)}%</p>
                  </div>
                </div>

                {isInfected && response.combined_img_base64 && (
                  <div style={{ marginBottom: '1.25rem' }}>
                    <p style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.6rem' }}>Segmented Region</p>
                    <img src={`data:image/jpeg;base64,${response.combined_img_base64}`} alt="Infected area highlighted" style={{ width: '100%', borderRadius: '8px', border: '2px solid #fca5a5' }} />
                    <button className="btn-primary" onClick={handleApproval} disabled={approving} style={{ width: '100%', justifyContent: 'center', marginTop: '1rem' }}>
                      {approving ? 'Approving…' : '✅ Approve for EHR'}
                    </button>
                  </div>
                )}

                {!isInfected && (
                  <div style={{ background: '#f0fdf4', borderRadius: '8px', padding: '0.85rem 1rem', color: '#16a34a', fontSize: '0.88rem' }}>
                    ✓ No infection detected. X-ray appears normal.
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>
  );
}