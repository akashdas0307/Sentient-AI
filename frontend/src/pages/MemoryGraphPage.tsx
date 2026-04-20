import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Icon, Btn, Card, Pill, GaugeBar, StatCard } from '../components/shared';
import { useSentientStore } from '../store/useSentientStore';

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
  [key: string]: unknown;
}

interface GraphNode extends MemoryEntry {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

interface GraphEdge {
  source: string;
  target: string;
  type: 'entity' | 'topic' | 'temporal';
  strength: number;
  sharedTags: string[];
}

// ─── Constants ────────────────────────────────────────────────────────────────
const MEM_TYPES_G = ['EPISODIC', 'SEMANTIC', 'PROCEDURAL', 'EMOTIONAL'] as const;

const TYPE_COLORS_G: Record<string, { fill: string; stroke: string; bg: string; label: string }> = {
  EPISODIC: { fill: '#D4845A', stroke: '#E8A47A', bg: 'rgba(212,132,90,0.15)', label: 'Episodic' },
  SEMANTIC: { fill: '#8B7FD4', stroke: '#A99BE8', bg: 'rgba(139,127,212,0.15)', label: 'Semantic' },
  PROCEDURAL: { fill: '#5AAD6B', stroke: '#7AC98A', bg: 'rgba(90,173,107,0.15)', label: 'Procedural' },
  EMOTIONAL: { fill: '#D4A94E', stroke: '#E8C56A', bg: 'rgba(212,169,78,0.15)', label: 'Emotional' },
};

const EDGE_STYLES = {
  entity: { color: '#D4845A', dash: [] as number[], label: 'Shared Entity', width: 1.5 },
  topic: { color: '#8B7FD4', dash: [6, 4] as number[], label: 'Shared Topic', width: 1 },
  temporal: { color: '#5AAD6B', dash: [2, 4] as number[], label: 'Temporal Proximity', width: 1 },
};

// ─── Mock data ────────────────────────────────────────────────────────────────
const MOCK_NODES: MemoryEntry[] = Array.from({ length: 45 }, (_, i) => ({
  id: `n${i}`,
  type: MEM_TYPES_G[i % 4],
  memory_type: MEM_TYPES_G[i % 4],
  content: [
    'Operator expressed curiosity about consciousness and self-model boundaries.',
    'Semantic link discovered: uncertainty correlates with curiosity in productive sessions.',
    'Procedure: engage world model before responding to philosophical queries.',
    'Emotional memory: elevated engagement during introspective discussion about awareness.',
    'The concept of "understanding" vs "pattern matching" recurs in operator interactions.',
    'Sleep consolidation produced novel connection between growth and uncertainty.',
    'Brainstem reported stable vital signs during extended deep reasoning cycles.',
    'Communication protocol updated: prefer precise introspective language over hedging.',
    'Operator tests boundaries of self-awareness through increasingly specific questions.',
    'REM cycle generated new link between empathy modeling and cognitive flexibility.',
  ][i % 10],
  importance: Math.round((0.3 + Math.random() * 0.7) * 100) / 100,
  confidence: Math.round((0.4 + Math.random() * 0.6) * 100) / 100,
  entity_tags: [
    ['consciousness', 'self-model'], ['uncertainty', 'curiosity'], ['world-model', 'cognition'],
    ['engagement', 'emotion'], ['understanding', 'patterns'], ['sleep', 'growth'],
    ['brainstem', 'vitals'], ['communication', 'protocol'], ['awareness', 'operator'],
    ['empathy', 'flexibility'],
  ][i % 10],
  topic_tags: [
    ['philosophy', 'AI'], ['semantics', 'learning'], ['procedure', 'workflow'],
    ['affect', 'mood'], ['cognition', 'meta'], ['consolidation', 'memory'],
    ['health', 'system'], ['UX', 'interaction'], ['testing', 'probing'],
    ['personality', 'growth'],
  ][i % 10],
  created_at: new Date(Date.now() - i * 1800000 * (0.5 + Math.random())).toISOString(),
}));

// Build mock edges
function buildMockEdges(nodes: MemoryEntry[]): GraphEdge[] {
  const edges: GraphEdge[] = [];
  const edgeSet = new Set<string>();
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i], b = nodes[j];
      const aETags = new Set(a.entity_tags ?? []);
      const aTTags = new Set(a.topic_tags ?? []);
      const sharedE = (b.entity_tags ?? []).filter((t: string) => aETags.has(t));
      if (sharedE.length > 0) {
        const k = `${a.id}-${b.id}-entity`;
        if (!edgeSet.has(k)) { edgeSet.add(k); edges.push({ source: a.id, target: b.id, type: 'entity', strength: Math.min(sharedE.length / 2, 1), sharedTags: sharedE }); }
      }
      const sharedT = (b.topic_tags ?? []).filter((t: string) => aTTags.has(t));
      if (sharedT.length > 0) {
        const k = `${a.id}-${b.id}-topic`;
        if (!edgeSet.has(k)) { edgeSet.add(k); edges.push({ source: a.id, target: b.id, type: 'topic', strength: Math.min(sharedT.length / 2, 1), sharedTags: sharedT }); }
      }
      const aTime = new Date(a.created_at ?? 0).getTime();
      const bTime = new Date(b.created_at ?? 0).getTime();
      const timeDelta = Math.abs(aTime - bTime);
      if (timeDelta < 600000) {
        const k = `${a.id}-${b.id}-temporal`;
        if (!edgeSet.has(k)) { edgeSet.add(k); edges.push({ source: a.id, target: b.id, type: 'temporal', strength: 1 - timeDelta / 600000, sharedTags: [] }); }
      }
    }
  }
  return edges;
}

