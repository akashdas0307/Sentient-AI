import React, { useState } from 'react';
import { useSentientStore } from '../store/useSentientStore';
import { Card, StatCard, Sparkline, Pill, Icon } from '../components/shared';
import type { InferenceCall } from '../types/gateway';
import { formatTimestamp as formatTimestampShort, formatDuration, formatCost as formatCostUtil } from '../lib/format';

// ─── Outcome colors ───
const OUTCOME_COLORS = {
  SUCCESS: 'var(--success)',
  FALLBACK: 'var(--warning)',
  ERROR: 'var(--destructive)',
} as const;

type Outcome = keyof typeof OUTCOME_COLORS;

// ─── Helpers ───
const getOutcome = (call: InferenceCall): Outcome => {
  if (call.error) return 'ERROR';
  if (call.fallback_used) return 'FALLBACK';
  return 'SUCCESS';
};

// ─── GaugeArc (semi-circle) ───
const GaugeArc: React.FC<{ value: number; size?: number }> = ({ value, size = 72 }) => {
  const r = (size - 8) / 2;
  const circumference = Math.PI * r;
  const offset = circumference * (1 - value);
  return (
    <svg width={size} height={size / 2 + 8} style={{ display: 'block' }}>
      <path
        d={`M 4 ${size / 2} A ${r} ${r} 0 0 1 ${size - 4} ${size / 2}`}
        fill="none"
        stroke="var(--surface-tertiary)"
        strokeWidth="4"
        strokeLinecap="round"
      />
      <path
        d={`M 4 ${size / 2} A ${r} ${r} 0 0 1 ${size - 4} ${size / 2}`}
        fill="none"
        stroke="var(--primary)"
        strokeWidth="4"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
      />
      <text
        x={size / 2}
        y={size / 2 - 2}
        textAnchor="middle"
        fill="var(--foreground)"
        fontSize="14"
        fontWeight="700"
        fontFamily="IBM Plex Mono"
      >
        {Math.round(value * 100)}%
      </text>
    </svg>
  );
};

// ─── Mock data ───
const MOCK_ENDPOINTS: Record<string, { health_score: number; success_count: number; failure_count: number }> = {
  'glm-5.1': { health_score: 0.97, success_count: 1240, failure_count: 38 },
  'kimi-k2.5': { health_score: 0.94, success_count: 876, failure_count: 55 },
  'minimax-m2.7': { health_score: 0.89, success_count: 2103, failure_count: 259 },
};

const MOCK_SPARK: Record<string, number[]> = {
  'glm-5.1': [12, 18, 14, 22, 17, 25, 19, 28, 24, 31],
  'kimi-k2.5': [8, 12, 10, 15, 13, 18, 16, 20, 17, 22],
  'minimax-m2.7': [20, 25, 18, 30, 22, 35, 28, 40, 33, 45],
};

const MOCK_CALLS: InferenceCall[] = Array.from({ length: 40 }, (_, i) => {
  const models = ['glm-5.1', 'kimi-k2.5', 'minimax-m2.7'];
  const providers = ['ollama', 'openai', 'anthropic'];
  const idx = i % 3;
  const err = i % 17 === 0 ? 'Request timeout after 30s' : i % 23 === 0 ? 'Model capacity exceeded' : null;
  const fallback = i % 11 === 0 && !err;
  return {
    timestamp: Date.now() - i * 45000,
    model_label: models[idx],
    model_actual: models[idx] + '-latest',
    provider: providers[idx],
    fallback_used: fallback,
    duration_ms: 200 + Math.floor(Math.random() * 2800),
    tokens_in: 100 + Math.floor(Math.random() * 2000),
    tokens_out: 50 + Math.floor(Math.random() * 800),
    cost_usd: parseFloat((Math.random() * 0.05).toFixed(6)),
    error: err,
  };
});

const MOCK_CALLS_SPARK: number[] = [5, 8, 12, 9, 15, 18, 14, 22, 19, 25, 21, 28, 24, 30, 27];

