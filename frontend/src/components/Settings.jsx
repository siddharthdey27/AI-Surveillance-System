import { useState, useEffect } from 'react';

const DEFAULTS = {
  twilioPhone: '',
  telegramChatId: '',
  violenceThreshold: 0.6,
  yoloConfidence: 0.4,
  frameSkip: 2,
  saveSnapshots: true,
  enableTwilio: false,
  enableTelegram: false,
};

export default function Settings() {
  const [settings, setSettings] = useState(() => {
    try {
      const saved = localStorage.getItem('ai_surveillance_settings');
      return saved ? { ...DEFAULTS, ...JSON.parse(saved) } : DEFAULTS;
    } catch { return DEFAULTS; }
  });
  const [saved, setSaved] = useState(false);

  const update = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = () => {
    localStorage.setItem('ai_surveillance_settings', JSON.stringify(settings));
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleReset = () => {
    setSettings(DEFAULTS);
    localStorage.removeItem('ai_surveillance_settings');
    setSaved(false);
  };

  return (
    <div className="glass-card p-6 max-w-2xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white flex items-center gap-2">
          <svg className="w-5 h-5 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          Settings
        </h2>
        {saved && (
          <span className="text-xs text-green-400 bg-green-400/10 px-3 py-1 rounded-full animate-fade-in">
            Saved successfully
          </span>
        )}
      </div>

      {/* Detection Thresholds */}
      <section>
        <h3 className="text-sm font-semibold text-white/50 uppercase tracking-wider mb-4">Detection Thresholds</h3>
        <div className="space-y-4">
          <div>
            <div className="flex justify-between mb-1.5">
              <label className="text-sm text-white/70">Violence Threshold</label>
              <span className="text-sm font-mono text-primary-400">{settings.violenceThreshold.toFixed(2)}</span>
            </div>
            <input type="range" min="0.1" max="1" step="0.05" value={settings.violenceThreshold}
              onChange={e => update('violenceThreshold', parseFloat(e.target.value))}
              className="w-full h-1.5 rounded-full appearance-none bg-white/10 accent-primary-500" />
          </div>
          <div>
            <div className="flex justify-between mb-1.5">
              <label className="text-sm text-white/70">YOLO Confidence</label>
              <span className="text-sm font-mono text-primary-400">{settings.yoloConfidence.toFixed(2)}</span>
            </div>
            <input type="range" min="0.1" max="1" step="0.05" value={settings.yoloConfidence}
              onChange={e => update('yoloConfidence', parseFloat(e.target.value))}
              className="w-full h-1.5 rounded-full appearance-none bg-white/10 accent-primary-500" />
          </div>
          <div>
            <div className="flex justify-between mb-1.5">
              <label className="text-sm text-white/70">Frame Skip</label>
              <span className="text-sm font-mono text-primary-400">{settings.frameSkip}</span>
            </div>
            <select value={settings.frameSkip} onChange={e => update('frameSkip', parseInt(e.target.value))}
              className="w-full bg-white/[0.05] border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-primary-500">
              {[1,2,3,4,5].map(n => <option key={n} value={n}>Every {n} frame{n>1?'s':''}</option>)}
            </select>
          </div>
          <label className="flex items-center gap-3 cursor-pointer">
            <input type="checkbox" checked={settings.saveSnapshots} onChange={e => update('saveSnapshots', e.target.checked)}
              className="w-4 h-4 rounded accent-primary-500" />
            <span className="text-sm text-white/70">Save snapshots on detection</span>
          </label>
        </div>
      </section>

      {/* Twilio */}
      <section>
        <h3 className="text-sm font-semibold text-white/50 uppercase tracking-wider mb-4">Twilio SMS Alerts</h3>
        <label className="flex items-center gap-3 cursor-pointer mb-4">
          <input type="checkbox" checked={settings.enableTwilio} onChange={e => update('enableTwilio', e.target.checked)}
            className="w-4 h-4 rounded accent-primary-500" />
          <span className="text-sm text-white/70">Enable Twilio notifications</span>
        </label>
        {settings.enableTwilio && (
          <div>
            <label className="text-sm text-white/50 mb-1 block">Recipient Phone Number</label>
            <input type="tel" value={settings.twilioPhone} onChange={e => update('twilioPhone', e.target.value)}
              placeholder="+1234567890"
              className="w-full bg-white/[0.05] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/20 focus:outline-none focus:border-primary-500" />
            <p className="text-[10px] text-white/30 mt-1">Configure TWILIO_* credentials in your .env file</p>
          </div>
        )}
      </section>

      {/* Telegram */}
      <section>
        <h3 className="text-sm font-semibold text-white/50 uppercase tracking-wider mb-4">Telegram Bot Alerts</h3>
        <label className="flex items-center gap-3 cursor-pointer mb-4">
          <input type="checkbox" checked={settings.enableTelegram} onChange={e => update('enableTelegram', e.target.checked)}
            className="w-4 h-4 rounded accent-primary-500" />
          <span className="text-sm text-white/70">Enable Telegram notifications</span>
        </label>
        {settings.enableTelegram && (
          <div>
            <label className="text-sm text-white/50 mb-1 block">Telegram Chat ID</label>
            <input type="text" value={settings.telegramChatId} onChange={e => update('telegramChatId', e.target.value)}
              placeholder="123456789"
              className="w-full bg-white/[0.05] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/20 focus:outline-none focus:border-primary-500" />
            <p className="text-[10px] text-white/30 mt-1">Configure TELEGRAM_BOT_TOKEN in your .env file</p>
          </div>
        )}
      </section>

      {/* Actions */}
      <div className="flex gap-3 pt-2">
        <button onClick={handleSave} className="btn-primary flex-1">Save Settings</button>
        <button onClick={handleReset}
          className="flex-1 px-6 py-3 rounded-xl font-semibold text-white/60 border border-white/10 hover:bg-white/5 transition-all">
          Reset Defaults
        </button>
      </div>
    </div>
  );
}
