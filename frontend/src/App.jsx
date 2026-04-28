import { useState, useCallback, useRef } from 'react';
import VideoFeed from './components/VideoFeed';
import AlertPanel from './components/AlertPanel';
import IncidentTimeline from './components/IncidentTimeline';
import Analytics from './components/Analytics';
import Settings from './components/Settings';
import useSSEStream from './hooks/useSSEStream';

const TABS = [
  { id: 'live', label: 'Live View', icon: 'M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z' },
  { id: 'analytics', label: 'Analytics', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
  { id: 'settings', label: 'Settings', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z' },
];

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

export default function App() {
  const [tab, setTab] = useState('live');
  const [jobId, setJobId] = useState(null);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const isMock = import.meta.env.VITE_MOCK === 'true';

  const stream = useSSEStream(jobId);

  const handleFile = useCallback((f) => {
    if (f && f.type.startsWith('video/')) {
      setFile(f);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    handleFile(f);
  }, [handleFile]);

  const handleAnalyze = useCallback(async () => {
    if (isMock) {
      setJobId('mock-job');
      stream.startStream();
      setTab('live');
      return;
    }

    if (!file) return;
    setUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const apiBase = import.meta.env.VITE_API_URL || '';
      const res = await fetch(`${apiBase}/upload`, { method: 'POST', body: formData });

      if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);

      const data = await res.json();
      setJobId(data.job_id);
      setTab('live');

      setTimeout(() => stream.startStream(), 100);
    } catch (err) {
      console.error('Upload error:', err);
      alert('Upload failed: ' + err.message);
    } finally {
      setUploading(false);
    }
  }, [file, stream, isMock]);

  const handleDownloadLog = useCallback(async () => {
    if (!jobId || isMock) return;
    const apiBase = import.meta.env.VITE_API_URL || '';
    window.open(`${apiBase}/logs/${jobId}/download`, '_blank');
  }, [jobId, isMock]);

  const handleDownloadReport = useCallback(async () => {
    if (!jobId || isMock) return;
    const apiBase = import.meta.env.VITE_API_URL || '';
    window.open(`${apiBase}/report/${jobId}`, '_blank');
  }, [jobId, isMock]);

  const progressPct = Math.round(stream.progress * 100);

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-surface-950/60 border-b border-white/[0.06]">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-500 to-purple-600 flex items-center justify-center text-white text-lg shadow-lg shadow-primary-500/20">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
              </div>
              <div>
                <h1 className="text-base font-bold text-white leading-tight">AI Surveillance</h1>
                <p className="text-[10px] text-white/30">YOLOv8 + Deep Learning</p>
              </div>
            </div>

            <nav className="flex items-center gap-1 bg-white/[0.03] rounded-xl p-1">
              {TABS.map(t => (
                <button key={t.id} onClick={() => setTab(t.id)}
                  className={`nav-tab flex items-center gap-1.5 ${tab === t.id ? 'active' : ''}`}>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={t.icon} />
                  </svg>
                  <span className="hidden sm:inline">{t.label}</span>
                </button>
              ))}
            </nav>

            <div className="flex items-center gap-2">
              {jobId && stream.status !== 'idle' && (
                <>
                  <button onClick={handleDownloadLog} title="Download CSV Log"
                    className="p-2 rounded-lg hover:bg-white/5 text-white/40 hover:text-white/70 transition-colors">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                  </button>
                  <button onClick={handleDownloadReport} title="Download PDF Report"
                    className="p-2 rounded-lg hover:bg-white/5 text-white/40 hover:text-white/70 transition-colors">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Progress bar */}
        {stream.status === 'streaming' && (
          <div className="h-0.5 bg-white/[0.03]">
            <div className="h-full transition-all duration-300 ease-out"
              style={{ width: `${progressPct}%`, background: 'linear-gradient(90deg, #3381ff, #7b2ff7)' }} />
          </div>
        )}
      </header>

      {/* Main content */}
      <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-6 py-6">
        {/* Upload section — show when no job */}
        {!jobId && tab === 'live' && (
          <div className="animate-fade-in max-w-xl mx-auto mt-8">
            <div
              className={`glass-card-hover p-8 text-center cursor-pointer transition-all duration-300 ${dragOver ? 'border-primary-500 bg-primary-500/10 scale-[1.02]' : ''}`}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={e => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
            >
              <input ref={fileInputRef} type="file" accept="video/*" className="hidden"
                onChange={e => handleFile(e.target.files[0])} />

              <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-primary-500/20 to-purple-600/20 flex items-center justify-center">
                <svg className="w-8 h-8 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>

              <h3 className="text-lg font-semibold text-white mb-1">
                {file ? file.name : 'Drop video file here'}
              </h3>
              <p className="text-sm text-white/40">
                {file ? formatFileSize(file.size) : 'or click to browse — MP4, AVI, MOV, MKV, WebM'}
              </p>

              {file && (
                <div className="mt-4 flex items-center justify-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-green-400" />
                  <span className="text-xs text-green-400">Ready to analyze</span>
                </div>
              )}
            </div>

            <button
              onClick={handleAnalyze}
              disabled={!file && !isMock}
              className="btn-primary w-full mt-4 flex items-center justify-center gap-2"
            >
              {uploading ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                  Uploading...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                  {isMock ? 'Run Mock Analysis' : 'Analyze Video'}
                </>
              )}
            </button>
          </div>
        )}

        {/* Live View tab */}
        {tab === 'live' && jobId && (
          <div className="animate-fade-in space-y-4">
            {/* Status bar */}
            <div className="flex items-center justify-between text-xs text-white/40">
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${stream.status === 'streaming' ? 'bg-green-400 animate-pulse' : stream.status === 'completed' ? 'bg-blue-400' : 'bg-gray-500'}`} />
                  {stream.status === 'streaming' ? 'Processing' : stream.status === 'completed' ? 'Complete' : stream.status}
                </span>
                {stream.status === 'streaming' && <span>{progressPct}%</span>}
              </div>
              <div className="flex items-center gap-3">
                <span>{stream.allAlerts.length} alerts</span>
                {stream.status === 'streaming' && (
                  <button onClick={stream.stopStream}
                    className="px-3 py-1 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors text-xs font-medium">
                    Stop
                  </button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2">
                <VideoFeed
                  frame={stream.frame}
                  violenceProb={stream.violenceProb}
                  isViolent={stream.isViolent}
                  videoTs={stream.videoTs}
                  status={stream.status}
                />
              </div>
              <div className="lg:col-span-1">
                <AlertPanel alerts={stream.allAlerts} />
              </div>
            </div>

            <IncidentTimeline alerts={stream.allAlerts} />
          </div>
        )}

        {/* Analytics tab */}
        {tab === 'analytics' && (
          <div className="animate-fade-in">
            <Analytics
              detectionCounts={stream.detectionCounts}
              violenceHistory={stream.violenceHistory}
            />
          </div>
        )}

        {/* Settings tab */}
        {tab === 'settings' && (
          <div className="animate-fade-in">
            <Settings />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="py-4 text-center text-[11px] text-white/20 border-t border-white/[0.04]">
        AI Surveillance System v2.0 &middot; YOLOv8 + Deep Learning &middot; Built with FastAPI + React
      </footer>
    </div>
  );
}
