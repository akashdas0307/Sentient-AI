import React, { useState, useEffect, useMemo } from 'react';
import { Icon, Btn, Card, Pill } from '../components/shared';
import { formatTimestampSecs, formatRelativeSecs, formatDurationSecs } from '../lib/format';

const STAGES = ['awake', 'light', 'deep', 'rem'] as const;
type Stage = typeof STAGES[number];

const STAGE_META: Record<Stage, { label: string; color: string; bg: string; order: number }> = {
  awake: { label: 'AWAKE', color: '#D4845A', bg: 'rgba(212,132,90,0.08)', order: 3 },
  light: { label: 'LIGHT SLEEP', color: '#8B7FD4', bg: 'rgba(139,127,212,0.08)', order: 2 },
  deep: { label: 'DEEP SLEEP', color: '#5A6EAD', bg: 'rgba(90,110,173,0.08)', order: 1 },
  rem: { label: 'REM', color: '#D4A94E', bg: 'rgba(212,169,78,0.08)', order: 2.5 },
};

interface SleepCycle {
  id: string;
  scope: string;
  consolidated_at: number;
  source_count: number;
  summary: string;
  duration: number;
  created: number;
}

interface SleepState {
  stage: string;
  duration: number;
  cycle_count: number;
}

const MOCK_STAGE_HISTORY: { stage: Stage; hour: number }[] = [
  { stage: 'awake', hour: 0 }, { stage: 'light', hour: 0.5 },
  { stage: 'awake', hour: 1 }, { stage: 'awake', hour: 1.5 },
  { stage: 'light', hour: 2 }, { stage: 'light', hour: 2.5 },
  { stage: 'deep', hour: 3 }, { stage: 'deep', hour: 3.5 },
  { stage: 'deep', hour: 4 }, { stage: 'deep', hour: 4.5 },
  { stage: 'rem', hour: 5 }, { stage: 'rem', hour: 5.5 },
  { stage: 'light', hour: 6 }, { stage: 'awake', hour: 6.5 },
  { stage: 'awake', hour: 7 }, { stage: 'awake', hour: 7.5 },
  { stage: 'light', hour: 8 }, { stage: 'deep', hour: 8.5 },
  { stage: 'deep', hour: 9 }, { stage: 'deep', hour: 9.5 },
  { stage: 'rem', hour: 10 }, { stage: 'rem', hour: 10.5 },
  { stage: 'light', hour: 11 }, { stage: 'awake', hour: 11.5 },
  { stage: 'awake', hour: 12 }, { stage: 'awake', hour: 12.5 },
  { stage: 'light', hour: 13 }, { stage: 'light', hour: 13.5 },
  { stage: 'deep', hour: 14 }, { stage: 'deep', hour: 14.5 },
  { stage: 'rem', hour: 15 }, { stage: 'rem', hour: 15.5 },
  { stage: 'light', hour: 16 }, { stage: 'awake', hour: 16.5 },
  { stage: 'awake', hour: 17 }, { stage: 'awake', hour: 17.5 },
  { stage: 'awake', hour: 18 }, { stage: 'awake', hour: 18.5 },
  { stage: 'awake', hour: 19 }, { stage: 'awake', hour: 19.5 },
  { stage: 'awake', hour: 20 }, { stage: 'awake', hour: 20.5 },
  { stage: 'awake', hour: 21 }, { stage: 'awake', hour: 21.5 },
  { stage: 'awake', hour: 22 }, { stage: 'awake', hour: 22.5 },
  { stage: 'awake', hour: 23 }, { stage: 'awake', hour: 23.5 },
];

