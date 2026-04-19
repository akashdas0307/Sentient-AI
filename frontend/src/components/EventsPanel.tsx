import React from 'react';
import { ListTree, Clock, Hash } from 'lucide-react';
import { EventMessage } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface EventsPanelProps {
  events: EventMessage[];
}

export const EventsPanel: React.FC<EventsPanelProps> = ({ events }) => {
  const getStageColor = (stage: string) => {
    switch (stage) {
      case 'perception': return 'text-primary border-primary/20 bg-primary/5';
      case 'cognition': return 'text-accent border-accent/20 bg-accent/5';
      case 'action': return 'text-success border-success/20 bg-success/5';
      case 'memory': return 'text-warning border-warning/20 bg-warning/5';
      default: return 'text-muted-foreground border-border bg-muted/30';
    }
  };

  return (
    <Card className="flex-1 min-h-0 bg-card border-border flex flex-col overflow-hidden shadow-sm">
      <CardHeader className="px-4 py-3 border-b border-border bg-muted/30 pb-3">
        <CardTitle className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground flex items-center justify-between">
          <div className="flex items-center">
            <ListTree size={14} className="mr-2 text-primary" /> Recent Events
          </div>
          <span className="font-mono text-[9px] opacity-40">{events.length}</span>
        </CardTitle>
      </CardHeader>
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-3">
          {events.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 opacity-20 text-muted-foreground space-y-2">
              <ListTree size={32} strokeWidth={1} />
              <p className="text-[10px] uppercase tracking-tighter">Buffer empty</p>
            </div>
          ) : (
            [...events].reverse().slice(0, 30).map((event, i) => (
              <div key={`${event.timestamp}-${i}`} className="group relative border-l-2 border-border pl-4 py-1.5 hover:bg-muted/30 transition-all rounded-r-md">
                <div className="flex justify-between items-center mb-1">
                  <Badge variant="outline" className={cn("text-[8px] font-mono h-4 px-1 tracking-tighter", getStageColor(event.stage))}>
                    {event.stage.toUpperCase()}
                  </Badge>
                  <span className="text-[9px] font-mono text-muted-foreground flex items-center gap-1 opacity-40">
                    <Clock size={8} /> {new Date(event.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                </div>
                <div className="text-[11px] font-mono font-bold text-foreground group-hover:text-primary transition-colors truncate mb-1">
                  {event.event_name}
                </div>
                {event.turn_id && (
                  <div className="text-[8px] font-mono text-muted-foreground flex items-center gap-1 opacity-30">
                    <Hash size={8} /> {event.turn_id}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </ScrollArea>
    </Card>
  );
};
