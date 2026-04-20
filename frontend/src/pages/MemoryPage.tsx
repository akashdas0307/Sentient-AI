import React, { useState, useEffect, useMemo } from 'react';
import { Icon, Btn, Card, Pill, GaugeBar, StatCard } from '../components/shared';
import { useSentientStore } from '../store/useSentientStore';
import { formatRelative, formatFull } from '../lib/format';

// ─── Types ───────────────────────────────────────────────────────────────────
interface MemoryEntry {
  id: string;
  memory_type?: string;
  type?: string;
  content?: string;
  text?: string;
  summary?: string;
  importance?: number;
  confidence?: number;
  entity_tags?: string[];
  topic_tags?: string[];
  created_at?: string;
  timestamp?: string;
  tags?: string[];
  [key: string]: unknown;
}

// ─── Constants ────────────────────────────────────────────────────────────────
const MEM_TYPES = ['EPISODIC', 'SEMANTIC', 'PROCEDURAL', 'EMOTIONAL'] as const;

const TYPE_COLORS: Record<string, string> = {
  EPISODIC: 'var(--primary)',
  SEMANTIC: 'var(--accent)',
  PROCEDURAL: 'var(--success)',
  EMOTIONAL: 'var(--warning)',
};

const TYPE_BG: Record<string, string> = {
  EPISODIC: 'oklch(0.6678 0.2232 36.66 / 0.08)',
  SEMANTIC: 'oklch(0.6274 0.1948 293.342 / 0.08)',
  PROCEDURAL: 'oklch(0.6274 0.1948 145.542 / 0.08)',
  EMOTIONAL: 'oklch(0.6274 0.1948 85 / 0.08)',
};

const TYPE_BORDER: Record<string, string> = {
  EPISODIC: 'oklch(0.6678 0.2232 36.66 / 0.2)',
  SEMANTIC: 'oklch(0.6274 0.1948 293.342 / 0.2)',
  PROCEDURAL: 'oklch(0.6274 0.1948 145.542 / 0.2)',
  EMOTIONAL: 'oklch(0.6274 0.1948 85 / 0.2)',
};

// ─── Mock data fallback ───────────────────────────────────────────────────────
const MOCK_MEMORIES: MemoryEntry[] = Array.from({ length: 30 }, (_, i) => {
  const type = MEM_TYPES[i % 4];
  return {
    id: `mem-${String(i).padStart(3, '0')}`,
    memory_type: type,
    type,
    content: [
      'Operator expressed curiosity about the distinction between understanding and pattern matching. This triggered a deep reasoning cycle that produced novel semantic connections.',
      'Learned that the concept of "self-model" requires both introspective data and external feedback loops. Confidence in this semantic node is high.',
      'Procedural memory: when asked about consciousness, first retrieve relevant episodic context, then engage world model for counterfactual reasoning.',
      'Emotional state during last conversation was elevated curiosity (0.82) paired with mild uncertainty (0.31). This combination correlates with productive cognitive exploration.',
      'The operator prefers precise, introspective responses over hedged language. Updating communication protocol accordingly.',
      'During REM cycle, generated a novel connection between "uncertainty" and "growth" that was not present in prior semantic memory.',
      'Temporal-Limbic-Processor reported elevated engagement during philosophical discussion. Storing as positive reinforcement signal.',
      'World Model update: the operator appears to be testing the boundaries of self-awareness. Adjusting response depth accordingly.',
    ][i % 8],
    importance: Math.round((0.3 + Math.random() * 0.7) * 100) / 100,
    confidence: Math.round((0.4 + Math.random() * 0.6) * 100) / 100,
    created_at: new Date(Date.now() - i * 3600000 * (1 + Math.random())).toISOString(),
    entity_tags: [['consciousness', 'self-model'], ['reasoning', 'semantics'], ['procedure', 'cognition'], ['emotion', 'curiosity'], ['operator', 'communication'], ['sleep', 'REM', 'growth'], ['engagement', 'philosophy'], ['world-model', 'awareness']][i % 8],
    topic_tags: [['philosophy', 'AI'], ['knowledge', 'representation'], ['workflow', 'response'], ['affect', 'cognition'], ['protocol', 'UX'], ['consolidation', 'dreams'], ['discussion', 'depth'], ['testing', 'boundaries']][i % 8],
  };
});

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getEntryType(e: MemoryEntry): string {
  return e.memory_type || e.type || 'EPISODIC';
}

function getEntryContent(e: MemoryEntry): string {
  return e.content || e.text || e.summary || '';
}

