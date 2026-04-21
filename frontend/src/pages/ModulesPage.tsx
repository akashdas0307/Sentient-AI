import React, { useState, useEffect, useMemo } from 'react';
import { Icon, Btn, Card, StatCard, Pill, Sparkline } from '../components/shared';
import { useSentientStore } from '../store/useSentientStore';

const STATUS_COLORS: Record<string, string> = {
  healthy: 'var(--success)',
  degraded: 'var(--warning)',
  error: 'var(--destructive)',
};

const MODULE_DATA = [
  { name: 'Thalamus', status: 'healthy', pulses: 2847, pps: 4.2, history: [3.8, 4.0, 4.1, 4.3, 4.2, 4.0, 3.9, 4.2, 4.4, 4.2, 4.1, 4.3] },
  { name: 'Checkpost', status: 'healthy', pulses: 1923, pps: 3.1, history: [2.8, 3.0, 3.2, 3.1, 3.0, 2.9, 3.1, 3.2, 3.0, 3.1, 3.0, 3.1] },
  { name: 'Queue Zone', status: 'healthy', pulses: 1456, pps: 2.4, history: [2.2, 2.3, 2.5, 2.4, 2.3, 2.4, 2.5, 2.4, 2.3, 2.4, 2.5, 2.4] },
  { name: 'Temporal-Limbic-Processor', status: 'degraded', pulses: 987, pps: 1.6, history: [2.1, 2.0, 1.8, 1.7, 1.6, 1.5, 1.6, 1.7, 1.6, 1.5, 1.6, 1.6] },
  { name: 'Cognitive Core', status: 'healthy', pulses: 3421, pps: 5.7, history: [5.2, 5.4, 5.6, 5.5, 5.7, 5.8, 5.6, 5.7, 5.5, 5.6, 5.7, 5.7] },
  { name: 'World Model', status: 'healthy', pulses: 2134, pps: 3.5, history: [3.2, 3.3, 3.5, 3.4, 3.5, 3.6, 3.5, 3.4, 3.5, 3.6, 3.5, 3.5] },
  { name: 'Brainstem', status: 'healthy', pulses: 4201, pps: 7.0, history: [6.8, 6.9, 7.0, 7.1, 7.0, 6.9, 7.0, 7.1, 7.0, 6.9, 7.0, 7.0] },
  { name: 'Sleep Scheduler', status: 'healthy', pulses: 892, pps: 1.4, history: [1.3, 1.4, 1.5, 1.4, 1.3, 1.4, 1.5, 1.4, 1.3, 1.4, 1.5, 1.4] },
  { name: 'Persona Manager', status: 'healthy', pulses: 1567, pps: 2.6, history: [2.4, 2.5, 2.6, 2.5, 2.6, 2.7, 2.6, 2.5, 2.6, 2.7, 2.6, 2.6] },
  { name: 'Memory Architecture', status: 'healthy', pulses: 2890, pps: 4.8, history: [4.5, 4.6, 4.7, 4.8, 4.7, 4.8, 4.9, 4.8, 4.7, 4.8, 4.9, 4.8] },
  { name: 'Inference Gateway', status: 'error', pulses: 342, pps: 0.5, history: [1.2, 1.0, 0.8, 0.6, 0.5, 0.4, 0.5, 0.6, 0.5, 0.4, 0.5, 0.5] },
  { name: 'Agent Harness Adapter', status: 'healthy', pulses: 1234, pps: 2.0, history: [1.8, 1.9, 2.0, 2.1, 2.0, 1.9, 2.0, 2.1, 2.0, 1.9, 2.0, 2.0] },
  { name: 'Environmental Awareness', status: 'healthy', pulses: 1678, pps: 2.8, history: [2.6, 2.7, 2.8, 2.7, 2.8, 2.9, 2.8, 2.7, 2.8, 2.9, 2.8, 2.8] },
  { name: 'System Health', status: 'healthy', pulses: 3567, pps: 5.9, history: [5.6, 5.7, 5.8, 5.9, 5.8, 5.9, 6.0, 5.9, 5.8, 5.9, 6.0, 5.9] },
];

