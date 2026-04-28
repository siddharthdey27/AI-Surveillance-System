import { useRef, useEffect } from 'react';

export default function VideoFeed({ frame, violenceProb, isViolent, videoTs, status }) {
  const imgRef = useRef(null);

  useEffect(() => {
    if (imgRef.current && frame) {
      imgRef.current.src = frame;
    }
  }, [frame]);

  const probPct = Math.round(violenceProb * 100);
  const arcRadius = 54;
  const arcCircumference = Math.PI * arcRadius;
  const arcOffset = arcCircumference - (arcCircumference * violenceProb);
  const gaugeColor = violenceProb > 0.7 ? '#ef4444' : violenceProb > 0.4 ? '#f59e0b' : '#22c55e';

  return (
    <div className="glass-card p-4 space-y-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${status === 'streaming' ? 'bg-red-500 animate-pulse' : status === 'completed' ? 'bg-green-500' : 'bg-gray-500'}`} />
          Live Feed
        </h2>
        <span className="text-xs font-mono text-white/40">{videoTs}</span>
      </div>

      <div className="relative rounded-xl overflow-hidden bg-black/50 aspect-video flex items-center justify-center">
        {frame ? (
          <img
            ref={imgRef}
            alt="Video feed"
            className="w-full h-full object-contain"
          />
        ) : (
          <div className="flex flex-col items-center gap-3 text-white/30">
            <svg className="w-16 h-16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            <p className="text-sm">Upload a video to start analysis</p>
          </div>
        )}

        {isViolent && status === 'streaming' && (
          <div className="absolute inset-0 border-4 border-red-500 rounded-xl animate-pulse pointer-events-none" />
        )}
      </div>

      <div className="flex items-center gap-6">
        <div className="flex-shrink-0">
          <svg width="120" height="70" viewBox="0 0 120 70">
            <path
              d="M 10 65 A 54 54 0 0 1 110 65"
              fill="none"
              stroke="rgba(255,255,255,0.08)"
              strokeWidth="8"
              strokeLinecap="round"
            />
            <path
              d="M 10 65 A 54 54 0 0 1 110 65"
              fill="none"
              stroke={gaugeColor}
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={arcCircumference}
              strokeDashoffset={arcOffset}
              className="gauge-arc"
              style={{ filter: `drop-shadow(0 0 6px ${gaugeColor})` }}
            />
            <text x="60" y="52" textAnchor="middle" fill={gaugeColor} fontSize="18" fontWeight="700" fontFamily="Inter">
              {probPct}%
            </text>
            <text x="60" y="66" textAnchor="middle" fill="rgba(255,255,255,0.4)" fontSize="8" fontFamily="Inter">
              Violence
            </text>
          </svg>
        </div>

        <div className="flex-1 grid grid-cols-3 gap-3">
          <div className="text-center p-2 rounded-lg bg-white/[0.03]">
            <div className="text-[10px] uppercase tracking-wider text-white/30 mb-1">Status</div>
            <div className={`text-sm font-semibold ${status === 'streaming' ? 'text-green-400' : status === 'error' ? 'text-red-400' : 'text-white/60'}`}>
              {status === 'streaming' ? 'LIVE' : status === 'completed' ? 'DONE' : status.toUpperCase()}
            </div>
          </div>
          <div className="text-center p-2 rounded-lg bg-white/[0.03]">
            <div className="text-[10px] uppercase tracking-wider text-white/30 mb-1">Threat</div>
            <div className={`text-sm font-semibold ${isViolent ? 'text-red-400' : 'text-green-400'}`}>
              {isViolent ? 'DETECTED' : 'CLEAR'}
            </div>
          </div>
          <div className="text-center p-2 rounded-lg bg-white/[0.03]">
            <div className="text-[10px] uppercase tracking-wider text-white/30 mb-1">Time</div>
            <div className="text-sm font-mono text-white/70">{videoTs}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