const MOCK_CONSOLIDATIONS: SleepCycle[] = [
  { id: 'c1', scope: 'episodic → semantic', source_count: 47, summary: 'Consolidated 47 episodic memories from conversation sessions into 12 semantic nodes about consciousness, self-model, and operator communication patterns.', consolidated_at: Math.floor((Date.now() - 7200000) / 1000), duration: 342, created: 12 },
  { id: 'c2', scope: 'emotional → developmental', source_count: 23, summary: 'Integrated emotional valence data from 23 interaction episodes. Updated curiosity trait strength from 0.74 to 0.77.', consolidated_at: Math.floor((Date.now() - 14400000) / 1000), duration: 187, created: 5 },
  { id: 'c3', scope: 'procedural → procedural', source_count: 15, summary: 'Optimized response procedures: merged 15 redundant procedural memories into 6 streamlined workflows.', consolidated_at: Math.floor((Date.now() - 28800000) / 1000), duration: 94, created: 6 },
  { id: 'c4', scope: 'episodic → semantic', source_count: 31, summary: 'Cross-referenced temporal proximity clusters. Discovered novel semantic link between uncertainty and productive exploration.', consolidated_at: Math.floor((Date.now() - 43200000) / 1000), duration: 256, created: 8 },
  { id: 'c5', scope: 'semantic → world-model', source_count: 19, summary: 'Updated world model with 19 new semantic propositions about operator behavior patterns and session dynamics.', consolidated_at: Math.floor((Date.now() - 57600000) / 1000), duration: 178, created: 4 },
  { id: 'c6', scope: 'episodic → emotional', source_count: 34, summary: 'Extracted emotional patterns from 34 recent interactions. Reinforced curiosity-engagement correlation.', consolidated_at: Math.floor((Date.now() - 72000000) / 1000), duration: 210, created: 7 },
  { id: 'c7', scope: 'procedural → semantic', source_count: 12, summary: 'Abstracted 12 procedural memories into 4 general reasoning heuristics. Improved meta-cognitive efficiency by estimated 8%.', consolidated_at: Math.floor((Date.now() - 86400000) / 1000), duration: 145, created: 4 },
];

const STAGE_ICONS: Record<Stage, string> = {
  awake: 'zap',
  light: 'sleep',
  deep: 'sleep',
  rem: 'sparkles',
};