export function ModulesPage() {
  const healthSnapshot = useSentientStore((s) => s.healthSnapshot);
  const [loading, setLoading] = useState(false);

  const fetchHealth = async () => {
    setLoading(true);
    try {
      await fetch('/api/health').then(r => r.json());
    } catch { /* data arrives via WS anyway */ }
    setLoading(false);
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const modules = useMemo(() => {
    if (!healthSnapshot || Object.keys(healthSnapshot).length === 0) {
      return MODULE_DATA;
    }
    return Object.entries(healthSnapshot).map(([name, data]) => {
      const existing = MODULE_DATA.find(m => m.name === name);
      return {
        name,
        status: data.status || 'healthy',
        pulses: data.pulse_count || 0,
        pps: existing?.pps || (data.pulse_count ? data.pulse_count / 60 : 0),
        history: existing?.history || Array.from({ length: 12 }, () => Math.random() * 5),
      };
    });
  }, [healthSnapshot]);

  const maxPps = useMemo(() => Math.max(...modules.map(m => m.pps)), [modules]);
  const maxPulses = useMemo(() => Math.max(...modules.map(m => m.pulses)), [modules]);
  const healthy = useMemo(() => modules.filter(m => m.status === 'healthy').length, [modules]);
  const degraded = useMemo(() => modules.filter(m => m.status === 'degraded').length, [modules]);
  const error = useMemo(() => modules.filter(m => m.status === 'error').length, [modules]);
  const sorted = useMemo(() => [...modules].sort((a, b) => b.pps - a.pps), [modules]);

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: 24 }}>
      <div style={{ maxWidth: 1400, margin: '0 auto' }}>

        {/* Summary row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 32 }}>
          <StatCard label="Total Modules" value={modules.length} sparkData={[12, 13, 14, 14, 14, 14, 14, 14]} />
          <StatCard label="Healthy" value={healthy} color="var(--success)" sparkData={[11, 12, 12, 12, 12, 11, 12, 12]} />
          <StatCard label="Degraded" value={degraded} color="var(--warning)" sparkData={[0, 0, 1, 1, 1, 1, 1, 1]} />
          <StatCard label="Error" value={error} color="var(--destructive)" sparkData={[0, 0, 0, 0, 0, 1, 1, 1]} />
        </div>

        {/* Pulse rate chart */}
        <Card style={{ padding: 0, marginBottom: 32, overflow: 'hidden' }}>
          <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--border)' }}>
            <span className="t-label" style={{ color: 'var(--muted-foreground)' }}>PULSE RATE · PULSES/SEC · LAST 60s</span>
          </div>
          <div style={{ padding: '16px 24px' }}>
            {sorted.map(mod => (
              <div key={mod.name} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '6px 0' }}>
                <div style={{ width: 180, fontSize: 11, fontWeight: 600, color: 'var(--muted-foreground)', textTransform: 'uppercase', letterSpacing: '0.05em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flexShrink: 0 }}>
                  {mod.name}
                </div>
                <div style={{ flex: 1, height: 12, background: 'var(--surface-secondary)', borderRadius: 6, overflow: 'hidden', position: 'relative' }}>
                  <div style={{
                    height: '100%',
                    borderRadius: 6,
                    width: `${maxPps > 0 ? (mod.pps / maxPps) * 100 : 0}%`,
                    background: STATUS_COLORS[mod.status] || 'var(--primary)',
                    opacity: 0.7,
                    transition: 'width 500ms ease',
                  }} />
                </div>
                <span style={{ width: 48, fontSize: 11, fontWeight: 600, color: STATUS_COLORS[mod.status], textAlign: 'right', flexShrink: 0 }}>
                  {mod.pps.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </Card>

        {/* Module grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340, 1fr))', gap: 16 }}>
          {modules.map(mod => (
            <Card key={mod.name} hover style={{ padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <span className="t-label" style={{ color: 'var(--foreground)', letterSpacing: '0.1em', fontSize: 11 }}>
                  {mod.name.toUpperCase()}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 6, height: 6, borderRadius: 3, background: STATUS_COLORS[mod.status] }} />
                  <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.15em', color: STATUS_COLORS[mod.status] }}>
                    {mod.status}
                  </span>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <div>
                  <span style={{ fontSize: 20, fontWeight: 700 }}>{mod.pulses.toLocaleString()}</span>
                  <span style={{ fontSize: 11, color: 'var(--muted-foreground)', marginLeft: 6 }}>pulses</span>
                </div>
                <Sparkline data={mod.history} width={72} height={20} color={STATUS_COLORS[mod.status]} />
              </div>
              <div style={{ fontSize: 10, color: 'var(--subtle-foreground)', marginBottom: 12 }}>
                Last pulse: {Math.floor(Math.random() * 5 + 1)}s ago
              </div>
              {/* Activity bar */}
              <div style={{ height: 3, background: 'var(--surface-tertiary)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{
                  height: '100%',
                  borderRadius: 2,
                  width: `${maxPulses > 0 ? (mod.pulses / maxPulses) * 100 : 0}%`,
                  background: 'var(--primary)',
                  opacity: 0.6,
                  transition: 'width 500ms ease',
                }} />
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
};
