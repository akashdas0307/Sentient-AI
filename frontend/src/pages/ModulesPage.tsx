import React, { useState, useEffect } from 'react';
import { Activity, RefreshCw, BarChart3, Layers, Zap, Info } from 'lucide-react';
import { useSentientStore } from '../store/useSentientStore';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';

export const ModulesPage: React.FC = () => {
  const healthSnapshot = useSentientStore((s) => s.healthSnapshot);
  const [loading, setLoading] = useState(false);

  const fetchHealth = async () => {
    setLoading(true);
    try {
      await fetch('/api/health').then(r => r.json());
    } catch { /* data arrives via WS anyway */ }
    setLoading(false);
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const modules = healthSnapshot
    ? Object.entries(healthSnapshot).map(([name, data]) => ({
        name,
        status: data.status,
        pulses: data.pulse_count,
        last_pulse: (data as any).last_pulse_timestamp ?? (data as any).last_pulse,
      }))
    : [];

  const chartData = modules.map((m) => ({
    name: m.name.length > 10 ? m.name.slice(0, 10) + '...' : m.name,
    pulses: m.pulses,
    status: m.status,
  }));

  const statusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'healthy': return 'var(--success)';
      case 'degraded': return 'var(--warning)';
      case 'error': return 'var(--danger)';
      default: return 'var(--text-disabled)';
    }
  };

  const getStatusBadge = (status: string) => {
    const color = statusColor(status);
    const label = (status || 'unknown').toUpperCase();

    let variant: "default" | "outline" | "secondary" | "destructive" = "outline";
    if (status === 'error') variant = "destructive";

    return (
      <Badge
        variant={variant}
        className={cn(
          "font-mono text-[10px] tracking-widest px-2 py-0.5 border",
          status === 'healthy' && "text-success border-success/20 bg-success/5",
          status === 'degraded' && "text-warning border-warning/20 bg-warning/5",
          status === 'unknown' && "text-muted-foreground border-border bg-muted/20"
        )}
      >
        {label}
      </Badge>
    );
  };

  return (
    <div className="p-6 space-y-8 max-w-6xl mx-auto w-full">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="text-2xl font-bold tracking-tight text-foreground">Module Architecture</h2>
          <p className="text-sm text-muted-foreground">Real-time telemetry and subsystem integrity monitoring.</p>
        </div>
        <Button
          variant="outline"
          size="icon"
          onClick={fetchHealth}
          className={cn("rounded-full h-10 w-10 border-border hover:bg-muted/50", loading && "animate-spin")}
        >
          <RefreshCw size={16} className="text-muted-foreground" />
        </Button>
      </div>

      {modules.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground space-y-4">
          <Activity size={48} strokeWidth={1} className="animate-pulse opacity-20" />
          <div className="text-center">
            <p className="text-sm font-medium">Synchronizing telemetry stream...</p>
            <p className="text-xs text-muted-foreground mt-1 font-mono uppercase tracking-tighter">Connecting to Thalamus host</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Visualizations */}
          <div className="lg:col-span-2 space-y-8">
            <Card className="bg-card border-border shadow-md overflow-hidden">
              <CardHeader className="border-b border-border/50 bg-muted/20 pb-3">
                <CardTitle className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground flex items-center gap-2">
                  <Zap size={14} className="text-warning" /> Throughput Distribution
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-8">
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-default)" opacity={0.3} />
                    <XAxis
                      dataKey="name"
                      tick={{ fill: 'var(--text-muted)', fontSize: 10, fontWeight: 500 }}
                      axisLine={false}
                      tickLine={false}
                      dy={10}
                    />
                    <YAxis
                      tick={{ fill: 'var(--text-muted)', fontSize: 10, fontWeight: 500 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      cursor={{ fill: 'var(--bg-3)', opacity: 0.4 }}
                      contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border-default)', borderRadius: '12px', fontSize: '12px', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.5)' }}
                      labelStyle={{ color: 'var(--text-primary)', fontWeight: 'bold', marginBottom: '4px' }}
                    />
                    <Bar dataKey="pulses" radius={[6, 6, 0, 0]} barSize={40}>
                      {chartData.map((entry, i) => (
                        <Cell key={i} fill={statusColor(entry.status)} fillOpacity={0.8} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
              <CardFooter className="bg-muted/10 border-t border-border/50 py-3 flex justify-center gap-6">
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-success" />
                  <span className="text-[10px] font-mono text-muted-foreground uppercase">Stable</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-warning" />
                  <span className="text-[10px] font-mono text-muted-foreground uppercase">Degraded</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-danger" />
                  <span className="text-[10px] font-mono text-muted-foreground uppercase">Critical</span>
                </div>
              </CardFooter>
            </Card>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card className="bg-card/50 border-border hover:border-primary/20 transition-colors shadow-sm">
                <CardContent className="p-6 flex items-center gap-4">
                  <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20">
                    <Layers size={24} className="text-primary" />
                  </div>
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Orchestration</p>
                    <p className="text-xl font-bold text-foreground">Multi-Core</p>
                  </div>
                </CardContent>
              </Card>
              <Card className="bg-card/50 border-border hover:border-accent/20 transition-colors shadow-sm">
                <CardContent className="p-6 flex items-center gap-4">
                  <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center border border-accent/20">
                    <BarChart3 size={24} className="text-accent" />
                  </div>
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Aggregated Pulses</p>
                    <p className="text-xl font-bold text-foreground">
                      {modules.reduce((acc, m) => acc + m.pulses, 0).toLocaleString()}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Module List Sidebar */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 px-1">
              <Layers size={16} className="text-muted-foreground" />
              <h3 className="text-sm font-bold uppercase tracking-widest text-muted-foreground">Subsystem Inventory</h3>
            </div>
            <ScrollArea className="h-[calc(100vh-280px)] pr-4">
              <div className="space-y-3 pb-6">
                {modules.map((mod) => (
                  <Card
                    key={mod.name}
                    className="bg-card/40 border-border hover:bg-card hover:border-border/80 transition-all cursor-default group"
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-sm font-mono font-bold text-foreground tracking-tight group-hover:text-primary transition-colors">
                          {mod.name.toUpperCase()}
                        </span>
                        {getStatusBadge(mod.status)}
                      </div>
                      <div className="flex items-center justify-between mt-4">
                        <div className="flex items-center gap-1.5">
                          <Zap size={12} className="text-warning" />
                          <span className="text-[11px] font-mono text-muted-foreground">{mod.pulses} Pulses</span>
                        </div>
                        <span className="text-[10px] font-mono text-muted-foreground opacity-40">
                          {mod.last_pulse ? new Date(mod.last_pulse * 1000).toLocaleTimeString([], { hour12: false }) : 'N/A'}
                        </span>
                      </div>
                      <div className="w-full h-1 bg-muted rounded-full mt-3 overflow-hidden">
                        <div
                          className="h-full bg-primary/30 transition-all duration-500"
                          style={{ width: `${Math.min(100, (mod.pulses / 1000) * 100)}%` }}
                        />
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </ScrollArea>
          </div>
        </div>
      )}
    </div>
  );
};
