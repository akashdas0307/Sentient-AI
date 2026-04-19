import React, { useState, useEffect } from 'react';
import { Database, Search, RefreshCw, BarChart3, Clock, Tag } from 'lucide-react';
import { useSentientStore } from '../store/useSentientStore';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

export const MemoryPage: React.FC = () => {
  const memoryStats = useSentientStore((s) => s.memoryStats);
  const [searchQuery, setSearchQuery] = useState('');
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchEntries = async (query?: string) => {
    setLoading(true);
    try {
      const url = query
        ? `/api/memory/search?q=${encodeURIComponent(query)}`
        : '/api/memory/recent';
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setEntries(data.entries || (Array.isArray(data) ? data : []));
      }
    } catch { /* silent */ }
    setLoading(false);
  };

  useEffect(() => {
    fetchEntries();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchEntries(searchQuery || undefined);
  };

  const importanceVariant = (score: number) => {
    if (score >= 0.8) return 'default';
    if (score >= 0.5) return 'secondary';
    return 'outline';
  };

  const importanceColor = (score: number) => {
    if (score >= 0.8) return 'text-success border-success/20 bg-success/5';
    if (score >= 0.5) return 'text-warning border-warning/20 bg-warning/5';
    return 'text-muted-foreground border-border bg-muted/30';
  };

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto w-full">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="text-2xl font-bold tracking-tight text-foreground">Knowledge Base</h2>
          <p className="text-sm text-muted-foreground">Long-term semantic memory and associative nodes.</p>
        </div>
        <Button
          variant="outline"
          size="icon"
          onClick={() => fetchEntries(searchQuery || undefined)}
          className={cn("rounded-full h-10 w-10 border-border hover:bg-muted/50", loading && "animate-spin")}
        >
          <RefreshCw size={16} className="text-muted-foreground" />
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="bg-card border-border shadow-sm hover:shadow-md transition-all">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center border border-accent/20">
                <Database size={24} className="text-accent" />
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Total Memories</p>
                <p className="text-3xl font-bold text-foreground">
                  {memoryStats?.total_memories?.toLocaleString() ?? memoryStats?.count?.toLocaleString() ?? '—'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card border-border shadow-sm hover:shadow-md transition-all">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20">
                <BarChart3 size={24} className="text-primary" />
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Active Clusters</p>
                <p className="text-3xl font-bold text-foreground">{entries.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search Bar */}
      <form onSubmit={handleSearch} className="relative group">
        <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground group-focus-within:text-primary transition-colors" />
        <Input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Query semantic index..."
          className="w-full bg-card border-border rounded-xl py-6 pl-12 pr-4 text-sm focus-visible:ring-primary/20 focus-visible:border-primary transition-all duration-200"
        />
        {loading && (
          <div className="absolute right-4 top-1/2 -translate-y-1/2">
            <div className="w-4 h-4 border-2 border-primary/20 border-t-primary rounded-full animate-spin" />
          </div>
        )}
      </form>

      <Separator className="bg-border/50" />

      {/* Entries List */}
      <ScrollArea className="h-[calc(100vh-420px)] min-h-[300px] pr-4">
        <div className="space-y-3 pb-6">
          {loading && entries.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-muted-foreground space-y-4">
              <div className="w-12 h-12 border-4 border-muted border-t-primary rounded-full animate-spin" />
              <p className="text-sm font-mono uppercase tracking-widest animate-pulse">Scanning database...</p>
            </div>
          ) : entries.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-muted-foreground space-y-3 opacity-50">
              <Database size={40} strokeWidth={1} />
              <p className="text-sm">No semantic matches found</p>
            </div>
          ) : (
            entries.map((entry: any) => (
              <Card
                key={entry.id || entry.chunk_id}
                className="bg-card/50 border-border hover:bg-card hover:border-border/80 transition-all cursor-default group"
              >
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="bg-muted/50 font-mono text-[10px] py-0 border-border/50">
                        {entry.type || entry.chunk_type || 'memory'}
                      </Badge>
                      <span className="text-[10px] font-mono text-muted-foreground flex items-center gap-1">
                        <Clock size={10} /> {entry.timestamp ? new Date(entry.timestamp).toLocaleDateString() : 'Historical'}
                      </span>
                    </div>
                    {entry.importance != null && (
                      <Badge
                        variant="outline"
                        className={cn("font-mono text-[10px] py-0 border", importanceColor(entry.importance))}
                      >
                        RELEVANCE: {(entry.importance * 100).toFixed(0)}%
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-foreground leading-relaxed">
                    {entry.content || entry.text || entry.summary}
                  </p>
                  {entry.tags && entry.tags.length > 0 && (
                    <div className="flex gap-2 mt-4 flex-wrap">
                      {entry.tags.slice(0, 8).map((tag: string) => (
                        <div key={tag} className="flex items-center gap-1 px-2 py-0.5 text-[10px] bg-muted/80 rounded-md text-muted-foreground border border-border/50">
                          <Tag size={8} /> {tag}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
};