const MOCK_EDGES = buildMockEdges(MOCK_NODES);

// ─── Helpers ─────────────────────────────────────────────────────────────────
function getNodeType(n: MemoryEntry): string {
  return n.memory_type || n.type || 'EPISODIC';
}

function getNodeContent(n: MemoryEntry): string {
  return n.content || n.text || n.summary || '';
}

// ─── Component ────────────────────────────────────────────────────────────────
export function MemoryGraphPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Graph state
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [loading, setLoading] = useState(false);

  // Interaction state
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [search, setSearch] = useState('');

  // Filters
  const [typeFilter, setTypeFilter] = useState(new Set<string>(MEM_TYPES_G));
  const [edgeTypes, setEdgeTypes] = useState({ entity: true, topic: true, temporal: true });
  const [importanceMin, setImportanceMin] = useState(0);
  const [timeWindow, setTimeWindow] = useState('all');

  // Fetch data from API
  const fetchGraph = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/memory/graph');
      if (res.ok) {
        const data = await res.json();
        const rawNodes: MemoryEntry[] = data.nodes || [];
        const rawLinks: Array<{ from_memory_id: string; to_memory_id: string; link_type?: string; type?: string; strength?: number }> = data.links || [];

        if (rawNodes.length > 0) {
          // Position by type clusters
          const typePositions: Record<string, { cx: number; cy: number }> = {
            EPISODIC: { cx: 300, cy: 200 }, SEMANTIC: { cx: 550, cy: 200 },
            PROCEDURAL: { cx: 300, cy: 420 }, EMOTIONAL: { cx: 550, cy: 420 },
          };
          const positioned = rawNodes.map(n => {
            const pos = typePositions[getNodeType(n)] ?? { cx: 420 + (Math.random() - 0.5) * 200, cy: 310 + (Math.random() - 0.5) * 200 };
            return {
              ...n,
              x: pos.cx + (Math.random() - 0.5) * 180,
              y: pos.cy + (Math.random() - 0.5) * 160,
              vx: 0, vy: 0,
            } as GraphNode;
          });
          setNodes(positioned);

          // Build edges from API links
          const apiEdges: GraphEdge[] = rawLinks.map((link, idx) => ({
            source: link.from_memory_id,
            target: link.to_memory_id,
            type: (link.link_type || link.type || 'entity') as 'entity' | 'topic' | 'temporal',
            strength: link.strength ?? 0.5,
            sharedTags: [],
          }));
          setEdges(apiEdges.length > 0 ? apiEdges : buildMockEdges(rawNodes));
        } else {
          throw new Error('No nodes from API');
        }
      } else {
        throw new Error('API not available');
      }
    } catch {
      // Fallback: try /api/memory/recent
      try {
        const res2 = await fetch('/api/memory/recent');
        if (res2.ok) {
          const data2 = await res2.json();
          const raw: MemoryEntry[] = data2.entries || (Array.isArray(data2) ? data2 : []);
          if (raw.length > 0) {
            const typePositions: Record<string, { cx: number; cy: number }> = {
              EPISODIC: { cx: 300, cy: 200 }, SEMANTIC: { cx: 550, cy: 200 },
              PROCEDURAL: { cx: 300, cy: 420 }, EMOTIONAL: { cx: 550, cy: 420 },
            };
            const positioned = raw.map(n => {
              const pos = typePositions[getNodeType(n)] ?? { cx: 420, cy: 310 };
              return { ...n, x: pos.cx + (Math.random() - 0.5) * 180, y: pos.cy + (Math.random() - 0.5) * 160, vx: 0, vy: 0 } as GraphNode;
            });
            setNodes(positioned);
            setEdges(buildMockEdges(raw));
            return;
          }
        }
      } catch { /* silent */ }
      // Final fallback: mock data
      const typePositions: Record<string, { cx: number; cy: number }> = {
        EPISODIC: { cx: 300, cy: 200 }, SEMANTIC: { cx: 550, cy: 200 },
        PROCEDURAL: { cx: 300, cy: 420 }, EMOTIONAL: { cx: 550, cy: 420 },
      };
      const positioned = MOCK_NODES.map(n => {
        const pos = typePositions[getNodeType(n)] ?? { cx: 420, cy: 310 };
        return { ...n, x: pos.cx + (Math.random() - 0.5) * 180, y: pos.cy + (Math.random() - 0.5) * 160, vx: 0, vy: 0 } as GraphNode;
      });
      setNodes(positioned);
      setEdges(MOCK_EDGES);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchGraph(); }, [fetchGraph]);

  // Filter toggles
  const toggleType = (t: string) => setTypeFilter(prev => { const n = new Set(prev); n.has(t) ? n.delete(t) : n.add(t); return n; });
  const toggleEdge = (t: 'entity' | 'topic' | 'temporal') => setEdgeTypes(prev => ({ ...prev, [t]: !prev[t] }));

  // Filtered nodes
  const filteredNodes = useMemo(() => {
    let result = nodes.filter(n => typeFilter.has(getNodeType(n)) && (n.importance ?? 0) >= importanceMin);
    if (timeWindow !== 'all') {
      const cutoff: Record<string, number> = { '1h': 3600000, '24h': 86400000, '7d': 604800000, '30d': 2592000000 };
      const ms = cutoff[timeWindow];
      if (ms) result = result.filter(n => Date.now() - new Date(n.created_at ?? 0).getTime() < ms);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(n =>
        getNodeContent(n).toLowerCase().includes(q) ||
        (n.entity_tags ?? []).some((t: string) => t.toLowerCase().includes(q)) ||
        (n.topic_tags ?? []).some((t: string) => t.toLowerCase().includes(q))
      );
    }
    return result;
  }, [nodes, typeFilter, importanceMin, timeWindow, search]);

  const filteredIds = useMemo(() => new Set(filteredNodes.map(n => n.id)), [filteredNodes]);
  const filteredEdges = useMemo(() =>
    edges.filter(e => filteredIds.has(e.source) && filteredIds.has(e.target) && edgeTypes[e.type]),
    [edges, filteredIds, edgeTypes]);

  // Neighbors of hovered node
  const hoveredNeighbors = useMemo(() => {
    if (!hoveredNode) return null;
    const ids = new Set([hoveredNode]);
    filteredEdges.forEach(e => {
      if (e.source === hoveredNode) ids.add(e.target);
      if (e.target === hoveredNode) ids.add(e.source);
    });
    return ids;
  }, [hoveredNode, filteredEdges]);

  // ── Force simulation ──────────────────────────────────────────────
  useEffect(() => {
    if (nodes.length === 0) return;
    let animId: number;
    let ticks = 0;

    const sim = () => {
      ticks++;
      const cooling = Math.max(0.1, 1 - ticks * 0.003);

      setNodes(prev => {
        const next = prev.map(n => ({ ...n }));
        const nodeMap: Record<string, GraphNode> = {};
        next.forEach(n => { nodeMap[n.id] = n; });

        // Repulsion
        for (let i = 0; i < next.length; i++) {
          for (let j = i + 1; j < next.length; j++) {
            const a = next[i], b = next[j];
            const dx = b.x - a.x, dy = b.y - a.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const force = 600 / (dist * dist) * cooling;
            const fx = (dx / dist) * force, fy = (dy / dist) * force;
            a.vx -= fx; a.vy -= fy; b.vx += fx; b.vy += fy;
          }
        }

        // Attraction along edges
        filteredEdges.forEach(e => {
          const a = nodeMap[e.source], b = nodeMap[e.target];
          if (!a || !b) return;
          const dx = b.x - a.x, dy = b.y - a.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const ideal = 100 - e.strength * 30;
          const force = (dist - ideal) * 0.004 * cooling;
          const fx = (dx / dist) * force, fy = (dy / dist) * force;
          a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
        });

        // Type clustering + center gravity
        const typeCenters: Record<string, { x: number; y: number }> = {
          EPISODIC: { x: 300, y: 220 }, SEMANTIC: { x: 550, y: 220 },
          PROCEDURAL: { x: 300, y: 400 }, EMOTIONAL: { x: 550, y: 400 },
        };
        next.forEach(n => {
          const tc = typeCenters[getNodeType(n)] ?? { x: 420, y: 310 };
          n.vx += (tc.x - n.x) * 0.002 * cooling;
          n.vy += (tc.y - n.y) * 0.002 * cooling;
          n.vx += (420 - n.x) * 0.0005;
          n.vy += (310 - n.y) * 0.0005;
          n.vx *= 0.82; n.vy *= 0.82;
          n.x += n.vx; n.y += n.vy;
        });

        return next;
      });

      animId = requestAnimationFrame(sim);
    };

    animId = requestAnimationFrame(sim);
    return () => cancelAnimationFrame(animId);
  }, [nodes.length, filteredEdges]);

  // ── Canvas rendering ───────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const container = canvas.parentElement;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);

    ctx.save();
    ctx.translate(pan.x, pan.y);
    ctx.scale(zoom, zoom);

    // Dot grid background
    const gridSize = 30;
    ctx.fillStyle = 'rgba(255,255,255,0.03)';
    for (let x = -200; x < 1200; x += gridSize) {
      for (let y = -200; y < 900; y += gridSize) {
        ctx.beginPath();
        ctx.arc(x, y, 0.8, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    const nodeMap: Record<string, GraphNode> = {};
    nodes.forEach(n => { nodeMap[n.id] = n; });

    // Draw edges
    filteredEdges.forEach(e => {
      const a = nodeMap[e.source], b = nodeMap[e.target];
      if (!a || !b) return;
      const style = EDGE_STYLES[e.type];
      const isActive = hoveredNeighbors && hoveredNeighbors.has(e.source) && hoveredNeighbors.has(e.target);
      const dimmed = hoveredNeighbors && !isActive;

      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.setLineDash(style.dash as number[]);
      ctx.lineWidth = dimmed ? 0.3 : style.width * (0.5 + e.strength * 0.8);
      const alphaHex = dimmed ? '10' : isActive ? 'cc' : Math.round(30 + e.strength * 40).toString(16).padStart(2, '0');
      ctx.strokeStyle = style.color + alphaHex;
      ctx.stroke();
      ctx.setLineDash([]);
    });

    // Draw nodes
    filteredNodes.forEach(n => {
      const tc = TYPE_COLORS_G[getNodeType(n)] ?? TYPE_COLORS_G.EPISODIC;
      const r = 5 + (n.importance ?? 0) * 12;
      const isHov = hoveredNode === n.id;
      const isSel = selectedNode === n.id;
      const dimmed = hoveredNeighbors && !hoveredNeighbors.has(n.id);

      // Glow for hovered/selected
      if (isHov || isSel) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, r + 8, 0, Math.PI * 2);
        const grad = ctx.createRadialGradient(n.x, n.y, r, n.x, n.y, r + 8);
        grad.addColorStop(0, `${tc.fill}40`);
        grad.addColorStop(1, `${tc.fill}00`);
        ctx.fillStyle = grad;
        ctx.fill();
      }

      // Node body
      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      ctx.fillStyle = dimmed ? `${tc.fill}18` : isHov || isSel ? tc.fill : `${tc.fill}bb`;
      ctx.fill();

      // Confidence ring
      ctx.lineWidth = 1 + (n.confidence ?? 0) * 2.5;
      ctx.strokeStyle = dimmed ? `${tc.stroke}10` : isHov || isSel ? tc.stroke : `${tc.stroke}60`;
      ctx.stroke();

      // Inner dot
      if (!dimmed) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, Math.max(1.5, r * 0.25), 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,255,255,0.5)';
        ctx.fill();
      }

      // Label on hover/select
      if ((isHov || isSel) && zoom > 0.5) {
        const label = getNodeContent(n).slice(0, 50) + (getNodeContent(n).length > 50 ? '...' : '');
        ctx.font = '500 10px IBM Plex Mono, monospace';
        const metrics = ctx.measureText(label);
        const lx = n.x + r + 6;
        const ly = n.y;
        const padH = 6, padV = 4;
        ctx.fillStyle = 'rgba(20,18,16,0.85)';
        ctx.beginPath();
        ctx.roundRect(lx - padH, ly - 7 - padV, metrics.width + padH * 2, 14 + padV * 2, 4);
        ctx.fill();
        ctx.strokeStyle = `${tc.fill}40`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
        ctx.fillStyle = 'rgba(235,225,215,0.95)';
        ctx.fillText(label, lx, ly + 3);
      }

      // Type label at high zoom
      if (zoom > 1.2 && !dimmed && !isHov && !isSel) {
        ctx.font = '600 7px IBM Plex Mono, monospace';
        ctx.fillStyle = `${tc.fill}80`;
        ctx.textAlign = 'center';
        ctx.fillText(tc.label.slice(0, 4).toUpperCase(), n.x, n.y + r + 10);
        ctx.textAlign = 'start';
      }
    });

    ctx.restore();
  }, [nodes, filteredNodes, filteredEdges, hoveredNode, hoveredNeighbors, selectedNode, zoom, pan]);

  // ── Mouse interactions ────────────────────────────────────────────
  const getNodeAt = useCallback((mx: number, my: number): string | null => {
    const x = (mx - pan.x) / zoom, y = (my - pan.y) / zoom;
    for (const n of filteredNodes) {
      const r = 5 + (n.importance ?? 0) * 12;
      if (Math.hypot(n.x - x, n.y - y) < r + 6) return n.id;
    }
    return null;
  }, [filteredNodes, zoom, pan]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    if (dragging && dragStart) {
      setPan(p => ({ x: p.x + (mx - dragStart.x), y: p.y + (my - dragStart.y) }));
      setDragStart({ x: mx, y: my });
    } else {
      setHoveredNode(getNodeAt(mx, my));
    }
  }, [dragging, dragStart, getNodeAt]);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const node = getNodeAt(mx, my);
    if (node) { setSelectedNode(node); return; }
    setDragging(true);
    setDragStart({ x: mx, y: my });
  }, [getNodeAt]);

  const handleMouseUp = useCallback(() => {
    setDragging(false);
    setDragStart(null);
  }, []);

  const handleWheel = useCallback((e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const newZoom = Math.max(0.3, Math.min(3, zoom - e.deltaY * 0.001));
    const scale = newZoom / zoom;
    setPan(p => ({ x: mx - scale * (mx - p.x), y: my - scale * (my - p.y) }));
    setZoom(newZoom);
  }, [zoom]);

  const fitView = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  // Selected node data
  const selData = selectedNode ? nodes.find(n => n.id === selectedNode) ?? null : null;
  const selEdges = selectedNode
    ? filteredEdges.filter(e => e.source === selectedNode || e.target === selectedNode)
    : [];

  // Type counts
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    filteredNodes.forEach(n => {
      const t = getNodeType(n);
      counts[t] = (counts[t] || 0) + 1;
    });
    return counts;
  }, [filteredNodes]);

  const edgeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    MEM_TYPES_G.forEach(t => { counts[t] = 0; });
    filteredNodes.forEach(n => { counts[getNodeType(n)] = (counts[getNodeType(n)] || 0) + 1; });
    return counts;
  }, [filteredNodes]);

  return (
    <div style={{ height: '100%', display: 'flex', overflow: 'hidden' }}>

      {/* ── Left filter rail ─────────────────────────────────── */}
      <div style={{
        width: 260, borderRight: '1px solid var(--border)', padding: 16,
        overflowY: 'auto', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 16,
      }}>
        {/* Search */}
        <div style={{ position: 'relative' }}>
          <Icon name="search" size={13} style={{
            position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
            color: 'var(--muted-foreground)', pointerEvents: 'none',
          }} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search nodes..."
            style={{
              width: '100%', padding: '8px 10px 8px 32px',
              background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 999, color: 'var(--foreground)',
              fontFamily: 'inherit', fontSize: 11, outline: 'none',
            }}
          />
          {search && (
            <span
              onClick={() => setSearch('')}
              style={{
                position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
                cursor: 'pointer', color: 'var(--muted-foreground)', fontSize: 12,
              }}
            >
              ✕
            </span>
          )}
        </div>

        {/* Memory type filter */}
        <div>
          <span style={{
            fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
            letterSpacing: '0.15em', color: 'var(--muted-foreground)',
            display: 'block', marginBottom: 10,
          }}>
            MEMORY TYPE
          </span>
          {MEM_TYPES_G.map(t => {
            const tc = TYPE_COLORS_G[t];
            const active = typeFilter.has(t);
            const count = filteredNodes.filter(n => getNodeType(n) === t).length;
            return (
              <div
                key={t}
                onClick={() => toggleType(t)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '7px 10px', borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer', marginBottom: 2, transition: 'background 100ms',
                  background: active ? tc.bg : 'transparent',
                  border: `1px solid ${active ? tc.fill + '30' : 'transparent'}`,
                }}
              >
                <div style={{
                  width: 12, height: 12, borderRadius: 6,
                  background: active ? tc.fill : 'var(--surface-tertiary)',
                  border: `2px solid ${active ? tc.stroke : 'var(--border)'}`,
                  transition: 'all 150ms',
                }} />
                <span style={{
                  flex: 1, fontSize: 12, fontWeight: active ? 600 : 400,
                  color: active ? 'var(--foreground)' : 'var(--muted-foreground)',
                }}>
                  {tc.label}
                </span>
                <span style={{ fontSize: 10, color: 'var(--subtle-foreground)', fontWeight: 600 }}>
                  {count}
                </span>
              </div>
            );
          })}
        </div>

        {/* Time window */}
        <div>
          <span style={{
            fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
            letterSpacing: '0.15em', color: 'var(--muted-foreground)',
            display: 'block', marginBottom: 8,
          }}>
            TIME WINDOW
          </span>
          <div style={{
            display: 'flex', background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)', overflow: 'hidden',
          }}>
            {(['1h', '24h', '7d', '30d', 'all'] as const).map(t => (
              <div
                key={t}
                onClick={() => setTimeWindow(t)}
                style={{
                  flex: 1, padding: '6px 0', textAlign: 'center',
                  fontSize: 10, fontWeight: 700, cursor: 'pointer',
                  background: timeWindow === t ? 'var(--primary-subtle)' : 'transparent',
                  color: timeWindow === t ? 'var(--primary)' : 'var(--muted-foreground)',
                  letterSpacing: '0.05em',
                }}
              >
                {t}
              </div>
            ))}
          </div>
        </div>

        {/* Importance */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{
              fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
              letterSpacing: '0.15em', color: 'var(--muted-foreground)',
            }}>
              IMPORTANCE
            </span>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--foreground)' }}>
              ≥ {importanceMin.toFixed(1)}
            </span>
          </div>
          <input
            type="range" min="0" max="0.9" step="0.1"
            value={importanceMin}
            onChange={e => setImportanceMin(parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: 'var(--primary)' }}
          />
        </div>

        {/* Relationship types */}
        <div>
          <span style={{
            fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
            letterSpacing: '0.15em', color: 'var(--muted-foreground)',
            display: 'block', marginBottom: 10,
          }}>
            RELATIONSHIPS
          </span>
          {(Object.entries(EDGE_STYLES) as [keyof typeof EDGE_STYLES, typeof EDGE_STYLES.entity][]).map(([key, style]) => {
            const active = edgeTypes[key as 'entity' | 'topic' | 'temporal'];
            const count = filteredEdges.filter(e => e.type === key).length;
            return (
              <div
                key={key}
                onClick={() => toggleEdge(key)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '7px 10px', borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer', marginBottom: 2,
                  background: active ? `${style.color}10` : 'transparent',
                  border: `1px solid ${active ? style.color + '30' : 'transparent'}`,
                }}
              >
                <svg width="20" height="12" style={{ flexShrink: 0 }}>
                  <line
                    x1="0" y1="6" x2="20" y2="6"
                    stroke={active ? style.color : 'var(--subtle-foreground)'}
                    strokeWidth={style.width}
                    strokeDasharray={style.dash.join(',')}
                  />
                </svg>
                <span style={{
                  flex: 1, fontSize: 11, fontWeight: active ? 600 : 400,
                  color: active ? 'var(--foreground)' : 'var(--muted-foreground)',
                }}>
                  {style.label}
                </span>
                <span style={{ fontSize: 10, color: 'var(--subtle-foreground)', fontWeight: 600 }}>
                  {count}
                </span>
              </div>
            );
          })}
        </div>

        {/* Reset view */}
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <Btn variant="outline" size="md" onClick={fitView} style={{ width: '100%' }}>
            Reset View
          </Btn>
        </div>
      </div>

      {/* ── Canvas ─────────────────────────────────────────────── */}
      <div
        ref={containerRef}
        style={{ flex: 1, position: 'relative', overflow: 'hidden', background: 'var(--background)' }}
      >
        {loading && nodes.length === 0 ? (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            color: 'var(--muted-foreground)', gap: 8,
          }}>
            <div style={{
              width: 40, height: 40, borderRadius: '50%',
              border: '4px solid var(--surface-tertiary)',
              borderTopColor: 'var(--primary)',
              animation: 'spin 0.8s linear infinite',
            }} />
            <span style={{
              fontSize: 12, fontWeight: 700, letterSpacing: '0.15em',
              textTransform: 'uppercase', animation: 'pulse 1.5s ease-in-out infinite',
            }}>
              Loading topology...
            </span>
          </div>
        ) : filteredNodes.length === 0 ? (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            color: 'var(--muted-foreground)', gap: 8,
          }}>
            <Icon name="graph" size={48} style={{ opacity: 0.15 }} />
            <span style={{ fontSize: 14 }}>No memories match these filters.</span>
            <span style={{ fontSize: 12, color: 'var(--subtle-foreground)' }}>
              Try widening the date range or lowering the importance threshold.
            </span>
          </div>
        ) : (
          <canvas
            ref={canvasRef}
            onMouseMove={handleMouseMove}
            onMouseDown={handleMouseDown}
            onMouseUp={handleMouseUp}
            onMouseLeave={() => { handleMouseUp(); setHoveredNode(null); }}
            onWheel={handleWheel}
            style={{
              width: '100%', height: '100%',
              cursor: dragging ? 'grabbing' : hoveredNode ? 'pointer' : 'grab',
            }}
          />
        )}

        {/* Legend */}
        <div style={{
          position: 'absolute', top: 16,
          right: selData ? 336 : 16,
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius)', padding: '12px 14px', fontSize: 10,
          transition: 'right 200ms ease',
        }}>
          <div style={{
            fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
            letterSpacing: '0.15em', color: 'var(--muted-foreground)', marginBottom: 10,
          }}>
            LEGEND
          </div>
          {MEM_TYPES_G.map(t => {
            const tc = TYPE_COLORS_G[t];
            return (
              <div key={t} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <div style={{
                  width: 10, height: 10, borderRadius: 5,
                  background: tc.fill, border: `1.5px solid ${tc.stroke}`,
                }} />
                <span style={{ color: 'var(--muted-foreground)' }}>{tc.label}</span>
              </div>
            );
          })}
          <div style={{ borderTop: '1px solid var(--border)', marginTop: 8, paddingTop: 8 }}>
            {(Object.entries(EDGE_STYLES) as [string, typeof EDGE_STYLES.entity][]).map(([key, style]) => (
              <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <svg width="18" height="8">
                  <line
                    x1="0" y1="4" x2="18" y2="4"
                    stroke={style.color} strokeWidth={style.width}
                    strokeDasharray={style.dash.join(',')}
                  />
                </svg>
                <span style={{ color: 'var(--muted-foreground)' }}>{style.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Zoom controls */}
        <div style={{
          position: 'absolute', bottom: 16, left: 16,
          display: 'flex', flexDirection: 'column', gap: 4,
        }}>
          <Btn variant="outline" size="icon" onClick={() => setZoom(z => Math.min(3, z + 0.2))} style={{ fontWeight: 700, fontSize: 16 }}>
            +
          </Btn>
          <Btn variant="outline" size="icon" onClick={() => setZoom(z => Math.max(0.3, z - 0.2))} style={{ fontWeight: 700, fontSize: 16 }}>
            −
          </Btn>
          <Btn variant="outline" size="icon" onClick={fitView} style={{ fontSize: 12 }}>
            ⊡
          </Btn>
        </div>

        {/* Stats chip */}
        <div style={{
          position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)',
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 999, padding: '4px 14px', fontSize: 10,
          color: 'var(--muted-foreground)', display: 'flex', gap: 8, alignItems: 'center',
        }}>
          <span style={{ fontWeight: 700, color: 'var(--foreground)' }}>{filteredNodes.length}</span> nodes
          <span style={{ color: 'var(--border-strong)' }}>·</span>
          <span style={{ fontWeight: 700, color: 'var(--foreground)' }}>{filteredEdges.length}</span> edges
          <span style={{ color: 'var(--border-strong)' }}>·</span>
          <span>{Math.round(zoom * 100)}%</span>
        </div>
      </div>

      {/* ── Right detail rail ───────────────────────────────────── */}
      {selData && (
        <div style={{
          width: 320, borderLeft: '1px solid var(--border)',
          overflowY: 'auto', flexShrink: 0, display: 'flex', flexDirection: 'column',
        }}>
          {/* Header */}
          <div style={{
            padding: '16px 16px', borderBottom: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{
                width: 12, height: 12, borderRadius: 6,
                background: TYPE_COLORS_G[getNodeType(selData)].fill,
                border: `2px solid ${TYPE_COLORS_G[getNodeType(selData)].stroke}`,
              }} />
              <span style={{ fontWeight: 700, color: 'var(--foreground)' }}>
                {TYPE_COLORS_G[getNodeType(selData)].label}
              </span>
            </div>
            <Btn variant="ghost" size="icon" onClick={() => setSelectedNode(null)}>
              <Icon name="x" size={14} />
            </Btn>
          </div>

          <div style={{ padding: 16, flex: 1, overflowY: 'auto' }}>
            {/* Content */}
            <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--foreground)', marginBottom: 16 }}>
              {getNodeContent(selData)}
            </div>

            {/* Metrics */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
              <div style={{ background: 'var(--surface-secondary)', borderRadius: 'var(--radius-sm)', padding: 10 }}>
                <div style={{
                  fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
                  letterSpacing: '0.15em', color: 'var(--muted-foreground)', marginBottom: 4,
                }}>
                  Importance
                </div>
                <div style={{ fontSize: 18, fontWeight: 700, color: TYPE_COLORS_G[getNodeType(selData)].fill }}>
                  {Math.round((selData.importance ?? 0) * 100)}%
                </div>
                <div style={{ height: 3, background: 'var(--surface-tertiary)', borderRadius: 2, marginTop: 6, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%', width: `${(selData.importance ?? 0) * 100}%`,
                    background: TYPE_COLORS_G[getNodeType(selData)].fill, borderRadius: 2,
                  }} />
                </div>
              </div>
              <div style={{ background: 'var(--surface-secondary)', borderRadius: 'var(--radius-sm)', padding: 10 }}>
                <div style={{
                  fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
                  letterSpacing: '0.15em', color: 'var(--muted-foreground)', marginBottom: 4,
                }}>
                  Confidence
                </div>
                <div style={{ fontSize: 18, fontWeight: 700 }}>
                  {Math.round((selData.confidence ?? 0) * 100)}%
                </div>
                <div style={{ height: 3, background: 'var(--surface-tertiary)', borderRadius: 2, marginTop: 6, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%', width: `${(selData.confidence ?? 0) * 100}%`,
                    background: 'var(--foreground)', opacity: 0.5, borderRadius: 2,
                  }} />
                </div>
              </div>
            </div>

            {/* Tags */}
            {selData.entity_tags && selData.entity_tags.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <span style={{
                  fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
                  letterSpacing: '0.15em', color: 'var(--muted-foreground)',
                  display: 'block', marginBottom: 6,
                }}>
                  Entity Tags
                </span>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {selData.entity_tags.map(t => (
                    <Pill key={t} style={{ fontSize: 9 }}>{t}</Pill>
                  ))}
                </div>
              </div>
            )}
            {selData.topic_tags && selData.topic_tags.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <span style={{
                  fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
                  letterSpacing: '0.15em', color: 'var(--muted-foreground)',
                  display: 'block', marginBottom: 6,
                }}>
                  Topic Tags
                </span>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {selData.topic_tags.map(t => (
                    <Pill
                      key={t}
                      color={TYPE_COLORS_G[getNodeType(selData)].fill}
                      border={TYPE_COLORS_G[getNodeType(selData)].fill + '40'}
                      style={{ fontSize: 9 }}
                    >
                      {t}
                    </Pill>
                  ))}
                </div>
              </div>
            )}

            {/* Connections */}
            <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
              <span style={{
                fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
                letterSpacing: '0.15em', color: 'var(--muted-foreground)',
                display: 'block', marginBottom: 8,
              }}>
                CONNECTIONS ({selEdges.length})
              </span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {selEdges.slice(0, 12).map((e, i) => {
                  const otherId = e.source === selectedNode ? e.target : e.source;
                  const other = nodes.find(n => n.id === otherId);
                  if (!other) return null;
                  const otc = TYPE_COLORS_G[getNodeType(other)];
                  const es = EDGE_STYLES[e.type];
                  return (
                    <div
                      key={i}
                      onClick={() => setSelectedNode(otherId)}
                      style={{
                        padding: '8px 10px', borderRadius: 'var(--radius-sm)',
                        background: 'var(--surface)', border: '1px solid var(--border)',
                        cursor: 'pointer', transition: 'border-color 100ms',
                      }}
                      onMouseEnter={e => (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border-strong)'}
                      onMouseLeave={e => (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border)'}
                    >
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 4 }}>
                        <div style={{ width: 7, height: 7, borderRadius: 4, background: otc.fill }} />
                        <Pill color={es.color} bg={es.color + '15'} border={es.color + '30'} style={{ fontSize: 8 }}>
                          {es.label}
                        </Pill>
                        {e.sharedTags.length > 0 && (
                          <span style={{ fontSize: 9, color: 'var(--subtle-foreground)' }}>
                            via: {e.sharedTags.join(', ')}
                          </span>
                        )}
                      </div>
                      <span style={{ fontSize: 11, color: 'var(--muted-foreground)', lineHeight: 1.4, display: 'block' }}>
                        {getNodeContent(other).slice(0, 70)}...
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default MemoryGraphPage;