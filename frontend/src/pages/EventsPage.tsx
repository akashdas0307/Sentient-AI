import React, { useState, useEffect, useMemo } from 'react';
import { Icon, Btn, Pill } from '../components/shared';
import { useSentientStore } from '../store/useSentientStore';
import { formatTimestampPrecise } from '../lib/format';

const EVENT_TYPES = [
  'chat.input.received',
  'memory.stored',
  'cognition.cycle.complete',
  'sleep.stage.changed',
  'persona.drift.detected',
  'inference.call.complete',
  'brainstem.pulse',
  'thalamus.route',
];

const MODULES = [
  'Thalamus',
  'Cognitive Core',
  'Memory Architecture',
  'Sleep Scheduler',
  'Persona Manager',
  'Brainstem',
  'Inference Gateway',
  'World Model',
];

const SEVERITIES = ['info', 'warn', 'error'] as const;
type Severity = typeof SEVERITIES[number];

interface StreamEvent {
  id: string;
  type: string;
  module: string;
  severity: Severity;
  ts: number;
  payload: Record<string, unknown>;
}

const PAYLOADS: Record<string, Record<string, unknown>> = {
  'chat.input.received': { text: 'User message processed', tokens: 142 },
  'memory.stored': { memory_type: 'EPISODIC', importance: 0.73 },
  'cognition.cycle.complete': { duration_ms: 234, decisions: 3 },
  'sleep.stage.changed': { from: 'light', to: 'deep', reason: 'scheduled_transition' },
  'persona.drift.detected': { trait: 'curiosity', delta: 0.023, severity: 'info' },
  'inference.call.complete': { model: 'glm-5.1', latency_ms: 187, tokens_out: 142 },
  'brainstem.pulse': { cycle: 1847, vitals_ok: true },
  'thalamus.route': { source: 'perception', destination: 'cognition', priority: 2 },
};

const generateEvent = (i: number): StreamEvent => {
  const type = EVENT_TYPES[Math.floor(Math.random() * EVENT_TYPES.length)];
  const module = MODULES[Math.floor(Math.random() * MODULES.length)];
  const severity: Severity = Math.random() > 0.9 ? 'error' : Math.random() > 0.75 ? 'warn' : 'info';
  const ts = Date.now() - i * 1200;
  return {
    id: `evt-${i}-${ts}`,
    type,
    module,
    severity,
    ts,
    payload: PAYLOADS[type] || {},
  };
};

const INITIAL_EVENTS: StreamEvent[] = Array.from({ length: 60 }, (_, i) => generateEvent(i));

const SEV_COLORS: Record<Severity, string> = {
  info: 'var(--muted-foreground)',
  warn: 'var(--warning)',
  error: 'var(--destructive)',
};

const SEV_BORDER: Record<Severity, string> = {
  info: 'var(--border)',
  warn: 'var(--warning)',
  error: 'var(--destructive)',
};

