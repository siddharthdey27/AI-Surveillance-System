import { useRef, useEffect } from 'react';

const EMOJI_MAP = {
  violence: '\u{1f6a8}', gun: '\u{1f52b}', weapon: '\u{1f52b}',
  knife: '\u{1f52a}', fire: '\u{1f525}', smoke: '\u{1f4a8}',
};

const COLOR_MAP = {
  violence: '#ef4444', gun: '#ef4444', weapon: '#ef4444',
  fire: '#ef4444', knife: '#f59e0b', smoke: '#f59e0b',
};

function getColor(type) {
  const l = type.toLowerCase();
  for (const [k, v] of Object.entries(COLOR_MAP)) { if (l.includes(k)) return v; }
  return '#3b82f6';
}

function getEmoji(type) {
  const l = type.toLowerCase();
  for (const [k, v] of Object.entries(EMOJI_MAP)) { if (l.includes(k)) return v; }
  return '\u26a0\ufe0f';
}

export default function IncidentTimeline({ alerts, onSelectAlert }) {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollLeft = scrollRef.current.scrollWidth;
    }
  }, [alerts.length]);

  if (alerts.length === 0) {
    return (
      <div className="glass-card p-4">
        <h3 className="text-sm font-semibold text-white/60 mb-3 flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Incident Timeline
        </h3>
        <div className="h-16 flex items-center justify-center text-white/20 text-sm">
          Events will appear here during analysis
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card p-4">
      <h3 className="text-sm font-semibold text-white/60 mb-3 flex items-center gap-2">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        Incident Timeline
        <span className="ml-auto text-xs text-white/30">{alerts.length} events</span>
      </h3>

      <div ref={scrollRef} className="overflow-x-auto pb-2" style={{ scrollBehavior: 'smooth' }}>
        <div className="relative flex items-end gap-1 min-w-max px-2" style={{ minHeight: '80px' }}>
          {/* Timeline baseline */}
          <div className="absolute bottom-6 left-0 right-0 h-px bg-white/10" />

          {alerts.map((alert, i) => {
            const color = getColor(alert.event_type);
            const emoji = getEmoji(alert.event_type);
            const height = 20 + (alert.confidence || 0.5) * 40;

            return (
              <button
                key={`${alert.video_timestamp}-${i}`}
                onClick={() => onSelectAlert && onSelectAlert(alert, i)}
                className="flex flex-col items-center group cursor-pointer transition-transform duration-200 hover:scale-110 focus:outline-none"
                style={{ minWidth: '44px' }}
                title={`${alert.event_type} at ${alert.video_timestamp} (${Math.round((alert.confidence || 0) * 100)}%)`}
              >
                <div
                  className="rounded-t-sm w-6 transition-all duration-300 group-hover:w-8"
                  style={{
                    height: `${height}px`,
                    background: `linear-gradient(to top, ${color}44, ${color})`,
                    boxShadow: `0 0 8px ${color}40`,
                  }}
                />
                <div className="text-base mt-1 group-hover:scale-125 transition-transform">{emoji}</div>
                <div className="text-[9px] font-mono text-white/30 mt-0.5 group-hover:text-white/60 transition-colors">
                  {alert.video_timestamp}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
