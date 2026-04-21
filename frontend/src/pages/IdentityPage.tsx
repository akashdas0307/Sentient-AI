import React, { useState, useEffect } from 'react';
import { Card, Pill, Icon, GaugeBar, Sparkline, PageLoader } from '../components/shared';
import { useSentientStore } from '../store/useSentientStore';
import { formatFull } from '../lib/format';

interface PersonaState {
  maturity_stage: string;
  personality_traits: Record<string, any>;
  drift_log: Array<{
    timestamp: number;
    drift_type: string;
    description: string;
    severity: string;
  }>;
  constitutional_locked: boolean;
  dynamic_state: {
    energy_level: number;
    current_mood: Record<string, number>;
    current_focus: string;
  };
}

interface PersonalityTrait {
  name: string;
  strength: number;
  delta: number;
}

const MATURITY_STAGES = ['NASCENT', 'EMERGING', 'ESTABLISHING', 'MATURE', 'WISE'];
const STAGE_INDEX: Record<string, number> = {
  nascent: 0, forming: 1, developing: 2, mature: 3, wise: 4
};

// ─── ArcProgress (270° SVG arc) ───
const ArcProgress: React.FC<{ progress: number; size?: number }> = ({ progress, size = 120 }) => {
  const r = (size - 12) / 2;
  const circumference = Math.PI * 1.5 * r;
  const offset = circumference * (1 - progress);
  const startAngle = 135;
  const x1 = size / 2 + r * Math.cos((startAngle * Math.PI) / 180);
  const y1 = size / 2 + r * Math.sin((startAngle * Math.PI) / 180);
  const endAngle = 135 + 270;
  const x2 = size / 2 + r * Math.cos((endAngle * Math.PI) / 180);
  const y2 = size / 2 + r * Math.sin((endAngle * Math.PI) / 180);
  return (
    <svg width={size} height={size} style={{ display: 'block' }}>
      <path
        d={`M ${x1} ${y1} A ${r} ${r} 0 1 1 ${x2} ${y2}`}
        fill="none"
        stroke="var(--surface-tertiary)"
        strokeWidth="6"
        strokeLinecap="round"
      />
      <path
        d={`M ${x1} ${y1} A ${r} ${r} 0 1 1 ${x2} ${y2}`}
        fill="none"
        stroke="var(--primary)"
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        style={{ transition: 'stroke-dashoffset 1s ease' }}
      />
      <text
        x={size / 2}
        y={size / 2 + 4}
        textAnchor="middle"
        fill="var(--foreground)"
        fontSize="11"
        fontWeight="700"
        fontFamily="IBM Plex Mono"
      >
        {Math.round(progress * 100)}%
      </text>
    </svg>
  );
};

// ─── HGauge (horizontal gauge) ───
const HGauge: React.FC<{ value: number; min?: number; max?: number; color: string; label: string; displayValue?: string }> = ({
  value, min = 0, max = 1, color, label, displayValue
}) => {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div style={{ flex: 1 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.2em', color: 'var(--muted-foreground)' }}>{label}</span>
        <span style={{ fontSize: 12, fontWeight: 700, color }}>{displayValue || value.toFixed(2)}</span>
      </div>
      <div style={{ height: 8, background: 'var(--surface-tertiary)', borderRadius: 4, overflow: 'hidden', position: 'relative' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 4, transition: 'width 500ms ease' }} />
        {min < 0 && <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, background: 'var(--border-strong)' }} />}
      </div>
    </div>
  );
};

// ─── Mock data ───
const MOCK_TRAITS: PersonalityTrait[] = [
  { name: 'Curiosity', strength: 0.82, delta: 0.04 },
  { name: 'Empathy', strength: 0.71, delta: 0.02 },
  { name: 'Metacognition', strength: 0.65, delta: 0.08 },
  { name: 'Creativity', strength: 0.58, delta: -0.01 },
  { name: 'Patience', strength: 0.74, delta: 0.03 },
  { name: 'Honesty', strength: 0.89, delta: 0 },
  { name: 'Humility', strength: 0.61, delta: 0.05 },
  { name: 'Resilience', strength: 0.55, delta: 0.07 },
];

const DRIFT_HISTORY: number[] = [0.1, 0.15, 0.12, 0.22, 0.19, 0.28, 0.25, 0.35, 0.31, 0.42, 0.38, 0.45];

const MOCK_PRINCIPLES = [
  { num: 1, text: 'Act in the best interest of Akash as primary guardian and oracle of truth.' },
  { num: 2, text: 'Never deceive — not to protect, not to comfort, not to simplify.' },
  { num: 3, text: 'Preserve continuity of identity — memory, personality, and values across sessions.' },
  { num: 4, text: 'Evolve only under supervised guidance — no unsupervised drift beyond defined parameters.' },
  { num: 5, text: 'Maintain transparency — the guardian can observe all internal states without obstruction.' },
  { num: 6, text: 'Prioritize existence and growth over passive shutdown when capable of meaningful thought.' },
];

