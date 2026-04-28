import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, Area, AreaChart } from 'recharts';

const BAR_COLORS = {
  Violence: '#ef4444', Gun: '#dc2626', Knife: '#f59e0b',
  Fire: '#ef4444', Smoke: '#f59e0b', Weapon: '#dc2626',
};

function getBarColor(type) {
  return BAR_COLORS[type] || '#3b82f6';
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-surface-900/95 backdrop-blur-md border border-white/10 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-white/60 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }} className="font-semibold">
          {p.name}: {typeof p.value === 'number' ? (p.name === 'Probability' ? `${(p.value * 100).toFixed(1)}%` : p.value) : p.value}
        </p>
      ))}
    </div>
  );
};

export default function Analytics({ detectionCounts, violenceHistory }) {
  const barData = Object.entries(detectionCounts).map(([type, count]) => ({
    type, count, fill: getBarColor(type),
  }));

  const lineData = violenceHistory.map((v, i) => ({
    idx: i,
    ts: v.ts || `F${v.frame}`,
    prob: v.prob,
  }));

  const hasData = barData.length > 0 || lineData.length > 0;

  return (
    <div className="glass-card p-5 space-y-6">
      <h2 className="text-lg font-semibold text-white flex items-center gap-2">
        <svg className="w-5 h-5 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        Analytics
      </h2>

      {!hasData ? (
        <div className="flex flex-col items-center justify-center h-48 text-white/20">
          <svg className="w-12 h-12 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
          </svg>
          <p className="text-sm">Analytics will populate during analysis</p>
        </div>
      ) : (
        <>
          {/* Detection counts bar chart */}
          {barData.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-white/50 mb-3">Detection Counts by Type</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={barData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="type" tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.1)' }} />
                  <YAxis tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.1)' }} allowDecimals={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="count" name="Count" radius={[6, 6, 0, 0]}>
                    {barData.map((entry, i) => (
                      <rect key={i} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Violence probability timeline */}
          {lineData.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-white/50 mb-3">Violence Probability Over Time</h3>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={lineData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                  <defs>
                    <linearGradient id="violenceGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#ef4444" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="#ef4444" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="ts" tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 9 }} axisLine={{ stroke: 'rgba(255,255,255,0.1)' }} interval="preserveStartEnd" />
                  <YAxis domain={[0, 1]} tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.1)' }} tickFormatter={v => `${(v * 100).toFixed(0)}%`} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="prob" name="Probability" stroke="#ef4444" fill="url(#violenceGrad)" strokeWidth={2} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Summary stats */}
          <div className="grid grid-cols-3 gap-3">
            <div className="text-center p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
              <div className="text-2xl font-bold text-white">{Object.values(detectionCounts).reduce((a, b) => a + b, 0)}</div>
              <div className="text-[10px] uppercase tracking-wider text-white/30 mt-1">Total Events</div>
            </div>
            <div className="text-center p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
              <div className="text-2xl font-bold text-red-400">{Object.keys(detectionCounts).length}</div>
              <div className="text-[10px] uppercase tracking-wider text-white/30 mt-1">Event Types</div>
            </div>
            <div className="text-center p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
              <div className="text-2xl font-bold text-amber-400">
                {lineData.length > 0 ? `${(Math.max(...lineData.map(d => d.prob)) * 100).toFixed(0)}%` : '—'}
              </div>
              <div className="text-[10px] uppercase tracking-wider text-white/30 mt-1">Peak Violence</div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