// ─── Call Row ───
const CallRow: React.FC<{ call: InferenceCall; expanded: boolean; onToggle: () => void }> = ({ call, expanded, onToggle }) => {
  const outcome = getOutcome(call);
  const borderColor = OUTCOME_COLORS[outcome];

  return (
    <div
      onClick={onToggle}
      style={{
        borderLeft: `3px solid ${borderColor}`,
        background: 'var(--surface)',
        borderTop: '1px solid var(--border)',
        borderRight: '1px solid var(--border)',
        borderBottom: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        padding: '12px 16px',
        cursor: 'pointer',
        transition: 'background 150ms ease',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        {/* Left: model info */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <Pill border="var(--border)">{call.model_label}</Pill>
          {call.fallback_used && (
            <Pill color="var(--warning)" bg="oklch(0.78 0.16 72 / 0.10)" border="var(--warning)">FALLBACK</Pill>
          )}
          {call.error && (
            <Pill color="var(--destructive)" bg="oklch(0.65 0.23 26 / 0.10)" border="var(--destructive)">FAILED</Pill>
          )}
          <span style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>{call.provider}</span>
        </div>

        {/* Right: metrics */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexShrink: 0 }}>
          <span style={{ fontSize: 10, color: 'var(--muted-foreground)', fontFamily: 'IBM Plex Mono' }}>
            {formatTimestampShort(call.timestamp, { fractional: true })}
          </span>
          <span style={{ fontSize: 11, fontFamily: 'IBM Plex Mono', color: 'var(--foreground)' }}>
            {formatDuration(call.duration_ms)}
          </span>
          {call.cost_usd > 0 && (
            <span style={{ fontSize: 10, fontFamily: 'IBM Plex Mono', color: 'var(--success)' }}>
              {formatCostUtil(call.cost_usd)}
            </span>
          )}
          <Pill color={borderColor} border={`${borderColor}66`}>
            {outcome}
          </Pill>
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
          {call.error ? (
            <div style={{ fontSize: 11, fontFamily: 'IBM Plex Mono', color: 'var(--destructive)', background: 'oklch(0.65 0.23 26 / 0.06)', padding: '8px 12px', borderRadius: 'var(--radius-sm)' }}>
              {call.error}
            </div>
          ) : (
            <div style={{ display: 'flex', gap: 24, fontSize: 10, fontFamily: 'IBM Plex Mono', color: 'var(--muted-foreground)' }}>
              <span>In: <strong style={{ color: 'var(--foreground)' }}>{call.tokens_in}</strong> tok</span>
              <span>Out: <strong style={{ color: 'var(--foreground)' }}>{call.tokens_out}</strong> tok</span>
              <span>Actual: <strong style={{ color: 'var(--foreground)' }}>{call.model_actual}</strong></span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ─── GatewayPage ───
const GatewayPageContent: React.FC = () => {
  const gatewayStatus = useSentientStore((s) => s.gatewayStatus);
  const gatewayCalls = useSentientStore((s) => s.gatewayCalls);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  const totalCalls = gatewayStatus?.total_calls ?? 0;
  const totalCost = gatewayStatus?.total_cost_usd ?? 0;
  const endpoints = gatewayStatus?.endpoints ?? (Object.keys(MOCK_ENDPOINTS).length > 0 ? MOCK_ENDPOINTS : null);
  const calls = gatewayCalls.length > 0 ? gatewayCalls : MOCK_CALLS;

  const fallbackCount = endpoints
    ? Object.values(endpoints).reduce((sum: number, ep: any) => sum + ep.failure_count, 0)
    : 0;
  const fallbackRate = totalCalls > 0 ? fallbackCount / totalCalls : 0;

  const endpointList = endpoints ? Object.entries(endpoints) : Object.entries(MOCK_ENDPOINTS);

  const toggleExpand = (i: number) => {
    setExpandedIdx(prev => (prev === i ? null : i));
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Top section: stats + model health */}
      <div style={{ padding: '24px 24px 0', flexShrink: 0, maxWidth: 1400, width: '100%', margin: '0 auto' }}>
        {/* Stat row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
          <StatCard label="Total Calls Today" value={totalCalls.toLocaleString()} color="var(--foreground)" sparkData={MOCK_CALLS_SPARK} />
          <StatCard label="Total Cost Today" value={formatCostUtil(totalCost)} color="var(--success)" sparkData={MOCK_CALLS_SPARK.map(v => v * 0.0018)} />
          <StatCard label="Fallback Rate" value={`${(fallbackRate * 100).toFixed(1)}%`} color={fallbackRate > 0.05 ? 'var(--warning)' : 'var(--success)'} sparkData={MOCK_CALLS_SPARK.map(() => Math.random() * 0.08)} />
        </div>

        {/* Model health grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
          {endpointList.map(([name, metrics]: [string, any]) => (
            <Card key={name} style={{ padding: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                <div>
                  <div className="t-label" style={{ color: 'var(--muted-foreground)', marginBottom: 4 }}>{name}</div>
                  <div style={{ fontSize: 11, color: 'var(--subtle-foreground)', fontFamily: 'IBM Plex Mono' }}>
                    {metrics.success_count} success / {metrics.failure_count} failed
                  </div>
                </div>
                <GaugeArc value={metrics.health_score} size={72} />
              </div>

              {/* Latency mock */}
              <div style={{ display: 'flex', gap: 16, marginBottom: 12 }}>
                <div style={{ flex: 1 }}>
                  <div className="t-label" style={{ color: 'var(--muted-foreground)', marginBottom: 4 }}>p50</div>
                  <div style={{ fontSize: 12, fontFamily: 'IBM Plex Mono', color: 'var(--foreground)' }}>
                    {(120 + Math.random() * 300).toFixed(0)}ms
                  </div>
                </div>
                <div style={{ flex: 1 }}>
                  <div className="t-label" style={{ color: 'var(--muted-foreground)', marginBottom: 4 }}>p95</div>
                  <div style={{ fontSize: 12, fontFamily: 'IBM Plex Mono', color: 'var(--foreground)' }}>
                    {(600 + Math.random() * 1200).toFixed(0)}ms
                  </div>
                </div>
                <div style={{ flex: 1 }}>
                  <div className="t-label" style={{ color: 'var(--muted-foreground)', marginBottom: 4 }}>avg cost</div>
                  <div style={{ fontSize: 12, fontFamily: 'IBM Plex Mono', color: 'var(--success)' }}>
                    ${(0.002 + Math.random() * 0.015).toFixed(4)}
                  </div>
                </div>
              </div>

              {/* Error rate */}
              <div style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span className="t-label" style={{ color: 'var(--muted-foreground)' }}>Error Rate</span>
                  <span style={{ fontSize: 10, fontFamily: 'IBM Plex Mono', color: metrics.failure_count / (metrics.success_count + metrics.failure_count) > 0.05 ? 'var(--warning)' : 'var(--success)' }}>
                    {(metrics.failure_count / (metrics.success_count + metrics.failure_count) * 100).toFixed(1)}%
                  </span>
                </div>
                <div style={{ height: 4, background: 'var(--surface-tertiary)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${(metrics.failure_count / (metrics.success_count + metrics.failure_count)) * 100}%`, background: metrics.failure_count / (metrics.success_count + metrics.failure_count) > 0.05 ? 'var(--warning)' : 'var(--success)', borderRadius: 2 }} />
                </div>
              </div>

              {/* Sparkline */}
              <div>
                <div className="t-label" style={{ color: 'var(--muted-foreground)', marginBottom: 6 }}>Call Volume · Last 10 cycles</div>
                <Sparkline data={MOCK_SPARK[name] || MOCK_SPARK['glm-5.1']} width={200} height={32} color="var(--primary)" filled />
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* Recent calls stream */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', padding: '0 24px 24px', minHeight: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, flexShrink: 0 }}>
          <Icon name="zap" size={14} style={{ color: 'var(--primary)' }} />
          <span className="t-label" style={{ color: 'var(--muted-foreground)' }}>RECENT CALLS</span>
          <span style={{ marginLeft: 'auto', fontSize: 10, fontFamily: 'IBM Plex Mono', color: 'var(--muted-foreground)' }}>
            {calls.length} calls
          </span>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {calls.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 12, opacity: 0.3 }}>
              <Icon name="zap" size={48} style={{ color: 'var(--muted-foreground)' }} />
              <span className="t-label" style={{ color: 'var(--muted-foreground)' }}>No inference calls yet</span>
            </div>
          ) : (
            calls.map((call, i) => (
              <CallRow
                key={`${call.timestamp}-${i}`}
                call={call}
                expanded={expandedIdx === i}
                onToggle={() => toggleExpand(i)}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export const GatewayPage: React.FC = () => <GatewayPageContent />;
export default GatewayPage;
