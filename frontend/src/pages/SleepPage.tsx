import React, { useState, useEffect } from 'react';
import { Moon, RefreshCw, Clock, Zap, History, Info } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

interface SleepCycle {
  id: string;
  scope: string;
  consolidated_at: number;
  source_count: number;
  summary: string;
}

export const SleepPage: React.FC = () => {
  const [cycles, setCycles] = useState<SleepCycle[]>([]);
  const [sleepState, setSleepState] = useState<{ stage: string; duration: number; cycle_count: number } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [sleepRes, cyclesRes] = await Promise.all([
          fetch('/api/sleep/status'),
          fetch('/api/sleep/consolidations'),
        ]);
        if (sleepRes.ok) {
          const data = await sleepRes.ok ? await sleepRes.json() : null;
          if (data) {
            setSleepState({
              stage: data.current_stage || 'awake',
              duration: data.stage_duration_seconds || 0,
              cycle_count: data.sleep_cycle_count || 0,
            });
          }
        }
        if (cyclesRes.ok) {
          const data = await cyclesRes.json();
          setCycles(Array.isArray(data) ? data : data.consolidations ?? []);
        }
      } catch { /* graceful */ }
      setLoading(false);
    };
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const chartData = cycles.slice(0, 20).reverse().map((c, i) => ({
    name: `#${i + 1}`,
    sources: c.source_count,
    time: new Date(c.consolidated_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  }));

  const stageLabel = (stage: string) => {
    switch (stage) {
      case 'awake': return { text: 'Awake', color: 'text-success', bg: 'bg-success/10', border: 'border-success/20', icon: Zap };
      case 'light': return { text: 'Light Sleep', color: 'text-primary', bg: 'bg-primary/10', border: 'border-primary/20', icon: Moon };
      case 'deep': return { text: 'Deep Sleep', color: 'text-accent', bg: 'bg-accent/10', border: 'border-accent/20', icon: Moon };
      case 'rem': return { text: 'REM', color: 'text-warning', bg: 'bg-warning/10', border: 'border-warning/20', icon: Sparkles };
      default: return { text: stage, color: 'text-muted-foreground', bg: 'bg-muted/50', border: 'border-border', icon: Info };
    }
  };

  const currentStage = sleepState ? stageLabel(sleepState.stage) : stageLabel('awake');
  const Icon = currentStage.icon;

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto w-full">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="text-2xl font-bold tracking-tight text-foreground">Sleep & Consolidation</h2>
          <p className="text-sm text-muted-foreground">Self-regulation and memory optimization cycles.</p>
        </div>
        <Button
          variant="outline"
          size="icon"
          onClick={() => {
            setLoading(true);
            Promise.all([
              fetch('/api/sleep/status').then(r => r.json()),
              fetch('/api/sleep/consolidations').then(r => r.json())
            ]).then(([data, d]) => {
              setSleepState({
                stage: data.current_stage || 'awake',
                duration: data.stage_duration_seconds || 0,
                cycle_count: data.sleep_cycle_count || 0,
              });
              setCycles(Array.isArray(d) ? d : d.consolidations ?? []);
              setLoading(false);
            });
          }}
          className={cn("rounded-full h-10 w-10 border-border hover:bg-muted/50", loading && "animate-spin")}
        >
          <RefreshCw size={16} className="text-muted-foreground" />
        </Button>
      </div>

      {/* Sleep State Card */}
      <Card className="overflow-hidden border-border bg-card shadow-lg">
        <CardContent className="p-0">
          <div className="flex flex-col md:flex-row">
            <div className={cn("p-8 md:w-1/3 flex flex-col items-center justify-center text-center space-y-4 border-b md:border-b-0 md:border-r border-border", currentStage.bg)}>
              <div className={cn("w-20 h-20 rounded-full flex items-center justify-center border shadow-inner", currentStage.border, "bg-background/40 backdrop-blur-sm")}>
                <Icon size={36} className={currentStage.color} />
              </div>
              <div className="space-y-1">
                <Badge variant="outline" className={cn("font-mono px-3 py-1 text-xs uppercase tracking-widest border", currentStage.border, currentStage.color)}>
                  {currentStage.text}
                </Badge>
                <p className="text-[10px] text-muted-foreground font-mono mt-2">Current Identity State</p>
              </div>
            </div>
            <div className="p-8 flex-1 grid grid-cols-2 gap-8">
              <div className="space-y-1">
                <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Duration</p>
                <p className="text-3xl font-bold text-foreground font-mono">
                  {sleepState?.duration ?? 0}<span className="text-sm font-normal text-muted-foreground ml-1">s</span>
                </p>
                <div className="w-full bg-muted rounded-full h-1 mt-3">
                  <div className={cn("h-full rounded-full transition-all duration-1000", currentStage.color.replace('text-', 'bg-'))} style={{ width: '65%' }}></div>
                </div>
              </div>
              <div className="space-y-1">
                <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Total Cycles</p>
                <p className="text-3xl font-bold text-foreground font-mono">
                  {sleepState?.cycle_count ?? 0}
                </p>
                <div className="flex items-center gap-1 mt-3 text-[10px] text-muted-foreground font-mono">
                  <Zap size={10} className="text-warning" /> 100% Efficiency
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Consolidation Chart */}
      {chartData.length > 0 && (
        <Card className="bg-card border-border shadow-md">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
              <History size={14} className="text-primary" /> Consolidation Velocity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorSources" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="var(--accent)" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: 'var(--bg-3)', border: '1px solid var(--border-default)', borderRadius: '12px', fontSize: '12px', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.3)' }}
                  labelStyle={{ color: 'var(--text-primary)', fontWeight: 'bold' }}
                  itemStyle={{ color: 'var(--accent)' }}
                />
                <Area type="monotone" dataKey="sources" stroke="var(--accent)" strokeWidth={3} fillOpacity={1} fill="url(#colorSources)" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Consolidation Log */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 px-1">
          <History size={16} className="text-muted-foreground" />
          <h3 className="text-sm font-bold uppercase tracking-widest text-muted-foreground">Knowledge Integration Log</h3>
        </div>
        <ScrollArea className="h-[400px] rounded-xl border border-border bg-muted/20 pr-4">
          <div className="p-4 space-y-3">
            {cycles.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-muted-foreground/40">
                <Moon size={40} strokeWidth={1} />
                <p className="text-sm mt-2">No consolidation events found</p>
              </div>
            ) : (
              cycles.slice(0, 50).map((cycle) => (
                <Card
                  key={cycle.id}
                  className="bg-card/80 border-border hover:bg-card hover:border-border/80 transition-all shadow-sm"
                >
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <Badge variant="outline" className="font-mono text-[10px] text-accent border-accent/20 bg-accent/5">
                        {cycle.scope}
                      </Badge>
                      <span className="text-[10px] font-mono text-muted-foreground flex items-center gap-1">
                        <Clock size={10} /> {new Date(cycle.consolidated_at * 1000).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="text-sm text-foreground mb-3 leading-relaxed">{cycle.summary}</p>
                    <div className="flex items-center gap-2">
                      <div className="h-1 flex-1 bg-muted rounded-full overflow-hidden">
                        <div className="h-full bg-accent/40" style={{ width: `${Math.min(100, cycle.source_count * 2)}%` }}></div>
                      </div>
                      <span className="text-[10px] font-mono text-muted-foreground shrink-0 uppercase tracking-tighter">
                        {cycle.source_count} vectors merged
                      </span>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
};
