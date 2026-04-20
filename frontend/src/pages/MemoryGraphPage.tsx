import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  BackgroundVariant,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { MemoryNode, MEMORY_TYPE_COLORS, MEMORY_TYPE_LABELS, type MemoryNodeData } from '../components/MemoryNode';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { Network, Search, RefreshCw, X, Tag, Database, Clock, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface MemoryEntry {
  id: string;
  memory_type: string;
  content: string;
  importance: number;
  confidence: number;
  entity_tags: string[];
  topic_tags: string[];
  created_at: string;
  [key: string]: unknown;
}

/* ------------------------------------------------------------------ */
/*  Layout engine -- groups by type, fans out within group            */
/* ------------------------------------------------------------------ */
const TYPE_ANGLES: Record<string, number> = {
  EPISODIC: 0,
  SEMANTIC: Math.PI * 0.5,
  PROCEDURAL: Math.PI,
  EMOTIONAL: Math.PI * 1.5,
};

const GROUP_RADIUS = 280;
const SPREAD_RADIUS = 140;

function layoutNodes(entries: MemoryEntry[]): Node[] {
  const groups: Record<string, MemoryEntry[]> = {};
  entries.forEach((e) => {
    const t = e.memory_type || 'EPISODIC';
    if (!groups[t]) groups[t] = [];
    groups[t].push(e);
  });

  const centerX = 400;
  const centerY = 350;
  const nodes: Node<MemoryNodeData>[] = [];

  Object.entries(groups).forEach(([type, items]) => {
    const angle = TYPE_ANGLES[type] ?? Math.random() * Math.PI * 2;
    const gx = centerX + Math.cos(angle) * GROUP_RADIUS;
    const gy = centerY + Math.sin(angle) * GROUP_RADIUS;

    items.forEach((entry, i) => {
      const spreadAngle = (2 * Math.PI * i) / Math.max(items.length, 1);
      const jitter = SPREAD_RADIUS * (0.4 + Math.random() * 0.6);
      nodes.push({
        id: entry.id,
        type: 'memory',
        position: {
          x: gx + Math.cos(spreadAngle) * jitter,
          y: gy + Math.sin(spreadAngle) * jitter,
        },
        data: {
          memory_type: entry.memory_type,
          content: entry.content,
          importance: entry.importance,
          confidence: entry.confidence,
          entity_tags: entry.entity_tags,
          topic_tags: entry.topic_tags,
          created_at: entry.created_at,
          id: entry.id,
        },
      });
    });
  });

  return nodes;
}

/* ------------------------------------------------------------------ */
/*  Edge builder -- connect memories sharing tags                     */
/* ------------------------------------------------------------------ */
function buildEdges(entries: MemoryEntry[]): Edge[] {
  const edges: Edge[] = [];
  const seen = new Set<string>();

  for (let i = 0; i < entries.length; i++) {
    for (let j = i + 1; j < entries.length; j++) {
      const a = entries[i];
      const b = entries[j];
      const aTags = new Set([...(a.entity_tags || []), ...(a.topic_tags || [])]);
      const shared = [...(b.entity_tags || []), ...(b.topic_tags || [])].filter((t) => aTags.has(t));
      if (shared.length > 0) {
        const key = [a.id, b.id].sort().join('--');
        if (!seen.has(key)) {
          seen.add(key);
          const color = MEMORY_TYPE_COLORS[a.memory_type] ?? '#a3a3a3';
          edges.push({
            id: `e-${key}`,
            source: a.id,
            target: b.id,
            animated: shared.length >= 2,
            style: {
              stroke: `${color}40`,
              strokeWidth: Math.min(shared.length * 0.6 + 0.4, 2.5),
            },
          });
        }
      }
    }
  }

  return edges;
}

/* ------------------------------------------------------------------ */
/*  Node types map                                                     */
/* ------------------------------------------------------------------ */
const nodeTypes = { memory: MemoryNode };

/* ------------------------------------------------------------------ */
/*  Page Component                                                     */
/* ------------------------------------------------------------------ */
export const MemoryGraphPage: React.FC = () => {
  const [entries, setEntries] = useState<MemoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNode, setSelectedNode] = useState<Node<MemoryNodeData> | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node<MemoryNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  /* Fetch ----------------------------------------------------------- */
  const fetchEntries = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/memory/graph');
      if (res.ok) {
        const data = await res.json();
        // data has { nodes: [], links: [] }
        const rawNodes: MemoryEntry[] = data.nodes || [];
        const rawLinks: any[] = data.links || [];

        setEntries(rawNodes);

        // Transform links to Edges
        const apiEdges: Edge[] = rawLinks.map((link, idx) => ({
          id: `link-${idx}-${link.from_memory_id}-${link.to_memory_id}`,
          source: link.from_memory_id,
          target: link.to_memory_id,
          label: link.link_type,
          animated: link.strength > 0.7,
          style: {
            stroke: '#6366f160',
            strokeWidth: Math.min(link.strength * 2 + 0.5, 3),
          },
        }));

        setEdges(apiEdges);
      } else {
        // Fallback to recent if graph fails
        const resRecent = await fetch('/api/memory/recent');
        if (resRecent.ok) {
          const data = await resRecent.json();
          const raw: MemoryEntry[] = data.entries || (Array.isArray(data) ? data : []);
          setEntries(raw);
        }
      }
    } catch {
      /* silent */
    }
    setLoading(false);
  }, [setEdges]);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  /* Derive graph from entries --------------------------------------- */
  useEffect(() => {
    const n = layoutNodes(entries);
    setNodes(n as any);
    // If we have no edges (e.g. from apiEdges), we could still build some based on tags
    // but the API links should be primary.
    if (edges.length === 0 && entries.length > 0) {
      const e = buildEdges(entries);
      setEdges(e);
    }
  }, [entries, setNodes, setEdges, edges.length]);

  /* Filter by search ----------------------------------------------- */
  const filteredNodes = useMemo(() => {
    if (!searchQuery.trim()) return nodes;
    const q = searchQuery.toLowerCase();
    return nodes.filter((n) => {
      const d = n.data as MemoryNodeData;
      return (
        (d.content || '').toLowerCase().includes(q) ||
        (d.entity_tags || []).some((t) => t.toLowerCase().includes(q)) ||
        (d.topic_tags || []).some((t) => t.toLowerCase().includes(q)) ||
        (MEMORY_TYPE_LABELS[d.memory_type] || '').toLowerCase().includes(q)
      );
    });
  }, [nodes, searchQuery]);

  const filteredNodeIds = useMemo(() => new Set(filteredNodes.map((n) => n.id)), [filteredNodes]);

  const filteredEdges = useMemo(() => {
    if (!searchQuery.trim()) return edges;
    return edges.filter((e) => filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target));
  }, [edges, searchQuery, filteredNodeIds]);

  /* Node click -> detail panel -------------------------------------- */
  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node as Node<MemoryNodeData>);
    setDetailOpen(true);
  }, []);

  const closeDetail = useCallback(() => {
    setDetailOpen(false);
    setSelectedNode(null);
  }, []);

  /* MiniMap color fn ------------------------------------------------ */
  const miniMapNodeColor = useCallback((node: Node) => {
    const d = node.data as MemoryNodeData;
    return MEMORY_TYPE_COLORS[d.memory_type] ?? '#a3a3a3';
  }, []);

  /* Type counts for legend ------------------------------------------ */
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    entries.forEach((e) => {
      const t = e.memory_type || 'EPISODIC';
      counts[t] = (counts[t] || 0) + 1;
    });
    return counts;
  }, [entries]);

  /* Selected node data ---------------------------------------------- */
  const selectedData = selectedNode?.data as MemoryNodeData | undefined;

  return (
    <div className="h-full flex flex-col bg-[var(--bg-0)]">
      {/* Header */}
      <div className="shrink-0 px-6 pt-6 pb-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
                <Network size={18} className="text-primary" />
              </div>
              <div>
                <h2 className="text-xl font-bold tracking-tight text-foreground">
                  Neural Cartography
                </h2>
                <p className="text-xs text-muted-foreground">
                  Interactive memory topology and associative mapping
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Type legend */}
            <div className="hidden md:flex items-center gap-3 mr-3">
              {Object.entries(typeCounts).map(([type, count]) => (
                <div key={type} className="flex items-center gap-1.5">
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: MEMORY_TYPE_COLORS[type] ?? '#a3a3a3' }}
                  />
                  <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
                    {MEMORY_TYPE_LABELS[type] ?? type}
                  </span>
                  <span className="text-[10px] font-mono text-muted-foreground/60">({count})</span>
                </div>
              ))}
            </div>

            <Button
              variant="outline"
              size="icon"
              onClick={fetchEntries}
              className={cn(
                'rounded-full h-9 w-9 border-border hover:bg-muted/50',
                loading && 'animate-spin'
              )}
            >
              <RefreshCw size={14} className="text-muted-foreground" />
            </Button>
          </div>
        </div>

        {/* Search bar */}
        <div className="relative group">
          <Search
            size={16}
            className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground group-focus-within:text-primary transition-colors"
          />
          <Input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter nodes by content, tags, or type..."
            className="w-full bg-[var(--bg-2)] border-border rounded-lg py-2.5 pl-10 pr-10 text-sm focus-visible:ring-primary/20 focus-visible:border-primary transition-all duration-200"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            >
              <X size={14} />
            </button>
          )}
        </div>

        <Separator className="bg-border/40" />
      </div>

      {/* Graph canvas */}
      <div className="flex-1 min-h-0 relative">
        {loading && nodes.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground space-y-4">
            <div className="w-14 h-14 border-4 border-muted border-t-primary rounded-full animate-spin" />
            <p className="text-xs font-mono uppercase tracking-widest animate-pulse">
              Loading topology...
            </p>
          </div>
        ) : nodes.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground/50 space-y-3">
            <Database size={48} strokeWidth={1} />
            <p className="text-sm">No memory entries to map</p>
            <p className="text-xs text-muted-foreground/40">Memories will appear here as they are created</p>
          </div>
        ) : (
          <ReactFlow
            nodes={filteredNodes}
            edges={filteredEdges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.15}
            maxZoom={2.5}
            proOptions={{ hideAttribution: true }}
            className="bg-[var(--bg-0)]"
            style={{ background: 'transparent' }}
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={20}
              size={1}
              color="var(--border-subtle)"
            />
            <Controls
              showInteractive={false}
              className="!bg-[var(--bg-2)] !border-border !rounded-lg !shadow-lg [&>button]:!bg-[var(--bg-2)] [&>button]:!border-border [&>button]:!text-muted-foreground [&>button:hover]:!bg-[var(--bg-4)] [&>button]:!rounded-md"
            />
            <MiniMap
              nodeColor={miniMapNodeColor}
              maskColor="rgba(10, 10, 10, 0.75)"
              style={{
                background: 'var(--bg-2)',
                border: '1px solid var(--border-default)',
                borderRadius: '8px',
              }}
              className="!border-border"
            />
          </ReactFlow>
        )}

        {/* Floating stats chip */}
        {entries.length > 0 && (
          <div className="absolute bottom-4 left-4 z-10 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--bg-2)]/90 backdrop-blur-sm border border-border/60 shadow-lg">
            <Sparkles size={12} className="text-accent" />
            <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
              {filteredNodes.length} nodes
            </span>
            <span className="text-[10px] text-border-default">/</span>
            <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
              {filteredEdges.length} edges
            </span>
            {searchQuery && (
              <>
                <span className="text-[10px] text-border-default">/</span>
                <span className="text-[10px] font-mono text-accent uppercase tracking-wider">
                  filtered
                </span>
              </>
            )}
          </div>
        )}
      </div>

      {/* Detail Sheet */}
      <Sheet open={detailOpen} onOpenChange={(open) => { if (!open) closeDetail(); }}>
        <SheetContent
          side="right"
          className="w-[420px] sm:max-w-[420px] bg-[var(--bg-1,#111)] border-l border-border p-0 overflow-hidden"
          showCloseButton={false}
        >
          {selectedData && (
            <div className="flex flex-col h-full">
              {/* Header */}
              <SheetHeader className="px-5 pt-5 pb-3 border-b border-border/60">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div
                      className="w-2.5 h-2.5 rounded-full shrink-0"
                      style={{
                        backgroundColor: MEMORY_TYPE_COLORS[selectedData.memory_type] ?? '#a3a3a3',
                        boxShadow: `0 0 8px ${MEMORY_TYPE_COLORS[selectedData.memory_type] ?? '#a3a3a3'}60`,
                      }}
                    />
                    <SheetTitle className="text-sm font-bold uppercase tracking-widest">
                      {MEMORY_TYPE_LABELS[selectedData.memory_type] ?? selectedData.memory_type}
                    </SheetTitle>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={closeDetail}
                    className="h-7 w-7 text-muted-foreground hover:text-foreground"
                  >
                    <X size={14} />
                  </Button>
                </div>
                <SheetDescription className="text-[10px] font-mono text-muted-foreground/60">
                  {selectedData.id}
                </SheetDescription>
              </SheetHeader>

              {/* Body */}
              <ScrollArea className="flex-1 px-5 py-4">
                <div className="space-y-5 pb-6">
                  {/* Metrics */}
                  <div className="grid grid-cols-2 gap-3">
                    <Card className="bg-[var(--bg-2)] border-border">
                      <CardContent className="p-3 space-y-1">
                        <p className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground">
                          Importance
                        </p>
                        <div className="flex items-baseline gap-1.5">
                          <span
                            className="text-lg font-bold"
                            style={{ color: MEMORY_TYPE_COLORS[selectedData.memory_type] ?? '#a3a3a3' }}
                          >
                            {((selectedData.importance ?? 0) * 100).toFixed(0)}
                          </span>
                          <span className="text-xs text-muted-foreground">%</span>
                        </div>
                        <div className="h-1 rounded-full bg-[var(--bg-4)] overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-500"
                            style={{
                              width: `${Math.max((selectedData.importance ?? 0) * 100, 2)}%`,
                              backgroundColor: MEMORY_TYPE_COLORS[selectedData.memory_type] ?? '#a3a3a3',
                            }}
                          />
                        </div>
                      </CardContent>
                    </Card>
                    <Card className="bg-[var(--bg-2)] border-border">
                      <CardContent className="p-3 space-y-1">
                        <p className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground">
                          Confidence
                        </p>
                        <div className="flex items-baseline gap-1.5">
                          <span className="text-lg font-bold text-foreground">
                            {((selectedData.confidence ?? 0) * 100).toFixed(0)}
                          </span>
                          <span className="text-xs text-muted-foreground">%</span>
                        </div>
                        <div className="h-1 rounded-full bg-[var(--bg-4)] overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-500 bg-foreground/60"
                            style={{
                              width: `${Math.max((selectedData.confidence ?? 0) * 100, 2)}%`,
                            }}
                          />
                        </div>
                      </CardContent>
                    </Card>
                  </div>

                  <Separator className="bg-border/40" />

                  {/* Content */}
                  <div className="space-y-2">
                    <p className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground">
                      Content
                    </p>
                    <p className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap">
                      {selectedData.content}
                    </p>
                  </div>

                  <Separator className="bg-border/40" />

                  {/* Timestamp */}
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Clock size={12} />
                    <span className="font-mono text-[11px]">
                      {selectedData.created_at
                        ? new Date(selectedData.created_at).toLocaleString()
                        : 'Unknown'}
                    </span>
                  </div>

                  {/* Entity tags */}
                  {selectedData.entity_tags && selectedData.entity_tags.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground">
                        Entity Tags
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {selectedData.entity_tags.map((tag) => (
                          <Badge
                            key={tag}
                            variant="outline"
                            className="bg-[var(--bg-4)] border-border/50 text-muted-foreground font-mono text-[10px] py-0"
                          >
                            <Tag size={8} className="mr-1" />
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Topic tags */}
                  {selectedData.topic_tags && selectedData.topic_tags.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground">
                        Topic Tags
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {selectedData.topic_tags.map((tag) => (
                          <Badge
                            key={tag}
                            variant="outline"
                            className="bg-primary/5 border-primary/20 text-primary font-mono text-[10px] py-0"
                          >
                            <Tag size={8} className="mr-1" />
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </ScrollArea>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
};

export default MemoryGraphPage;