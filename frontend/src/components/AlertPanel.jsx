import { useRef, useEffect } from 'react';

const SEVERITY_COLORS = {
  violence: { bg: 'rgba(239,68,68,0.15)', border: '#ef4444', text: '#fca5a5' },
  gun: { bg: 'rgba(239,68,68,0.15)', border: '#ef4444', text: '#fca5a5' },
  weapon: { bg: 'rgba(239,68,68,0.15)', border: '#ef4444', text: '#fca5a5' },
  fire: { bg: 'rgba(239,68,68,0.15)', border: '#ef4444', text: '#fca5a5' },
  knife: { bg: 'rgba(245,158,11,0.15)', border: '#f59e0b', text: '#fcd34d' },
  smoke: { bg: 'rgba(245,158,11,0.15)', border: '#f59e0b', text: '#fcd34d' },
};

function getSeverity(eventType) {
  const lower = eventType.toLowerCase();
  for (const [key, val] of Object.entries(SEVERITY_COLORS)) {
    if (lower.includes(key)) return val;
  }
  return { bg: 'rgba(59,130,246,0.15)', border: '#3b82f6', text: '#93c5fd' };
}

const EMOJI_MAP = {
  violence: '\u{1f6a8}', gun: '\u{1f52b}', weapon: '\u{1f52b}',
  knife: '\u{1f52a}', fire: '\u{1f525}', smoke: '\u{1f4a8}',
};

function getEmoji(eventType) {
  const lower = eventType.toLowerCase();
  for (const [key, emoji] of Object.entries(EMOJI_MAP)) {
    if (lower.includes(key)) return emoji;
  }
  return '\u26a0\ufe0f';
}

export default function AlertPanel({ alerts }) {
  const panelRef = useRef(null);

  useEffect(() => {
    if (panelRef.current) {
      panelRef.current.scrollTop = 0;
    }
  }, [alerts.length]);

  return (
    <div className="glass-card p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          Alerts
        </h2>
        <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-red-500/20 text-red-400">
          {alerts.length}
        </span>
      </div>

      <div ref={panelRef} className="flex-1 overflow-y-auto space-y-2 max-h-[500px] pr-1">
        {alerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-white/20">
            <svg className="w-10 h-10 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm">No alerts yet</p>
          </div>
        ) : (
          [...alerts].reverse().map((alert, i) => {
            const sev = getSeverity(alert.event_type);
            const confPct = Math.round((alert.confidence || 0) * 100);
            return (
              <div
                key={`${alert.video_timestamp}-${alert.event_type}-${i}`}
                className="alert-enter rounded-xl p-3 transition-all duration-300"
                style={{ background: sev.bg, borderLeft: `3px solid ${sev.border}` }}
              >
                <div className="flex items-start gap-2">
                  <span className="text-lg flex-shrink-0">{getEmoji(alert.event_type)}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-sm" style={{ color: sev.text }}>
                        {alert.event_type}
                      </span>
                      <span className="text-[10px] font-mono text-white/40 flex-shrink-0">
                        {alert.video_timestamp}
                      </span>
                    </div>
                    <div className="mt-1.5 flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{ width: `${confPct}%`, background: sev.border }}
                        />
                      </div>
                      <span className="text-[10px] font-mono text-white/50 w-8 text-right">
                        {confPct}%
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
