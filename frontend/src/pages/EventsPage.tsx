import React, { useState, useMemo } from 'react';
import { ListTree, Filter, Search, Clock, Database, ChevronRight } from 'lucide-react';
import { useSentientStore } from '../store/useSentientStore';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

export const EventsPage: React.FC = () => {
  const messages = useSentientStore((s) => s.messages);
  const [filterStage, setFilterStage] = useState<string>('all');
  const [filterType, setFilterType] = useState<string>('all');

  const events = useMemo(() => {
    return messages
      .filter((m) => m.type === 'event')
      .map((m) => ({
        stage: (m as any).stage || 'system',
        event_name: (m as any).event_name || 'unknown',
        data: (m as any).data || {},
        turn_id: (m as any).turn_id || null,
        timestamp: m.timestamp,
      }));
  }, [messages]);

  const stages = useMemo(() => {
    const set = new Set(events.map((e) => e.stage));
    return ['all', ...Array.from(set)];
  }, [events]);

  const types = useMemo(() => {
    const set = new Set(events.map((e) => e.event_name));
    return ['all', ...Array.from(set)];
  }, [events]);

  const filtered = useMemo(() => {
    return events.filter((e) => {
      if (filterStage !== 'all' && e.stage !== filterStage) return false;
      if (filterType !== 'all' && e.event_name !== filterType) return false;
      return true;
    });
  }, [events, filterStage, filterType]);

  const stageColor = (stage: string) => {
    switch (stage) {
      case 'perception': return 'var(--primary)';
      case 'cognition': return 'var(--accent)';
      case 'action': return 'var(--success)';
      case 'memory': return 'var(--warning)';
      default: return 'var(--text-muted)';
    }
  };

  const getStageBadgeColor = (stage: string) => {
    switch (stage) {
      case 'perception': return 'text-primary border-primary/20 bg-primary/5';
      case 'cognition': return 'text-accent border-accent/20 bg-accent/5';
      case 'action': return 'text-success border-success/20 bg-success/5';
      case 'memory': return 'text-warning border-warning/20 bg-warning/5';
      default: return 'text-muted-foreground border-border bg-muted/30';
    }
  };

  return (
    <div className="h-full flex flex-col bg-background overflow-hidden">
      <div className="p-6 border-b border-border bg-card/30 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-6">
          <div className="space-y-1">
            <h2 className="text-2xl font-bold tracking-tight text-foreground">Event Stream</h2>
            <p className="text-sm text-muted-foreground uppercase tracking-widest font-mono text-[10px]">Neural pulse monitoring • Real-time telemetry</p>
          </div>
          <Badge variant="outline" className="font-mono text-xs border-primary/20 text-primary px-3">
            {filtered.length} BROADCASTS
          </Badge>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center border border-border">
              <Filter size={14} className="text-muted-foreground" />
            </div>
            <div className="flex gap-2">
              <Select value={filterStage} onValueChange={setFilterStage}>
                <SelectTrigger className="w-[160px] h-9 bg-card border-border rounded-lg text-xs font-medium">
                  <SelectValue placeholder="All Stages" />
                </SelectTrigger>
                <SelectContent className="bg-card border-border">
                  {stages.map((s) => (
                    <SelectItem key={s} value={s} className="text-xs">
                      {s === 'all' ? 'All Stages' : s.toUpperCase()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={filterType} onValueChange={setFilterType}>
                <SelectTrigger className="w-[180px] h-9 bg-card border-border rounded-lg text-xs font-medium">
                  <SelectValue placeholder="All Types" />
                </SelectTrigger>
                <SelectContent className="bg-card border-border">
                  {types.map((t) => (
                    <SelectItem key={t} value={t} className="text-xs">
                      {t === 'all' ? 'All Types' : t.toUpperCase()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      </div>

      {/* Events List */}
      <ScrollArea className="flex-1 px-6">
        <div className="py-6 space-y-4 max-w-5xl mx-auto w-full">
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-muted-foreground space-y-3 opacity-30">
              <ListTree size={48} strokeWidth={1} />
              <p className="text-sm uppercase tracking-widest font-mono">No telemetry matching filters</p>
            </div>
          ) : (
            filtered.map((event, i) => (
              <div
                key={`${event.timestamp}-${i}`}
                className="group relative flex gap-6 p-4 rounded-xl hover:bg-muted/30 transition-all duration-200 border border-transparent hover:border-border/50"
              >
                <div className="flex flex-col items-center gap-2 shrink-0 pt-1">
                  <div className="w-2.5 h-2.5 rounded-full ring-4 ring-background shadow-lg" style={{ backgroundColor: stageColor(event.stage) }} />
                  <div className="w-px flex-1 bg-border/50 group-last:hidden" />
                </div>

                <div className="flex-1 min-w-0 pb-2">
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-bold font-mono text-primary tracking-tight">
                        {event.event_name.toUpperCase()}
                      </span>
                      <Badge
                        variant="outline"
                        className={cn("text-[10px] font-mono py-0 px-2 tracking-tighter border", getStageBadgeColor(event.stage))}
                      >
                        {event.stage}
                      </Badge>
                    </div>
                    <span className="text-[10px] font-mono text-muted-foreground bg-muted/50 px-2 py-0.5 rounded flex items-center gap-1 border border-border/50">
                      <Clock size={10} /> {new Date(event.timestamp).toLocaleTimeString([], { hour12: false, fractionalSecondDigits: 3 })}
                    </span>
                  </div>

                  <div className="bg-muted/40 rounded-lg p-3 border border-border/50 group-hover:bg-muted/60 transition-colors">
                    {event.data && Object.keys(event.data).length > 0 ? (
                      <pre className="text-[11px] font-mono text-muted-foreground overflow-x-auto leading-relaxed">
                        {JSON.stringify(event.data, null, 2)}
                      </pre>
                    ) : (
                      <p className="text-[11px] font-mono text-muted-foreground italic">No additional telemetry data payload</p>
                    )}
                  </div>

                  {event.turn_id && (
                    <div className="mt-2 flex items-center gap-1 text-[10px] font-mono text-primary/40 hover:text-primary transition-colors cursor-pointer">
                      <Database size={10} /> LINKED TURN ID: {event.turn_id} <ChevronRight size={10} />
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
};
