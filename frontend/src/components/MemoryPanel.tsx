import React, { useState, useEffect } from 'react';
import { Database, Network, HardDrive, Cpu } from 'lucide-react';
import { MemoryStats } from '../types';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export const MemoryPanel: React.FC = () => {
  const [stats, setStats] = useState<MemoryStats | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch('/api/memory/count');
        if (res.ok) setStats(await res.json());
      } catch (e) {
        console.error('Failed to fetch memory stats', e);
      }
    };
    fetchStats();
    const interval = setInterval(fetchStats, 60000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Card className="bg-card border-border shadow-sm hover:shadow-md transition-all overflow-hidden group">
      <CardContent className="p-4 flex items-center space-x-4">
        <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center shrink-0 border border-accent/20 group-hover:bg-accent/20 transition-colors">
          <Database size={24} className="text-accent" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex justify-between items-center mb-1">
            <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground group-hover:text-accent transition-colors">Semantic Store</h3>
            <div className="flex gap-1">
              <div className="w-1 h-3 bg-accent/20 rounded-full" />
              <div className="w-1 h-3 bg-accent/40 rounded-full" />
              <div className="w-1 h-3 bg-accent/60 rounded-full" />
            </div>
          </div>
          <div className="flex items-baseline justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold text-foreground font-mono tracking-tight">{stats?.count?.toLocaleString() || '0'}</span>
              <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest opacity-60">Nodes</span>
            </div>
            <Badge variant="outline" className="text-[9px] font-mono bg-muted/30 border-border/50 text-muted-foreground h-4 px-1.5">
              FAISS INDEX
            </Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