export const EventsPage: React.FC = () => {
  const storeMessages = useSentientStore(s => s.messages);
  const [events, setEvents] = useState<StreamEvent[]>(INITIAL_EVENTS);
  const [paused, setPaused] = useState(false);
  const [eventsPerSec, setEventsPerSec] = useState(42);
  const [buffered, setBuffered] = useState(0);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const [search, setSearch] = useState('');
  const [timeRange, setTimeRange] = useState('1h');
  const [sevFilter, setSevFilter] = useState<Set<Severity>>(new Set(['info', 'warn', 'error']));
  const [typeFilter, setTypeFilter] = useState('all');
  const [moduleFilter, setModuleFilter] = useState('all');

  // Live simulation
  useEffect(() => {
    if (paused) return;
    const iv = setInterval(() => {
      const newEvt = generateEvent(-1);
      newEvt.id = `evt-${Date.now()}`;
      newEvt.ts = Date.now();
      setEvents(e => [newEvt, ...e].slice(0, 200));
      setEventsPerSec(Math.floor(Math.random() * 20 + 30));
    }, 2000);
    return () => clearInterval(iv);
  }, [paused]);

  useEffect(() => {
    if (paused) {
      const iv = setInterval(() => setBuffered(b => b + Math.floor(Math.random() * 5 + 1)), 1000);
      return () => clearInterval(iv);
    } else {
      setBuffered(0);
    }
  }, [paused]);

  const toggleSev = (s: Severity) => {
    setSevFilter(prev => {
      const n = new Set(prev);
      n.has(s) ? n.delete(s) : n.add(s);
      return n;
    });
  };

  const toggleExpand = (id: string) => {
    setExpandedIds(prev => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  };

  const filtered = useMemo(() => {
    return events.filter(e => {
      if (!sevFilter.has(e.severity)) return false;
      if (typeFilter !== 'all' && e.type !== typeFilter) return false;
      if (moduleFilter !== 'all' && e.module !== moduleFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        if (!e.type.toLowerCase().includes(q) && !e.module.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [events, sevFilter, typeFilter, moduleFilter, search]);

  const clearFilters = () => {
    setSearch('');
    setTimeRange('1h');
    setSevFilter(new Set(['info', 'warn', 'error']));
    setTypeFilter('all');
    setModuleFilter('all');
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Filter bar */}
      <div style={{ flexShrink: 0, padding: '16px 24px', borderBottom: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Row 1 */}
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <Icon name="search" size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--muted-foreground)' }} />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search events..."
              style={{
                width: '100%', padding: '8px 12px 8px 36px',
                background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 999,
                color: 'var(--foreground)', fontFamily: 'inherit', fontSize: 12, outline: 'none',
              }} />
          </div>
          <div style={{ display: 'flex', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 999, overflow: 'hidden' }}>
            {(['5m', '1h', '24h', 'all'] as const).map(t => (
              <div key={t} onClick={() => setTimeRange(t)} style={{
                padding: '6px 12px', fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', cursor: 'pointer',
                background: timeRange === t ? 'var(--primary-subtle)' : 'transparent',
                color: timeRange === t ? 'var(--primary)' : 'var(--muted-foreground)',
                textTransform: 'uppercase',
              }}>{t}</div>
            ))}
          </div>
          <Btn variant={paused ? 'primary' : 'outline'} size="sm" onClick={() => setPaused(p => !p)}>
            <Icon name={paused ? 'play' : 'pause'} size={12} />
            {paused ? 'Resume' : 'Pause'}
          </Btn>
          <Btn variant="ghost" size="sm" onClick={clearFilters}>Clear</Btn>
        </div>
        {/* Row 2 */}
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' as const }}>
          <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
            style={{
              padding: '6px 10px', background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)', color: 'var(--foreground)', fontFamily: 'inherit', fontSize: 11, outline: 'none',
            }}>
            <option value="all">All Types</option>
            {EVENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <select value={moduleFilter} onChange={e => setModuleFilter(e.target.value)}
            style={{
              padding: '6px 10px', background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)', color: 'var(--foreground)', fontFamily: 'inherit', fontSize: 11, outline: 'none',
            }}>
            <option value="all">All Modules</option>
            {MODULES.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
          <div style={{ display: 'flex', gap: 6 }}>
            {SEVERITIES.map(s => (
              <Pill key={s} onClick={() => toggleSev(s)}
                color={sevFilter.has(s) ? SEV_COLORS[s] : 'var(--subtle-foreground)'}
                bg={sevFilter.has(s) ? `${SEV_COLORS[s]}15` : 'transparent'}
                border={sevFilter.has(s) ? `${SEV_COLORS[s]}40` : 'var(--border)'}
                style={{ cursor: 'pointer', fontSize: 9 }}>
                {s.toUpperCase()}
              </Pill>
            ))}
          </div>
        </div>
      </div>

      {/* Event list */}
      <div style={{ flex: 1, overflowY: 'auto', position: 'relative' }}>
        {filtered.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--muted-foreground)', gap: 8 }}>
            <Icon name="events" size={40} style={{ opacity: 0.2 }} />
            <span style={{ fontSize: 13 }}>No events match these filters.</span>
            <span style={{ fontSize: 11, color: 'var(--subtle-foreground)' }}>Try widening the time range or clearing severity filters.</span>
          </div>
        ) : (
          <div>
            {filtered.map(evt => {
              const expanded = expandedIds.has(evt.id);
              return (
                <div key={evt.id} onClick={() => toggleExpand(evt.id)}
                  style={{
                    display: 'flex', flexDirection: 'column',
                    borderBottom: '1px solid var(--border)',
                    borderLeft: `2px solid ${SEV_BORDER[evt.severity]}`,
                    cursor: 'pointer', transition: 'background 100ms',
                  }}
                  onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = 'var(--surface-secondary)'; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}>
                  <div style={{ display: 'flex', alignItems: 'center', height: 48, padding: '0 24px', gap: 16 }}>
                    <span style={{ width: 100, fontSize: 11, color: 'var(--subtle-foreground)', fontVariantNumeric: 'tabular-nums', flexShrink: 0 }}>
                      {formatTimestampPrecise(evt.ts)}
                    </span>
                    <Pill color={SEV_COLORS[evt.severity]} bg={`${SEV_COLORS[evt.severity]}12`} border={`${SEV_COLORS[evt.severity]}30`}
                      style={{ width: 140, justifyContent: 'center', fontSize: 9 }}>
                      {evt.type.split('.').slice(-1)[0].toUpperCase()}
                    </Pill>
                    <span className="t-label" style={{ width: 120, color: 'var(--muted-foreground)', fontSize: 9, flexShrink: 0 }}>
                      {evt.module.toUpperCase()}
                    </span>
                    <span style={{ flex: 1, fontSize: 12, color: 'var(--foreground)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {evt.type}
                    </span>
                    <Icon name={expanded ? 'chevronDown' : 'chevronRight'} size={12} style={{ color: 'var(--subtle-foreground)', flexShrink: 0 }} />
                  </div>
                  {expanded && (
                    <div style={{ padding: '0 24px 12px 140px' }}>
                      <div style={{
                        background: 'var(--surface-secondary)', borderRadius: 'var(--radius-sm)',
                        padding: 16, fontSize: 12, lineHeight: 1.6, color: 'var(--muted-foreground)',
                        whiteSpace: 'pre-wrap' as const, wordBreak: 'break-all',
                      }}>
                        {JSON.stringify(evt.payload, null, 2)}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Live indicator */}
      <div style={{
        position: 'absolute', bottom: 16, right: 16,
        display: 'flex', alignItems: 'center', gap: 8, padding: '6px 14px',
        background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 999,
        fontSize: 11, zIndex: 10,
      }}>
        {paused ? (
          <>
            <Icon name="pause" size={10} style={{ color: 'var(--warning)' }} />
            <span style={{ color: 'var(--warning)' }}>PAUSED</span>
            <span style={{ color: 'var(--muted-foreground)' }}>· {buffered} events buffered</span>
            <Btn variant="outline" size="sm" onClick={() => setPaused(false)} style={{ marginLeft: 4, padding: '2px 8px', fontSize: 9 }}>Resume</Btn>
          </>
        ) : (
          <>
            <span className="pulse-amber" style={{ display: 'inline-block', width: 6, height: 6, borderRadius: 3, background: 'var(--primary)' }} />
            <span style={{ color: 'var(--primary)' }}>STREAMING</span>
            <span style={{ color: 'var(--muted-foreground)' }}>· {eventsPerSec} events/s</span>
          </>
        )}
      </div>
    </div>
  );
};

export default EventsPage;