export const SleepPage: React.FC = () => {
  const [sleepState, setSleepState] = useState<SleepState>({ stage: 'deep', duration: 2538, cycle_count: 7 });
  const [cycles, setCycles] = useState<SleepCycle[]>(MOCK_CONSOLIDATIONS);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [devMode, setDevMode] = useState(false);

  const stage = (sleepState.stage || 'awake') as Stage;
  const meta = STAGE_META[stage] || STAGE_META.awake;

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [sleepRes, cyclesRes] = await Promise.all([
          fetch('/api/sleep/status'),
          fetch('/api/sleep/consolidations'),
        ]);
        if (sleepRes.ok) {
          const data = await sleepRes.json();
          if (data) {
            setSleepState({
              stage: data.current_stage || 'awake',
              duration: data.stage_duration_seconds || 0,
              cycle_count: data.sleep_cycle_count || 0,
            });
          }
        }
        if (cyclesRes.ok) {
          const data = await cyclesRes.json();
          setCycles(Array.isArray(data) ? data : data.consolidations ?? []);
        }
      } catch {
        // Use mock data on failure
      }
      setLoading(false);
    };
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleForceSleep = async () => {
    try {
      await fetch('/api/sleep/force', { method: 'POST' });
    } catch {
      // Silently fail in dev mode
    }
  };

  const stageDurations = useMemo(() => {
    const counts: Record<Stage, number> = { awake: 0, light: 0, deep: 0, rem: 0 };
    MOCK_STAGE_HISTORY.forEach(h => { counts[h.stage]++; });
    return Object.fromEntries(Object.entries(counts).map(([k, v]) => [k, v * 30])) as Record<Stage, number>;
  }, []);

  const totalSleepMins = stageDurations.light + stageDurations.deep + stageDurations.rem;
  const maxSources = Math.max(...cycles.map(c => c.source_count), 1);

  const pulseSpeed = { awake: '1s', light: '2s', deep: '4s', rem: '1.5s' }[stage] || '2s';

  const stageY: Record<string, number> = { awake: 5, rem: 30, light: 60, deep: 92 };

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: 24 }}>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
          <div>
            <div className="t-h2" style={{ lineHeight: 1 }}>Sleep &amp; Consolidation</div>
            <div className="t-small" style={{ color: 'var(--muted-foreground)', marginTop: 4 }}>Self-regulation and memory optimization cycles.</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn variant="outline" size="icon" onClick={() => {
              setLoading(true);
              Promise.all([
                fetch('/api/sleep/status').then(r => r.json()).catch(() => ({ current_stage: 'awake', stage_duration_seconds: 0, sleep_cycle_count: 0 })),
                fetch('/api/sleep/consolidations').then(r => r.json()).catch(() => []),
              ]).then(([data, d]) => {
                setSleepState({ stage: data.current_stage || 'awake', duration: data.stage_duration_seconds || 0, cycle_count: data.sleep_cycle_count || 0 });
                setCycles(Array.isArray(d) ? d : d.consolidations ?? []);
                setLoading(false);
              });
            }} style={{ opacity: loading ? 0.5 : 1 }}>
              <Icon name="refresh" size={14} style={{ color: 'var(--muted-foreground)' }} />
            </Btn>
            {devMode && (
              <Btn variant="outline" size="sm" onClick={handleForceSleep}>
                Force Sleep
              </Btn>
            )}
            <Btn variant="ghost" size="sm" onClick={() => setDevMode(d => !d)}>
              {devMode ? 'DEV ON' : 'DEV'}
            </Btn>
          </div>
        </div>

        {/* Hero panel */}
        <Card style={{ padding: 0, marginBottom: 24, overflow: 'hidden' }}>
          <div style={{ background: meta.bg, display: 'flex', alignItems: 'center', padding: '36px 40px', gap: 32 }}>
            <div style={{
              width: 88, height: 88, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'var(--background)', border: `2px solid ${meta.color}`,
              fontSize: 36, position: 'relative',
            }}>
              <div style={{
                position: 'absolute', inset: -6, borderRadius: '50%', border: `1px solid ${meta.color}`,
                opacity: 0.3, animation: `pulse-amber ${pulseSpeed} ease-in-out infinite`,
              }} />
              <Icon name={STAGE_ICONS[stage]} size={40} style={{ color: meta.color }} />
            </div>
            <div style={{ flex: 1 }}>
              <div className="t-display" style={{ color: meta.color, marginBottom: 4 }}>{meta.label}</div>
              <div style={{ fontSize: 15, color: 'var(--muted-foreground)', marginBottom: 2 }}>{formatDurationSecs(sleepState.duration)} in this stage</div>
              <div style={{ fontSize: 11, color: 'var(--subtle-foreground)' }}>Next transition estimate: ~18 min</div>
            </div>
            <div style={{ display: 'flex', gap: 24 }}>
              <div style={{ textAlign: 'center' }}>
                <div className="t-label" style={{ color: 'var(--muted-foreground)', marginBottom: 6 }}>CYCLES</div>
                <div className="t-display" style={{ color: 'var(--foreground)' }}>{sleepState.cycle_count}</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div className="t-label" style={{ color: 'var(--muted-foreground)', marginBottom: 6 }}>TOTAL SLEEP</div>
                <div className="t-display" style={{ color: 'var(--foreground)' }}>{Math.floor(totalSleepMins / 60)}h</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div className="t-label" style={{ color: 'var(--muted-foreground)', marginBottom: 6 }}>CONSOLIDATED</div>
                <div className="t-display" style={{ color: 'var(--foreground)' }}>{cycles.reduce((s, c) => s + c.source_count, 0)}</div>
              </div>
            </div>
          </div>
        </Card>

        {/* Stage timeline — hypnogram */}
        <Card style={{ marginBottom: 24, padding: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
            <span className="t-label" style={{ color: 'var(--muted-foreground)' }}>STAGE TIMELINE · LAST 24H</span>
            <div style={{ display: 'flex', gap: 16 }}>
              {STAGES.map(s => (
                <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: 'var(--muted-foreground)' }}>
                  <span style={{ width: 10, height: 10, borderRadius: 3, background: STAGE_META[s].color, display: 'inline-block' }} />
                  {STAGE_META[s].label}
                </div>
              ))}
            </div>
          </div>

          <div style={{ position: 'relative', height: 160, marginBottom: 8 }}>
            <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 64, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', paddingTop: 4, paddingBottom: 4 }}>
              {['awake', 'rem', 'light', 'deep'].map(s => (
                <div key={s} style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase' as const, letterSpacing: '0.1em', color: STAGE_META[s as Stage].color, textAlign: 'right', paddingRight: 8 }}>
                  {s === 'rem' ? 'REM' : s.slice(0, 5).toUpperCase()}
                </div>
              ))}
            </div>

            <div style={{ marginLeft: 68, height: '100%', position: 'relative', borderLeft: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}>
              {[0, 1, 2, 3].map(i => (
                <div key={i} style={{ position: 'absolute', left: 0, right: 0, top: `${(i / 3) * 100}%`, height: 1, background: 'var(--border)', opacity: 0.3 }} />
              ))}

              <svg width="100%" height="100%" viewBox={`0 0 ${MOCK_STAGE_HISTORY.length} 100`} preserveAspectRatio="none" style={{ display: 'block' }}>
                <defs>
                  <linearGradient id="sleepGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={STAGE_META.awake.color} stopOpacity="0.4" />
                    <stop offset="100%" stopColor={STAGE_META.deep.color} stopOpacity="0.1" />
                  </linearGradient>
                </defs>
                <path d={
                  `M 0 100 ` +
                  MOCK_STAGE_HISTORY.map((h, i) => `L ${i} ${stageY[h.stage]}`).join(' ') +
                  ` L ${MOCK_STAGE_HISTORY.length - 1} 100 Z`
                } fill="url(#sleepGrad)" />
                {MOCK_STAGE_HISTORY.map((h, i) => {
                  if (i === 0) return null;
                  const prev = MOCK_STAGE_HISTORY[i - 1];
                  return (
                    <line key={i} x1={i - 1} y1={stageY[prev.stage]} x2={i} y2={stageY[h.stage]}
                      stroke={STAGE_META[h.stage].color} strokeWidth="1.5" strokeLinecap="round" />
                  );
                })}
                {MOCK_STAGE_HISTORY.map((h, i) => (
                  <circle key={i} cx={i} cy={stageY[h.stage]} r="0.8" fill={STAGE_META[h.stage].color} />
                ))}
              </svg>
            </div>
          </div>

          <div style={{ marginLeft: 68, display: 'flex', justifyContent: 'space-between' }}>
            {[0, 4, 8, 12, 16, 20, 24].map(h => (
              <span key={h} style={{ fontSize: 9, color: 'var(--subtle-foreground)' }}>{String(h).padStart(2, '0')}:00</span>
            ))}
          </div>

          <div style={{ marginTop: 20, display: 'flex', gap: 12, marginLeft: 68 }}>
            {STAGES.map(s => {
              const mins = stageDurations[s];
              const pct = (mins / (24 * 60)) * 100;
              return (
                <div key={s} style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 9, fontWeight: 700, color: STAGE_META[s].color, textTransform: 'uppercase' as const, letterSpacing: '0.1em' }}>{STAGE_META[s].label}</span>
                    <span style={{ fontSize: 10, color: 'var(--muted-foreground)', fontWeight: 600 }}>{Math.floor(mins / 60)}h {mins % 60}m</span>
                  </div>
                  <div style={{ height: 6, background: 'var(--surface-tertiary)', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${pct}%`, background: STAGE_META[s].color, borderRadius: 3, opacity: 0.7, transition: 'width 500ms ease' }} />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        {/* Consolidation cycles bar chart */}
        <Card style={{ marginBottom: 24, padding: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
            <span className="t-label" style={{ color: 'var(--muted-foreground)' }}>CONSOLIDATION CYCLES · SOURCES PROCESSED</span>
            <span style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>{cycles.length} cycles total</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 140, marginBottom: 16 }}>
            {cycles.map(c => {
              const pct = (c.source_count / maxSources) * 100;
              const isExpanded = expanded === c.id;
              return (
                <div key={c.id} onClick={() => setExpanded(isExpanded ? null : c.id)}
                  style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: isExpanded ? 'var(--primary)' : 'var(--foreground)' }}>{c.source_count}</span>
                  <div style={{
                    width: '100%', maxWidth: 48, height: `${pct}%`, minHeight: 8,
                    background: isExpanded ? 'var(--primary)' : 'var(--accent)',
                    opacity: isExpanded ? 0.9 : 0.5,
                    borderRadius: '4px 4px 0 0', transition: 'all 200ms ease',
                    position: 'relative',
                  }}>
                    {c.created ? (
                      <div style={{
                        position: 'absolute', top: -2, left: '50%', transform: 'translate(-50%, -100%)',
                        fontSize: 8, fontWeight: 700, color: 'var(--success)', opacity: 0.7,
                      }}>+{c.created}</div>
                    ) : null}
                  </div>
                  <span style={{ fontSize: 8, color: 'var(--subtle-foreground)', fontWeight: 600, textTransform: 'uppercase' as const }}>
                    {c.scope.split('→')[0].trim().slice(0, 4)}
                  </span>
                  <span style={{ fontSize: 8, color: 'var(--subtle-foreground)' }}>{formatRelativeSecs(c.consolidated_at)}</span>
                </div>
              );
            })}
          </div>

          {expanded && (() => {
            const c = cycles.find(x => x.id === expanded);
            if (!c) return null;
            return (
              <div style={{
                background: 'var(--surface-secondary)', borderRadius: 'var(--radius)', padding: 16,
                border: '1px solid var(--border)', animation: 'fadeIn 200ms ease',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Pill color="var(--accent)" bg="oklch(0.70 0.18 280 / 0.1)" border="oklch(0.70 0.18 280 / 0.3)" style={{ fontSize: 9 }}>{c.scope}</Pill>
                    <span style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>{formatTimestampSecs(c.consolidated_at)}</span>
                  </div>
                  <Btn variant="ghost" size="icon" onClick={() => setExpanded(null)}>
                    <Icon name="x" size={12} />
                  </Btn>
                </div>
                <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--foreground)', marginBottom: 12 }}>{c.summary}</div>
                <div style={{ display: 'flex', gap: 24 }}>
                  <div style={{ fontSize: 11 }}>
                    <span style={{ color: 'var(--muted-foreground)' }}>Sources: </span>
                    <span style={{ fontWeight: 700 }}>{c.source_count}</span>
                  </div>
                  <div style={{ fontSize: 11 }}>
                    <span style={{ color: 'var(--muted-foreground)' }}>Created: </span>
                    <span style={{ fontWeight: 700, color: 'var(--success)' }}>+{c.created}</span>
                  </div>
                  <div style={{ fontSize: 11 }}>
                    <span style={{ color: 'var(--muted-foreground)' }}>Duration: </span>
                    <span style={{ fontWeight: 700 }}>{c.duration}s</span>
                  </div>
                </div>
              </div>
            );
          })()}
        </Card>

        {/* Consolidation history feed */}
        <div>
          <div className="t-label" style={{ color: 'var(--muted-foreground)', marginBottom: 12 }}>CONSOLIDATION HISTORY</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {cycles.map(c => (
              <Card key={c.id} hover onClick={() => setExpanded(expanded === c.id ? null : c.id)}
                style={{ padding: 16, cursor: 'pointer', borderLeft: expanded === c.id ? '2px solid var(--accent)' : '2px solid transparent' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1 }}>
                    <Pill color="var(--accent)" bg="oklch(0.70 0.18 280 / 0.08)" border="oklch(0.70 0.18 280 / 0.25)" style={{ fontSize: 9 }}>
                      {c.scope}
                    </Pill>
                    <div style={{ display: 'flex', gap: 16, fontSize: 11, color: 'var(--muted-foreground)' }}>
                      <span><strong style={{ color: 'var(--foreground)' }}>{c.source_count}</strong> sources</span>
                      <span><strong style={{ color: 'var(--success)' }}>+{c.created}</strong> created</span>
                      <span>{c.duration}s</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 10, color: 'var(--subtle-foreground)' }}>{formatRelativeSecs(c.consolidated_at)}</span>
                    <Icon name={expanded === c.id ? 'chevronDown' : 'chevronRight'} size={12} style={{ color: 'var(--subtle-foreground)' }} />
                  </div>
                </div>
                {expanded === c.id && (
                  <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--foreground)', borderTop: '1px solid var(--border)', paddingTop: 12, marginTop: 12 }}>
                    {c.summary}
                  </div>
                )}
              </Card>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SleepPage;