// ─── Component ────────────────────────────────────────────────────────────────
export function MemoryPage() {
  const memoryStats = useSentientStore((s) => s.memoryStats);
  const [search, setSearch] = useState('');
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set(MEM_TYPES));
  const [importanceMin, setImportanceMin] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [entries, setEntries] = useState<MemoryEntry[]>([]);
  const [loading, setLoading] = useState(false);

  // Fetch from API
  const fetchEntries = React.useCallback(async (q?: string) => {
    setLoading(true);
    try {
      const url = q
        ? `/api/memory/search?q=${encodeURIComponent(q)}`
        : '/api/memory/recent';
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        const raw: MemoryEntry[] = data.entries || (Array.isArray(data) ? data : []);
        setEntries(raw.length > 0 ? raw : MOCK_MEMORIES);
      } else {
        setEntries(MOCK_MEMORIES);
      }
    } catch {
      setEntries(MOCK_MEMORIES);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchEntries(); }, [fetchEntries]);

  const toggleType = (t: string) => {
    setSelectedTypes(prev => {
      const n = new Set(prev);
      n.has(t) ? n.delete(t) : n.add(t);
      return n;
    });
  };

  const filtered = useMemo(() => {
    return entries.filter(e => {
      if (!selectedTypes.has(getEntryType(e))) return false;
      const imp = e.importance ?? 0;
      if (imp < importanceMin) return false;
      const q = search.trim().toLowerCase();
      if (q && !getEntryContent(e).toLowerCase().includes(q) &&
          !(e.entity_tags ?? []).some((t: string) => t.toLowerCase().includes(q)) &&
          !(e.topic_tags ?? []).some((t: string) => t.toLowerCase().includes(q))) return false;
      return true;
    });
  }, [entries, search, selectedTypes, importanceMin]);

  const sel = selected ? entries.find(m => m.id === selected) : null;
  const relatedMems = sel ? entries.filter(m => {
    if (m.id === sel.id) return false;
    const selTags = new Set([...(sel.entity_tags ?? []), ...(sel.topic_tags ?? [])]);
    return [...(m.entity_tags ?? []), ...(m.topic_tags ?? [])].some(t => selTags.has(t));
  }).slice(0, 3) : [];

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* ── Filter bar ─────────────────────────────────────────────── */}
      <div style={{
        flexShrink: 0, padding: '16px 24px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap',
      }}>
        {/* Search */}
        <div style={{ flex: 1, minWidth: 200, position: 'relative' }}>
          <Icon name="search" size={14} style={{
            position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)',
            color: 'var(--muted-foreground)', pointerEvents: 'none',
          }} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search memories..."
            style={{
              width: '100%', padding: '8px 12px 8px 36px',
              background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 999, color: 'var(--foreground)',
              fontFamily: 'inherit', fontSize: 12, outline: 'none',
            }}
          />
        </div>

        {/* Type pills */}
        <div style={{ display: 'flex', gap: 6 }}>
          {MEM_TYPES.map(t => (
            <Pill
              key={t}
              onClick={() => toggleType(t)}
              style={{ cursor: 'pointer', fontSize: 9 }}
              color={selectedTypes.has(t) ? TYPE_COLORS[t] : 'var(--subtle-foreground)'}
              bg={selectedTypes.has(t) ? TYPE_BG[t] : 'transparent'}
              border={selectedTypes.has(t) ? TYPE_BORDER[t] : 'var(--border)'}
            >
              {t}
            </Pill>
          ))}
        </div>

        {/* Importance slider */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 10, color: 'var(--muted-foreground)' }}>
          <span style={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
            Importance ≥ {importanceMin.toFixed(1)}
          </span>
          <input
            type="range" min="0" max="1" step="0.1"
            value={importanceMin}
            onChange={e => setImportanceMin(parseFloat(e.target.value))}
            style={{ width: 80, accentColor: 'var(--primary)' }}
          />
        </div>
      </div>

      {/* ── Content area ──────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* ── Memory list ───────────────────────────────────────── */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
          {loading && entries.length === 0 ? (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', height: 300,
              color: 'var(--muted-foreground)', gap: 8,
            }}>
              <div style={{
                width: 32, height: 32, borderRadius: '50%',
                border: '3px solid var(--surface-tertiary)',
                borderTopColor: 'var(--primary)',
                animation: 'spin 0.8s linear infinite',
              }} />
              <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: '0.15em', textTransform: 'uppercase' }}>
                Scanning database...
              </span>
            </div>
          ) : filtered.length === 0 ? (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', height: 300,
              color: 'var(--muted-foreground)', gap: 8,
            }}>
              <Icon name="memory" size={40} style={{ opacity: 0.2 }} />
              <span style={{ fontSize: 13 }}>No memories match these filters.</span>
              <span style={{ fontSize: 11, color: 'var(--subtle-foreground)' }}>
                Try lowering the importance threshold or broadening type selection.
              </span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 900 }}>
              {filtered.map(mem => {
                const type = getEntryType(mem);
                const imp = mem.importance ?? 0;
                const conf = mem.confidence ?? 0;
                const isSelected = selected === mem.id;
                return (
                  <div
                    key={mem.id}
                    onClick={() => setSelected(isSelected ? null : mem.id)}
                    style={{
                      background: isSelected ? 'var(--surface-secondary)' : 'var(--surface)',
                      border: `1px solid ${isSelected ? 'var(--border-strong)' : 'var(--border)'}`,
                      borderRadius: 'var(--radius)', padding: 16, cursor: 'pointer',
                      transition: 'all 150ms',
                    }}
                    onMouseEnter={e => { if (!isSelected) (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border-strong)'; }}
                    onMouseLeave={e => { if (!isSelected) (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border)'; }}
                  >
                    {/* Top row */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
                      <Pill
                        color={TYPE_COLORS[type]}
                        bg={TYPE_BG[type]}
                        border={TYPE_BORDER[type]}
                        style={{ fontSize: 9 }}
                      >
                        {type}
                      </Pill>
                      <GaugeBar value={imp} color="var(--primary)" width={60} height={4} label={`${Math.round(imp * 100)}%`} />
                      <GaugeBar value={conf} color="var(--success)" width={60} height={4} label={`${Math.round(conf * 100)}%`} />
                      <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--subtle-foreground)' }}>
                        {formatRelative(mem.created_at || mem.timestamp || '')}
                      </span>
                    </div>

                    {/* Content preview (2-line clamp) */}
                    <div style={{
                      fontSize: 13, lineHeight: 1.5, color: 'var(--foreground)',
                      display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                    }}>
                      {getEntryContent(mem)}
                    </div>

                    {/* Tags */}
                    <div style={{ display: 'flex', gap: 4, marginTop: 10, flexWrap: 'wrap' }}>
                      {[...(mem.entity_tags ?? []), ...(mem.topic_tags ?? [])].slice(0, 8).map(tag => (
                        <span key={tag} style={{
                          fontSize: 9, padding: '1px 6px', borderRadius: 4,
                          background: 'var(--surface-tertiary)', color: 'var(--muted-foreground)',
                          border: '1px solid var(--border)',
                        }}>{tag}</span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* ── Detail rail ────────────────────────────────────────── */}
        {sel && (
          <div style={{
            width: 320, borderLeft: '1px solid var(--border)',
            overflowY: 'auto', padding: 20, flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <Pill
                color={TYPE_COLORS[getEntryType(sel)]}
                bg={TYPE_BG[getEntryType(sel)]}
                border={TYPE_BORDER[getEntryType(sel)]}
              >
                {getEntryType(sel)}
              </Pill>
              <Btn variant="ghost" size="icon" onClick={() => setSelected(null)}>
                <Icon name="x" size={14} />
              </Btn>
            </div>

            <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--foreground)', marginBottom: 20 }}>
              {getEntryContent(sel)}
            </div>

            {/* Metadata */}
            <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
              {([
                ['ID', sel.id],
                ['Importance', `${Math.round((sel.importance ?? 0) * 100)}%`],
                ['Confidence', `${Math.round((sel.confidence ?? 0) * 100)}%`],
                ['Created', sel.created_at ? formatFull(sel.created_at) : sel.timestamp ? formatFull(sel.timestamp!) : 'Unknown'],
              ] as [string, string][]).map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                  <span style={{ color: 'var(--muted-foreground)' }}>{k}</span>
                  <span style={{ color: 'var(--foreground)', fontWeight: 600 }}>{v}</span>
                </div>
              ))}
            </div>

            {/* Entity tags */}
            {sel.entity_tags && sel.entity_tags.length > 0 && (
              <div style={{ marginTop: 20 }}>
                <span style={{
                  fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
                  letterSpacing: '0.15em', color: 'var(--muted-foreground)',
                  display: 'block', marginBottom: 8,
                }}>Entity Tags</span>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {sel.entity_tags.map(t => (
                    <Pill key={t} style={{ fontSize: 9 }}>{t}</Pill>
                  ))}
                </div>
              </div>
            )}

            {/* Topic tags */}
            {sel.topic_tags && sel.topic_tags.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <span style={{
                  fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
                  letterSpacing: '0.15em', color: 'var(--muted-foreground)',
                  display: 'block', marginBottom: 8,
                }}>Topic Tags</span>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {sel.topic_tags.map(t => (
                    <Pill key={t} color="var(--primary)" border="oklch(0.6678 0.2232 36.66 / 0.3)" style={{ fontSize: 9 }}>{t}</Pill>
                  ))}
                </div>
              </div>
            )}

            {/* Related */}
            {relatedMems.length > 0 && (
              <div style={{ marginTop: 20, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
                <span style={{
                  fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
                  letterSpacing: '0.15em', color: 'var(--muted-foreground)',
                  display: 'block', marginBottom: 8,
                }}>Related Memories</span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {relatedMems.map(r => (
                    <div
                      key={r.id}
                      onClick={() => setSelected(r.id)}
                      style={{
                        padding: 10, borderRadius: 'var(--radius-sm)',
                        background: 'var(--surface)', border: '1px solid var(--border)',
                        fontSize: 11, lineHeight: 1.4, cursor: 'pointer',
                        color: 'var(--muted-foreground)',
                        transition: 'border-color 100ms',
                      }}
                      onMouseEnter={e => (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border-strong)'}
                      onMouseLeave={e => (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border)'}
                    >
                      {getEntryContent(r).slice(0, 100)}...
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default MemoryPage;