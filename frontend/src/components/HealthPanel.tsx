import React from 'react';
import { Activity, Zap, CheckCircle2 } from 'lucide-react';
import { HealthSnapshot } from '../types';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface HealthPanelProps {
  snapshot: HealthSnapshot | null;
}

export const HealthPanel: React.FC<HealthPanelProps> = ({ snapshot }) => {
  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'healthy': return 'bg-success';
      case 'degraded': return 'bg-warning';
      case 'error': return 'bg-danger';
      default: return 'bg-muted-foreground';
    }
  };

  const getStatusBadge = (status: string) => {
    const s = status?.toLowerCase();
    if (s === 'healthy') return <Badge variant="outline" className="text-[8px] h-4 border-success/30 text-success bg-success/5 font-mono px-1">HEALTHY</Badge>;
    if (s === 'degraded') return <Badge variant="outline" className="text-[8px] h-4 border-warning/30 text-warning bg-warning/5 font-mono px-1">DEGRADED</Badge>;
    if (s === 'error') return <Badge variant="destructive" className="text-[8px] h-4 font-mono px-1">ERROR</Badge>;
    return <Badge variant="outline" className="text-[8px] h-4 font-mono px-1">UNKNOWN</Badge>;
  };

  const modules = snapshot ? Object.entries(snapshot) : [];

  return (
    <Card className="bg-card border-border shadow-sm overflow-hidden">
      <CardHeader className="px-4 py-3 border-b border-border bg-muted/30 pb-3">
        <CardTitle className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground flex items-center justify-between">
          <div className="flex items-center">
            <Activity size={14} className="mr-2 text-primary" /> Subsystems
          </div>
          {snapshot && (
            <div className="flex items-center gap-1.5">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-success"></span>
              </span>
              <span className="text-[9px] text-success font-bold tracking-tighter">LIVE</span>
            </div>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        {modules.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-6 opacity-20 space-y-2">
            <Activity size={24} className="animate-pulse" />
            <p className="text-[10px] uppercase tracking-tighter font-mono italic">Waiting for telemetry...</p>
          </div>
        ) : (
          modules.map(([name, data]) => (
            <div key={name} className="flex items-center justify-between group py-0.5">
              <div className="flex items-center gap-2 min-w-0">
                <div className={cn("w-1.5 h-1.5 rounded-full shrink-0 shadow-[0_0_8px_rgba(0,0,0,0.3)]", getStatusColor(data.status))} />
                <span className="text-[11px] text-muted-foreground font-mono group-hover:text-foreground transition-colors truncate uppercase tracking-tight">{name}</span>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <div className="flex items-center gap-1 opacity-40">
                  <Zap size={10} className="text-warning" />
                  <span className="text-[9px] text-muted-foreground font-mono">{data.pulse_count}</span>
                </div>
                {getStatusBadge(data.status)}
              </div>
            </div>
          ))
        )}
      </CardContent>
      <CardFooter className="bg-muted/10 border-t border-border/50 py-2 flex justify-center">
        <div className="flex items-center gap-1 text-[9px] font-mono text-muted-foreground uppercase opacity-40">
          <CheckCircle2 size={10} className="text-success" /> All systems nominal
        </div>
      </CardFooter>
    </Card>
  );
};
