import React, { useState, useEffect } from 'react';
import { User, Lock, Unlock, Zap, Brain, Clock, Shield, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

interface PersonaState {
  maturity_stage: string;
  personality_traits: Record<string, any>;
  drift_log: Array<{
    timestamp: number;
    drift_type: string;
    description: string;
    severity: string;
  }>;
  constitutional_locked: boolean;
  dynamic_state: {
    energy_level: number;
    current_mood: Record<string, number>;
    current_focus: string;
  };
}

const MATURITY_STAGES = ['nascent', 'forming', 'developing', 'mature'];
const STAGE_INDEX: Record<string, number> = {
  nascent: 0, forming: 1, developing: 2, mature: 3
};

export const IdentityPage: React.FC = () => {
  const [state, setState] = useState<PersonaState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchState = async () => {
      try {
        const res = await fetch('/api/persona/state');
        if (res.ok) {
          const data = await res.json();
          setState(data);
        } else {
          setError('Persona state unavailable');
        }
      } catch {
        setError('Failed to fetch persona state');
      }
      setLoading(false);
    };
    fetchState();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
        <div className="w-12 h-12 border-4 border-muted border-t-primary rounded-full animate-spin" />
        <p className="mt-4 text-sm font-mono uppercase tracking-widest animate-pulse">Loading identity state...</p>
      </div>
    );
  }

  if (error || !state) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground space-y-4">
        <AlertTriangle size={48} strokeWidth={1} className="opacity-30" />
        <p className="text-sm">{error || 'No identity state available'}</p>
      </div>
    );
  }

  const stageIndex = STAGE_INDEX[state.maturity_stage] ?? 0;
  const stageProgress = ((stageIndex + 1) / MATURITY_STAGES.length) * 100;

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto w-full">
      {/* Header */}
      <div className="space-y-1">
        <h2 className="text-2xl font-bold tracking-tight text-foreground">Identity State</h2>
        <p className="text-sm text-muted-foreground">Constitutional core, personality profile, and dynamic state.</p>
      </div>

      {/* Identity Header */}
      <Card className="bg-card border-border shadow-md overflow-hidden">
        <CardContent className="p-6">
          <div className="flex flex-col md:flex-row items-start md:items-center gap-6">
            <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20 shrink-0">
              <User size={32} className="text-primary" />
            </div>
            <div className="flex-1 space-y-3">
              <div className="flex items-center gap-3 flex-wrap">
                <Badge
                  variant="outline"
                  className={cn(
                    "font-mono text-sm px-3 py-1 border",
                    state.constitutional_locked
                      ? "text-success border-success/20 bg-success/5"
                      : "text-warning border-warning/20 bg-warning/5"
                  )}
                >
                  {state.constitutional_locked ? <Lock size={14} className="mr-1" /> : <Unlock size={14} className="mr-1" />}
                  {state.constitutional_locked ? 'CONSTITUTIONAL LOCK ENGAGED' : 'CONSTITUTIONAL LOCK DISENGAGED'}
                </Badge>
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Brain size={16} className="text-muted-foreground" />
                  <span className="text-sm font-mono text-muted-foreground uppercase tracking-widest">Maturity Stage</span>
                </div>
                <div className="flex items-center gap-3">
                  <Badge
                    variant="outline"
                    className="text-lg font-bold px-4 py-1 border-primary/20 bg-primary/5 text-primary"
                  >
                    {state.maturity_stage.toUpperCase()}
                  </Badge>
                  <div className="flex-1 max-w-[200px] h-2 bg-muted rounded-full overflow-hidden">
                    <div className="h-full bg-primary/60 rounded-full transition-all" style={{ width: `${stageProgress}%` }} />
                  </div>
                  <span className="text-xs font-mono text-muted-foreground">
                    {stageIndex + 1} / {MATURITY_STAGES.length}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Dynamic State */}
      <Card className="bg-card border-border shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
            <Zap size={14} className="text-warning" /> Dynamic State
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">Energy Level</span>
                <span className="text-sm font-mono font-bold text-foreground">{(state.dynamic_state.energy_level * 100).toFixed(0)}%</span>
              </div>
              <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-warning/60 rounded-full transition-all" style={{ width: `${state.dynamic_state.energy_level * 100}%` }} />
              </div>
            </div>
            <div className="space-y-2">
              <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">Current Focus</span>
              <div className="h-8 flex items-center px-3 rounded-lg bg-muted/50 border border-border">
                <span className="text-sm font-mono text-foreground truncate">
                  {state.dynamic_state.current_focus || 'idle'}
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">Current Mood</span>
              <div className="flex flex-wrap gap-1">
                {Object.keys(state.dynamic_state.current_mood).length === 0 ? (
                  <span className="text-xs font-mono text-muted-foreground italic">no active mood</span>
                ) : (
                  Object.entries(state.dynamic_state.current_mood).map(([emotion, intensity]) => (
                    <Badge key={emotion} variant="outline" className="text-[10px] font-mono border-border/50 bg-muted/30">
                      {emotion}: {(Number(intensity) * 100).toFixed(0)}%
                    </Badge>
                  ))
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Personality Traits */}
      <Card className="bg-card border-border shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
            <Shield size={14} className="text-primary" /> Personality Traits
          </CardTitle>
        </CardHeader>
        <CardContent>
          {Object.keys(state.personality_traits).length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground/40 space-y-2">
              <Brain size={32} strokeWidth={1} />
              <p className="text-sm italic">No personality traits have emerged yet</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Object.entries(state.personality_traits).map(([trait, data]: [string, any]) => (
                <div key={trait} className="flex items-center justify-between p-3 rounded-lg bg-muted/30 border border-border/50">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-foreground capitalize">{trait.replace(/_/g, ' ')}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-1.5 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary/60 rounded-full transition-all"
                        style={{ width: `${Math.min(100, (data.strength ?? 0) * 100)}%` }}
                      />
                    </div>
                    <span className="text-[10px] font-mono text-muted-foreground w-8 text-right">
                      {(data.strength ?? 0).toFixed(2)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Drift Log */}
      <Card className="bg-card border-border shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
            <AlertTriangle size={14} className="text-warning" /> Identity Drift Log
          </CardTitle>
        </CardHeader>
        <CardContent>
          {state.drift_log.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground/40 space-y-2">
              <Shield size={32} strokeWidth={1} />
              <p className="text-sm italic">No drift events recorded</p>
            </div>
          ) : (
            <ScrollArea className="h-[300px]">
              <div className="space-y-3">
                {state.drift_log.map((entry, i) => (
                  <div key={i} className="flex gap-4 p-4 rounded-lg bg-muted/30 border border-border/50">
                    <div className="flex flex-col items-center gap-1 shrink-0">
                      <div className="w-2 h-2 rounded-full bg-warning" />
                      <div className="w-px flex-1 bg-border/50" />
                    </div>
                    <div className="flex-1 space-y-2 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <Badge variant="outline" className="text-[10px] font-mono border-warning/20 bg-warning/5 text-warning">
                          {entry.drift_type?.toUpperCase() ?? 'DRIFT'}
                        </Badge>
                        <span className="text-[10px] font-mono text-muted-foreground flex items-center gap-1">
                          <Clock size={10} />
                          {entry.timestamp ? new Date(entry.timestamp * 1000).toLocaleString() : 'unknown'}
                        </span>
                      </div>
                      <p className="text-sm text-foreground leading-relaxed">{entry.description}</p>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono text-muted-foreground uppercase">Severity:</span>
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-[10px] font-mono",
                            entry.severity === 'high' && "text-destructive border-destructive/20 bg-destructive/5",
                            entry.severity === 'medium' && "text-warning border-warning/20 bg-warning/5",
                            entry.severity === 'low' && "text-success border-success/20 bg-success/5"
                          )}
                        >
                          {entry.severity ?? 'unknown'}
                        </Badge>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