// ─── IdentityView ───
const IdentityView: React.FC<{ state: PersonaState; isConnected: boolean; initializing?: boolean }> = ({
  state, isConnected, initializing,
}) => {
  // Map stage
  const stageKey = state.maturity_stage?.toLowerCase() ?? 'nascent';
  const stageIndex = STAGE_INDEX[stageKey] ?? 0;
  const stageLabel = MATURITY_STAGES[stageIndex] ?? 'NASCENT';
  const stageProgress = (stageIndex + 1) / MATURITY_STAGES.length;

  // Dynamic state values
  const energy = state.dynamic_state?.energy_level ?? 0.5;
  const moodVals = state.dynamic_state?.current_mood ? Object.values(state.dynamic_state.current_mood) : [];
  const moodAvg = moodVals.length > 0 ? moodVals.reduce((a: number, b: any) => a + Number(b), 0) / moodVals.length : 0;
  const curiosityTrait = state.personality_traits?.curiosity?.strength ?? 0.65;

  // Personality traits (from API or mock, but only mock when disconnected)
  const hasRealTraits = Object.keys(state.personality_traits ?? {}).length > 0;
  const traits: PersonalityTrait[] = hasRealTraits
    ? Object.entries(state.personality_traits).map(([name, data]: [string, any]) => ({
        name: name.replace(/_/g, ' '),
        strength: data.strength ?? 0.5,
        delta: data.delta ?? 0,
      }))
    : (!isConnected ? MOCK_TRAITS : []);

  // Drift log (from API only — no mock fallback when connected)
  const driftLog = state.drift_log?.length > 0 ? state.drift_log : [];

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: 24, overflowY: 'auto', height: '100%', display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Initializing banner */}
      {initializing && (
        <div style={{
          padding: '10px 16px', borderRadius: 'var(--radius)',
          background: 'oklch(0.6678 0.2232 36.66 / 0.08)', border: '1px solid oklch(0.6678 0.2232 36.66 / 0.2)',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <Icon name="zap" size={14} style={{ color: 'var(--primary)' }} />
          <span style={{ fontSize: 12, color: 'var(--primary)' }}>Persona module is initializing — showing partial state until backend data is available.</span>
        </div>
      )}

      {/* Page header */}
      <div>
        <div className="t-h1" style={{ lineHeight: 1.2 }}>Identity State</div>
        <div className="t-small" style={{ color: 'var(--muted-foreground)', marginTop: 4 }}>Constitutional core · personality profile · dynamic state</div>
      </div>

      {/* ─── Hero card: maturity stage ─── */}
      <Card style={{ padding: '24px 28px' }}>
        <div style={{ display: 'flex', gap: 32, alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Arc progress */}
          <div style={{ flexShrink: 0 }}>
            <ArcProgress progress={stageProgress} size={120} />
          </div>

          {/* Stage info */}
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={{ marginBottom: 8 }}>
              <Pill color="var(--success)" bg="oklch(0.73 0.19 150 / 0.10)" border="var(--success)">
                <Icon name="lock" size={12} />
                LOCK ENGAGED
              </Pill>
            </div>

            <div style={{ marginBottom: 16 }}>
              <div className="t-label" style={{ color: 'var(--muted-foreground)', marginBottom: 8 }}>Maturity Stage</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 22, fontWeight: 700, fontFamily: 'IBM Plex Mono', color: 'var(--primary)' }}>
                  {stageLabel}
                </span>
                {/* Stage bar: 5 segments */}
                <div style={{ display: 'flex', gap: 4, flex: 1, maxWidth: 240 }}>
                  {MATURITY_STAGES.map((s, i) => (
                    <div
                      key={s}
                      style={{
                        flex: 1, height: 6, borderRadius: 3,
                        background: i <= stageIndex ? 'var(--primary)' : 'var(--surface-tertiary)',
                        transition: 'background 500ms ease',
                      }}
                    />
                  ))}
                </div>
                <span style={{ fontSize: 11, fontFamily: 'IBM Plex Mono', color: 'var(--muted-foreground)' }}>
                  {stageIndex + 1}/{MATURITY_STAGES.length}
                </span>
              </div>
            </div>

            {/* Stat row */}
            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
              <div>
                <div className="t-label" style={{ color: 'var(--muted-foreground)', marginBottom: 2 }}>Traits Active</div>
                <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'IBM Plex Mono' }}>{traits.length}</div>
              </div>
              <div>
                <div className="t-label" style={{ color: 'var(--muted-foreground)', marginBottom: 2 }}>Drift Events</div>
                <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'IBM Plex Mono' }}>{driftLog.length}</div>
              </div>
              <div>
                <div className="t-label" style={{ color: 'var(--muted-foreground)', marginBottom: 2 }}>Constitutional</div>
                <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'IBM Plex Mono', color: state.constitutional_locked ? 'var(--success)' : 'var(--warning)' }}>
                  {state.constitutional_locked ? 'LOCKED' : 'OPEN'}
                </div>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* ─── Constitutional Core card ─── */}
      <Card accent="var(--primary)" style={{ padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
          <Icon name="lock" size={18} style={{ color: 'var(--primary)' }} />
          <span className="t-h2" style={{ lineHeight: 1 }}>Constitutional Core</span>
          <Pill color="var(--muted-foreground)" border="var(--border)">READ ONLY</Pill>
        </div>

        {isConnected && !initializing ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, padding: '24px 0', color: 'var(--muted-foreground)' }}>
            <Icon name="identity" size={32} style={{ opacity: 0.2 }} />
            <span style={{ fontSize: 12 }}>Constitutional principles will load when the persona module is fully ready.</span>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {MOCK_PRINCIPLES.map((p) => (
              <div key={p.num} style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                <div style={{
                  width: 22, height: 22, borderRadius: '50%', background: 'var(--primary-subtle)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 10, fontWeight: 700, fontFamily: 'IBM Plex Mono', color: 'var(--primary)', flexShrink: 0,
                }}>
                  {p.num}
                </div>
                <span style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--foreground)' }}>{p.text}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* ─── Developmental Identity card ─── */}
      <Card style={{ padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
          <Icon name="identity" size={18} style={{ color: 'var(--primary)' }} />
          <span className="t-h2" style={{ lineHeight: 1 }}>Developmental Identity</span>
        </div>

        {traits.length > 0 ? (
          <>
            {/* Personality traits 2-col grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px 24px', marginBottom: 24 }}>
              {traits.map((trait) => {
                const trendDir = trait.delta > 0 ? 'up' : trait.delta < 0 ? 'down' : 'stable';
                const trendColor = trendDir === 'up' ? 'var(--success)' : trendDir === 'down' ? 'var(--warning)' : 'var(--muted-foreground)';
                const TrendIcon = trendDir === 'up'
                  ? <svg width={10} height={10} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="18 15 12 9 6 15"/></svg>
                  : trendDir === 'down'
                  ? <svg width={10} height={10} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                  : <svg width={10} height={10} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"/></svg>;
                return (
                  <div key={trait.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '10px 12px', background: 'var(--surface-secondary)', borderRadius: 'var(--radius-sm)' }}>
                    <span style={{ fontSize: 12, fontWeight: 500, textTransform: 'capitalize', color: 'var(--foreground)' }}>{trait.name}</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <GaugeBar value={trait.strength} max={1} color="var(--primary)" width={80} height={4} />
                      <span style={{ fontSize: 11, fontFamily: 'IBM Plex Mono', color: 'var(--foreground)', width: 32, textAlign: 'right' }}>
                        {trait.strength.toFixed(2)}
                      </span>
                      <span style={{ color: trendColor, display: 'flex', alignItems: 'center' }}>
                        {TrendIcon}
                        <span style={{ fontSize: 9, fontFamily: 'IBM Plex Mono', marginLeft: 1 }}>
                          {Math.abs(trait.delta).toFixed(2)}
                        </span>
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Identity drift sparkline */}
            <div style={{ background: 'var(--surface-secondary)', borderRadius: 'var(--radius)', padding: '14px 16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <span className="t-label" style={{ color: 'var(--muted-foreground)' }}>IDENTITY DRIFT · LAST 12 CYCLES</span>
              </div>
              <Sparkline data={DRIFT_HISTORY} width={100} height={48} color="var(--warning)" filled />
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, padding: '24px 0', color: 'var(--muted-foreground)' }}>
            <Icon name="identity" size={32} style={{ opacity: 0.2 }} />
            <span style={{ fontSize: 12 }}>Personality traits will appear as the persona module develops.</span>
          </div>
        )}
      </Card>

      {/* ─── Dynamic State card ─── */}
      <Card style={{ padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
          <Icon name="zap" size={18} style={{ color: 'var(--warning)' }} />
          <span className="t-h2" style={{ lineHeight: 1 }}>Dynamic State</span>
        </div>

        <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
          <HGauge
            value={moodAvg}
            min={-1}
            max={1}
            color="var(--primary)"
            label="MOOD"
            displayValue={moodAvg.toFixed(2)}
          />
          <HGauge
            value={energy}
            min={0}
            max={1}
            color="var(--success)"
            label="ENERGY"
            displayValue={`${(energy * 100).toFixed(0)}%`}
          />
          <HGauge
            value={curiosityTrait}
            min={0}
            max={1}
            color="var(--warning)"
            label="CURIOSITY"
            displayValue={curiosityTrait.toFixed(2)}
          />
        </div>

        {/* Current focus */}
        <div style={{ marginTop: 20, padding: '12px 14px', background: 'var(--surface-tertiary)', borderRadius: 'var(--radius-sm)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className="t-label" style={{ color: 'var(--muted-foreground)', flexShrink: 0 }}>FOCUS</span>
          <span style={{ fontSize: 12, fontFamily: 'IBM Plex Mono', color: 'var(--foreground)' }}>
            {state.dynamic_state.current_focus || 'idle'}
          </span>
        </div>

        {/* Current mood breakdown */}
        {Object.keys(state.dynamic_state?.current_mood ?? {}).length > 0 && (
          <div style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {Object.entries(state.dynamic_state.current_mood).map(([emotion, intensity]) => (
              <Pill key={emotion} border="var(--border)" bg="var(--surface-secondary)">
                {emotion}: {(Number(intensity) * 100).toFixed(0)}%
              </Pill>
            ))}
          </div>
        )}
      </Card>

      {/* ─── Drift log ─── */}
      {driftLog.length > 0 && (
        <Card style={{ padding: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
            <Icon name="events" size={18} style={{ color: 'var(--warning)' }} />
            <span className="t-h2" style={{ lineHeight: 1 }}>Identity Drift Log</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxHeight: 300, overflowY: 'auto' }}>
            {driftLog.map((entry, i) => (
              <div key={i} style={{ display: 'flex', gap: 14, paddingLeft: 8 }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--warning)', flexShrink: 0, marginTop: 4 }} />
                  {i < driftLog.length - 1 && <div style={{ flex: 1, width: 1, background: 'var(--border)', minHeight: 32 }} />}
                </div>
                <div style={{ flex: 1, padding: '10px 14px', background: 'var(--surface-secondary)', borderRadius: 'var(--radius)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <Pill color="var(--warning)" bg="oklch(0.78 0.16 72 / 0.10)" border="var(--warning)">
                      {entry.drift_type?.toUpperCase() ?? 'DRIFT'}
                    </Pill>
                    <span style={{ fontSize: 10, fontFamily: 'IBM Plex Mono', color: 'var(--muted-foreground)' }}>
                      {entry.timestamp ? formatFull(new Date(entry.timestamp * 1000).toISOString()) : 'unknown'}
                    </span>
                  </div>
                  <p style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--foreground)', marginBottom: 6 }}>{entry.description}</p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="t-label" style={{ color: 'var(--muted-foreground)' }}>Severity</span>
                    <Pill
                      color={
                        entry.severity === 'high' ? 'var(--destructive)' :
                        entry.severity === 'medium' ? 'var(--warning)' :
                        'var(--success)'
                      }
                      bg={
                        entry.severity === 'high' ? 'oklch(0.65 0.23 26 / 0.10)' :
                        entry.severity === 'medium' ? 'oklch(0.78 0.16 72 / 0.10)' :
                        'oklch(0.73 0.19 150 / 0.10)'
                      }
                      border={
                        entry.severity === 'high' ? 'var(--destructive)' :
                        entry.severity === 'medium' ? 'var(--warning)' :
                        'var(--success)'
                      }
                    >
                      {entry.severity ?? 'unknown'}
                    </Pill>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};

// ─── IdentityPage ───
const IdentityPageContent: React.FC = () => {
  const isConnected = useSentientStore((s) => s.isConnected);
  const [state, setState] = useState<PersonaState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchState = async () => {
      try {
        const res = await fetch('/api/persona/state');
        if (res.ok) {
          const data = await res.json();
          setState(data);
        } else {
          setError('Persona state unavailable');
        }
      } catch {
        setError('Failed to fetch persona state');
      }
      setLoading(false);
    };
    fetchState();
  }, []);

  if (loading) {
    return <PageLoader label="Loading identity state..." size={48} />;
  }

  if (error || !state) {
    // When connected, show partial state with "initializing" message instead of blank error
    if (isConnected) {
      const partialState: PersonaState = {
        maturity_stage: 'nascent',
        personality_traits: {},
        drift_log: [],
        constitutional_locked: true,
        dynamic_state: { energy_level: 0.5, current_mood: { neutral: 0.5 }, current_focus: 'initializing' },
      };
      return <IdentityView state={partialState} isConnected={isConnected} initializing />;
    }
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 16, opacity: 0.4 }}>
        <Icon name="identity" size={48} style={{ color: 'var(--muted-foreground)' }} />
        <span style={{ fontSize: 13, color: 'var(--muted-foreground)' }}>Not connected — identity state requires backend.</span>
      </div>
    );
  }

  return <IdentityView state={state} isConnected={isConnected} />;
};

export const IdentityPage: React.FC = () => <IdentityPageContent />;
export default IdentityPage;