import React, { useState, useEffect } from 'react';
import { Shield, Activity, Clock } from 'lucide-react';
import { SystemStatus } from '../types';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export const StatusPanel: React.FC = () => {
  const [status, setStatus] = useState<SystemStatus | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch('/api/status');
        if (res.ok) setStatus(await res.json());
      } catch (e) {
        console.error('Failed to fetch status', e);
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const formatUptime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  };

  const isHealthy = status?.status?.toLowerCase() === 'healthy';

  return (
    <Card className="bg-card border-border shadow-sm hover:shadow-md transition-all overflow-hidden group">
      <CardContent className="p-4 flex items-center space-x-4">
        <div className={cn(
          "w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 border transition-colors",
          isHealthy ? "bg-primary/10 border-primary/20" : "bg-destructive/10 border-destructive/20"
        )}>
          <Shield size={24} className={cn(isHealthy ? "text-primary" : "text-destructive")} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex justify-between items-center mb-1">
            <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground group-hover:text-primary transition-colors">System Integrity</h3>
            <Badge variant="outline" className="text-[9px] font-mono bg-muted/30 border-border/50 text-muted-foreground h-4 px-1.5">
              {status?.version || 'v0.7.0'}
            </Badge>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className={cn(
                "text-sm font-bold uppercase tracking-tight",
                isHealthy ? "text-foreground" : "text-destructive"
              )}>
                {status?.status || 'INITIALIZING...'}
              </span>
              {isHealthy && (
                <span className="flex h-2 w-2 rounded-full bg-success animate-pulse" />
              )}
            </div>
            <div className="flex items-center gap-1 text-[10px] font-mono text-muted-foreground bg-muted/20 px-1.5 rounded border border-border/10">
              <Clock size={10} />
              <span>{status ? formatUptime(status.uptime) : '--:--'}</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
