import React from 'react';
import { Activity, Zap, AlertTriangle, Clock, DollarSign } from 'lucide-react';
import { useSentientStore } from '../store/useSentientStore';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

export const GatewayPage: React.FC = () => {
  const gatewayStatus = useSentientStore((s) => s.gatewayStatus);
  const gatewayCalls = useSentientStore((s) => s.gatewayCalls);

  const formatCost = (cost: number) => {
    if (cost < 0.0001) return '<$0.0001';
    return `$${cost.toFixed(4)}`;
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const healthColor = (score: number) => {
    if (score >= 0.9) return 'text-success border-success/20 bg-success/5';
    if (score >= 0.7) return 'text-warning border-warning/20 bg-warning/5';
    return 'text-destructive border-destructive/20 bg-destructive/5';
  };

  const getCallBorderColor = (call: typeof gatewayCalls[0]) => {
    if (call.error) return 'border-destructive/50';
    if (call.fallback_used) return 'border-warning/50';
    return 'border-border/50';
  };

  const getCallAccent = (call: typeof gatewayCalls[0]) => {
    if (call.error) return 'bg-destructive/10';
    if (call.fallback_used) return 'bg-warning/10';
    return 'bg-primary/5';
  };

  return (
    <div className="h-full flex flex-col bg-background overflow-hidden">
      {/* Header */}
      <div className="p-6 border-b border-border bg-card/30 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-6">
          <div className="space-y-1">
            <h2 className="text-2xl font-bold tracking-tight text-foreground">Inference Gateway</h2>
            <p className="text-sm text-muted-foreground uppercase tracking-widest font-mono text-[10px]">Model routing • Cost tracking • Fallback events</p>
          </div>
          <Badge variant="outline" className="font-mono text-xs border-primary/20 text-primary px-3">
            <Zap size={12} className="mr-1" /> LIVE
          </Badge>
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-3 gap-4">
          <Card className="bg-card/50 border-border">
            <CardContent className="flex items-center gap-3 p-4">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                <Activity size={18} className="text-primary" />
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono">Total Calls</p>
                <p className="text-xl font-bold font-mono">{gatewayStatus?.total_calls ?? 0}</p>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card/50 border-border">
            <CardContent className="flex items-center gap-3 p-4">
              <div className="w-10 h-10 rounded-lg bg-success/10 flex items-center justify-center">
                <DollarSign size={18} className="text-success" />
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono">Total Cost</p>
                <p className="text-xl font-bold font-mono">{formatCost(gatewayStatus?.total_cost_usd ?? 0)}</p>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card/50 border-border">
            <CardContent className="flex items-center gap-3 p-4">
              <div className="w-10 h-10 rounded-lg bg-warning/10 flex items-center justify-center">
                <AlertTriangle size={18} className="text-warning" />
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono">Fallbacks</p>
                <p className="text-xl font-bold font-mono">
                  {gatewayStatus ? Object.values(gatewayStatus.endpoints).reduce((sum, ep) => sum + ep.failure_count, 0) : 0}
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Endpoints Table */}
      <div className="px-6 py-4 border-b border-border">
        <h3 className="text-sm font-bold tracking-tight mb-3 flex items-center gap-2">
          <Activity size={14} className="text-primary" />
          Endpoint Health
        </h3>
        {gatewayStatus && Object.keys(gatewayStatus.endpoints).length > 0 ? (
          <div className="space-y-2">
            {Object.entries(gatewayStatus.endpoints).map(([name, metrics]) => (
              <div key={name} className="flex items-center justify-between p-3 rounded-lg bg-card/50 border border-border">
                <div className="flex items-center gap-3">
                  <Badge variant="outline" className="font-mono text-xs">
                    {name}
                  </Badge>
                </div>
                <div className="flex items-center gap-6">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono">Health</span>
                    <Badge variant="outline" className={cn("font-mono text-xs", healthColor(metrics.health_score))}>
                      {(metrics.health_score * 100).toFixed(0)}%
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono">S/F</span>
                    <span className="text-xs font-mono text-success">{metrics.success_count}</span>
                    <span className="text-xs font-mono text-muted-foreground">/</span>
                    <span className="text-xs font-mono text-destructive">{metrics.failure_count}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground italic">No endpoint data available</p>
        )}
      </div>

      {/* Recent Calls Stream */}
      <div className="flex-1 px-6 py-4 overflow-hidden flex flex-col">
        <h3 className="text-sm font-bold tracking-tight mb-3 flex items-center gap-2">
          <Zap size={14} className="text-primary" />
          Recent Inference Calls
        </h3>
        <ScrollArea className="flex-1">
          <div className="space-y-2 max-w-5xl">
            {gatewayCalls.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-muted-foreground space-y-3 opacity-30">
                <Zap size={48} strokeWidth={1} />
                <p className="text-sm uppercase tracking-widest font-mono">No inference calls yet</p>
              </div>
            ) : (
              gatewayCalls.map((call, i) => (
                <div
                  key={`${call.timestamp}-${i}`}
                  className={cn(
                    "p-4 rounded-xl border transition-all duration-200",
                    getCallBorderColor(call),
                    getCallAccent(call)
                  )}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <Badge variant="outline" className="font-mono text-[10px]">
                        {call.model_label}
                      </Badge>
                      {call.fallback_used && (
                        <Badge variant="outline" className="text-warning border-warning/20 bg-warning/5 font-mono text-[10px]">
                          FALLBACK
                        </Badge>
                      )}
                      {call.error && (
                        <Badge variant="outline" className="text-destructive border-destructive/20 bg-destructive/5 font-mono text-[10px]">
                          FAILED
                        </Badge>
                      )}
                      <span className="text-[10px] font-mono text-muted-foreground">
                        {call.provider}
                      </span>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-[10px] font-mono text-muted-foreground flex items-center gap-1">
                        <Clock size={10} /> {new Date(call.timestamp * 1000).toLocaleTimeString([], { hour12: false, fractionalSecondDigits: 3 })}
                      </span>
                      <span className="text-[10px] font-mono">
                        {formatDuration(call.duration_ms)}
                      </span>
                      {call.cost_usd > 0 && (
                        <span className="text-[10px] font-mono text-success">
                          {formatCost(call.cost_usd)}
                        </span>
                      )}
                    </div>
                  </div>

                  {call.error ? (
                    <p className="text-xs font-mono text-destructive">{call.error}</p>
                  ) : (
                    <div className="flex items-center gap-4 text-[10px] font-mono text-muted-foreground">
                      <span>In: {call.tokens_in} tok</span>
                      <Separator orientation="vertical" className="h-3" />
                      <span>Out: {call.tokens_out} tok</span>
                      <Separator orientation="vertical" className="h-3" />
                      <span>Actual: {call.model_actual}</span>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
};
