import React, { createContext, useContext, useState, useRef, useEffect, useCallback, ReactNode } from 'react';

// ─── Navigation context ───
interface NavContextValue {
  page: string;
  setPage: (page: string) => void;
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
}
const NavContext = createContext<NavContextValue>({ page: 'chat', setPage: () => {}, collapsed: false, setCollapsed: () => {} });
export const useNav = () => useContext(NavContext);

// ─── Command Palette context ───
interface CmdContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
}
const CmdContext = createContext<CmdContextValue>({ open: false, setOpen: () => {} });
export const useCmd = () => useContext(CmdContext);

// ─── Icon components ───
interface IconProps {
  name: string;
  size?: number;
  style?: React.CSSProperties;
}

const Icons: Record<string, React.FC<React.SVGAttributes<SVGElement>>> = {
  chat: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>,
  modules: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>,
  memory: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3"/></svg>,
  graph: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="18" r="3"/><line x1="8.5" y1="7.5" x2="15.5" y2="16.5"/><line x1="15.5" y1="7.5" x2="8.5" y2="16.5"/></svg>,
  sleep: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>,
  events: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>,
  gateway: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>,
  identity: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>,
  send: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>,
  chevronLeft: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6"/></svg>,
  chevronRight: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>,
  chevronDown: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>,
  search: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>,
  x: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>,
  trash: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>,
  download: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>,
  pause: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>,
  play: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>,
  lock: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>,
  unlock: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>,
  filter: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>,
  arrowDown: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/></svg>,
  bot: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/></svg>,
  user: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>,
  copy: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>,
  sparkles: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3z"/></svg>,
  zap: (p) => <svg {...p} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>,
};

export const Icon: React.FC<IconProps> = ({ name, size = 16, style = {}, ...rest }) => {
  const Comp = Icons[name];
  if (!Comp) return null;
  return <Comp width={size} height={size} style={{ flexShrink: 0, ...style }} {...rest as Record<string, unknown>} />;
};

// ─── Sparkline ───
interface SparklineProps {
  data?: number[];
  width?: number;
  height?: number;
  color?: string;
  filled?: boolean;
}

export const Sparkline: React.FC<SparklineProps> = ({ data = [], width = 80, height = 24, color = 'var(--primary)', filled = false }) => {
  if (data.length < 2) return <div style={{ width, height }} />;
  const min = Math.min(...data);
  const max = Math.max(...data) || 1;
  const range = max - min || 1;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 2) - 1;
    return `${x},${y}`;
  }).join(' ');
  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      {filled && <polygon points={`0,${height} ${points} ${width},${height}`} fill={color} opacity="0.15" />}
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
};

// ─── Pill / Badge ───
interface PillProps extends React.HTMLAttributes<HTMLSpanElement> {
  children: ReactNode;
  color?: string;
  bg?: string;
  border?: string;
}

export const Pill: React.FC<PillProps> = ({ children, color, bg, border, style = {}, ...rest }) => (
  <span style={{
    display: 'inline-flex', alignItems: 'center', gap: 4,
    padding: '2px 8px', borderRadius: 999,
    fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.2em',
    color: color || 'var(--muted-foreground)',
    background: bg || 'transparent',
    border: `1px solid ${border || 'var(--border)'}`,
    whiteSpace: 'nowrap', lineHeight: 1.2,
    ...style,
  }} {...rest}>{children}</span>
);

// ─── Card ───
interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  style?: React.CSSProperties;
  hover?: boolean;
  accent?: string;
  onClick?: () => void;
}

export const Card: React.FC<CardProps> = ({ children, style = {}, hover = false, accent, onClick, ...rest }) => {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={onClick}
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-xl)',
        padding: 24,
        position: 'relative',
        transition: 'background 150ms ease, border-color 150ms ease',
        cursor: onClick ? 'pointer' : 'default',
        ...(hover && hovered ? { background: 'var(--surface-secondary)', borderColor: 'var(--border-strong)' } : {}),
        ...style,
      }} {...rest}
    >
      {accent && <div style={{ position: 'absolute', left: 0, top: 16, bottom: 16, width: 2, borderRadius: 1, background: accent }} />}
      {children}
    </div>
  );
};

// ─── Stat Card ───
interface StatCardProps {
  label: string;
  value: string | number;
  color?: string;
  sparkData?: number[];
}

export const StatCard: React.FC<StatCardProps> = ({ label, value, color = 'var(--foreground)', sparkData }) => (
  <Card style={{ padding: 20 }}>
    <div className="t-label" style={{ color: 'var(--muted-foreground)', marginBottom: 8 }}>{label}</div>
    <div className="t-display" style={{ color }}>{value}</div>
    {sparkData && <div style={{ marginTop: 8 }}><Sparkline data={sparkData} width={100} height={20} color={color} filled /></div>}
  </Card>
);

// ─── Button ───
interface BtnProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: 'ghost' | 'outline' | 'primary' | 'destructive';
  size?: 'sm' | 'md' | 'lg' | 'icon' | 'icon-lg';
}

export const Btn: React.FC<BtnProps> = ({ children, variant = 'ghost', size = 'md', style = {}, disabled, ...rest }) => {
  const [hovered, setHovered] = useState(false);
  const base = {
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
    border: 'none', cursor: disabled ? 'default' : 'pointer',
    fontFamily: 'inherit', fontWeight: 600, fontSize: 12, letterSpacing: '0.05em',
    borderRadius: 999, transition: 'all 150ms ease',
    opacity: disabled ? 0.4 : 1,
    outline: 'none',
  };
  const sizes: Record<string, React.CSSProperties> = {
    sm: { padding: '4px 12px', fontSize: 10 },
    md: { padding: '8px 16px' },
    lg: { padding: '12px 24px', fontSize: 14 },
    icon: { padding: 8, width: 36, height: 36 },
    'icon-lg': { padding: 12, width: 48, height: 48 },
  };
  const variants: Record<string, React.CSSProperties> = {
    ghost: { background: hovered ? 'var(--surface-secondary)' : 'transparent', color: 'var(--muted-foreground)' },
    outline: { background: 'transparent', color: 'var(--muted-foreground)', border: '1px solid var(--border)', ...(hovered ? { borderColor: 'var(--border-strong)', background: 'var(--surface-secondary)' } : {}) },
    primary: { background: hovered ? 'oklch(0.72 0.22 36.66)' : 'var(--primary)', color: 'var(--primary-foreground)' },
    destructive: { background: hovered ? 'oklch(0.65 0.23 26 / 0.2)' : 'transparent', color: 'var(--destructive)' },
  };
  return (
    <button
      onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}
      disabled={disabled}
      style={{ ...base, ...sizes[size], ...variants[variant], ...style }}
      {...rest}
    >{children}</button>
  );
};

// ─── Gauge bar ───
interface GaugeBarProps {
  value?: number;
  max?: number;
  color?: string;
  width?: number;
  height?: number;
  label?: string;
}

export const GaugeBar: React.FC<GaugeBarProps> = ({ value = 0, max = 1, color = 'var(--primary)', width = 80, height = 6, label }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
    <div style={{ width, height, background: 'var(--surface-tertiary)', borderRadius: height / 2, overflow: 'hidden' }}>
      <div style={{ width: `${(value / max) * 100}%`, height: '100%', background: color, borderRadius: height / 2, transition: 'width 300ms ease' }} />
    </div>
    {label && <span style={{ fontSize: 10, color: 'var(--muted-foreground)', fontWeight: 700 }}>{label}</span>}
  </div>
);

// ─── Skeleton ───
interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  radius?: number;
  style?: React.CSSProperties;
}

export const Skeleton: React.FC<SkeletonProps> = ({ width = '100%', height = 16, radius = 8, style = {} }) => (
  <div className="shimmer" style={{ width, height, borderRadius: radius, ...style }} />
);

// ─── PageLoader ───
interface PageLoaderProps {
  label?: string;
  size?: number;
}

export const PageLoader: React.FC<PageLoaderProps> = ({ label = 'Loading...', size = 40 }) => (
  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 16 }}>
    <div style={{
      width: size, height: size, border: `${Math.max(3, size / 10)}px solid var(--surface-tertiary)`,
      borderTopColor: 'var(--primary)', borderRadius: '50%', animation: 'spin-stepped 1s steps(8) infinite',
    }} />
    {label && <span className="t-label" style={{ color: 'var(--muted-foreground)' }}>{label}</span>}
  </div>
);

// ─── Toast system ───
interface ToastContextValue {
  addToast: (msg: string, type?: string) => void;
}
const ToastContext = createContext<ToastContextValue>({ addToast: () => {} });
export const useToast = () => useContext(ToastContext);

interface Toast {
  id: number;
  msg: string;
  type: string;
}

interface ToastProviderProps {
  children: ReactNode;
}

export const ToastProvider: React.FC<ToastProviderProps> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const addToast = useCallback((msg: string, type = 'info') => {
    const id = Date.now();
    setToasts(t => [...t, { id, msg, type }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4000);
  }, []);
  const colors: Record<string, string> = { info: 'var(--primary)', error: 'var(--destructive)', success: 'var(--success)' };
  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div style={{ position: 'fixed', bottom: 16, right: 16, zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {toasts.map(t => (
          <div key={t.id} style={{
            background: 'var(--surface)', border: '1px solid var(--border)', borderLeft: `2px solid ${colors[t.type] || colors.info}`,
            borderRadius: 'var(--radius)', padding: '12px 16px', fontSize: 12, color: 'var(--foreground)',
            boxShadow: '0 1px 2px oklch(0 0 0 / 0.4)', maxWidth: 320,
            animation: 'fadeIn 200ms ease',
          }}>{t.msg}</div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

// ─── Command Palette ───
interface CommandItem {
  label: string;
  desc: string;
  page: string;
  icon: string;
}

export const CommandPalette: React.FC = () => {
  const { open, setOpen } = useCmd();
  const { setPage } = useNav();
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) { setQuery(''); setTimeout(() => inputRef.current?.focus(), 50); }
  }, [open]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); setOpen(!open); }
      if (e.key === 'Escape' && open) setOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, setOpen]);

  const commands: CommandItem[] = [
    { label: 'Chat', desc: 'Cognitive Link', page: 'chat', icon: 'chat' },
    { label: 'Modules', desc: 'System telemetry', page: 'modules', icon: 'modules' },
    { label: 'Memory', desc: 'Knowledge base', page: 'memory', icon: 'memory' },
    { label: 'Memory Graph', desc: 'Neural cartography', page: 'graph', icon: 'graph' },
    { label: 'Sleep', desc: 'Consolidation cycles', page: 'sleep', icon: 'sleep' },
    { label: 'Events', desc: 'Event stream', page: 'events', icon: 'events' },
    { label: 'Gateway', desc: 'Inference routing', page: 'gateway', icon: 'gateway' },
    { label: 'Identity', desc: 'Persona state', page: 'identity', icon: 'identity' },
  ];
  const filtered = commands.filter(c => c.label.toLowerCase().includes(query.toLowerCase()) || c.desc.toLowerCase().includes(query.toLowerCase()));

  if (!open) return null;
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 10000, background: 'var(--overlay)', display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: 120 }} onClick={() => setOpen(false)}>
      <div onClick={e => e.stopPropagation()} style={{ width: 520, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-xl)', overflow: 'hidden', boxShadow: '0 1px 2px oklch(0 0 0 / 0.4)' }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon name="search" size={16} style={{ color: 'var(--muted-foreground)' }} />
          <input ref={inputRef} value={query} onChange={e => setQuery(e.target.value)} placeholder="Search commands..." style={{
            flex: 1, background: 'transparent', border: 'none', outline: 'none', color: 'var(--foreground)',
            fontFamily: 'inherit', fontSize: 14,
          }} />
          <Pill style={{ fontSize: 9, padding: '1px 6px' }}>ESC</Pill>
        </div>
        <div style={{ maxHeight: 320, overflowY: 'auto', padding: 4 }}>
          {filtered.map(c => (
            <div key={c.page} onClick={() => { setPage(c.page); setOpen(false); }} style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', borderRadius: 'var(--radius-sm)',
              cursor: 'pointer', transition: 'background 100ms',
            }} onMouseEnter={e => { e.currentTarget.style.background = 'var(--surface-secondary)'; }}
               onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}>
              <Icon name={c.icon} size={16} style={{ color: 'var(--muted-foreground)' }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{c.label}</div>
                <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>{c.desc}</div>
              </div>
            </div>
          ))}
          {filtered.length === 0 && <div style={{ padding: 24, textAlign: 'center', color: 'var(--subtle-foreground)', fontSize: 12 }}>No results</div>}
        </div>
      </div>
    </div>
  );
};

// ─── Sidebar ───
interface SidebarProps {
  currentPage?: string;
  onNavigate?: (page: string) => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentPage = 'chat', onNavigate, collapsed = false, onToggleCollapse }) => {
  const { page, setPage, collapsed: navCollapsed, setCollapsed } = useNav();
  const activePage = currentPage || page;
  const setActivePage = onNavigate || setPage;
  const isCollapsed = collapsed !== undefined ? collapsed : navCollapsed;
  const toggleCollapse = onToggleCollapse || setCollapsed;

  const items = [
    { id: 'chat', label: 'Chat', icon: 'chat' },
    { id: 'modules', label: 'Modules', icon: 'modules' },
    { id: 'memory', label: 'Memory', icon: 'memory' },
    { id: 'graph', label: 'Memory Graph', icon: 'graph' },
    { id: 'sleep', label: 'Sleep', icon: 'sleep' },
    { id: 'events', label: 'Events', icon: 'events' },
    { id: 'gateway', label: 'Gateway', icon: 'gateway' },
    { id: 'identity', label: 'Identity', icon: 'identity' },
  ];
  const w = isCollapsed ? 64 : 240;

  return (
    <aside style={{
      width: w, minWidth: w, height: '100%', display: 'flex', flexDirection: 'column',
      borderRight: '1px solid var(--border)', background: 'var(--surface)', transition: 'width 200ms ease, min-width 200ms ease',
      overflow: 'hidden',
    }}>
      {/* Logo */}
      <div style={{
        height: 56, display: 'flex', alignItems: 'center', gap: 10,
        padding: '0 20px', borderBottom: '1px solid var(--border)',
        justifyContent: isCollapsed ? 'center' : 'flex-start',
      }}>
        <div style={{ width: 8, height: 8, borderRadius: 4, background: 'var(--primary)', flexShrink: 0 }} />
        {!isCollapsed && <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.15em', textTransform: 'uppercase' }}>SENTIENT</span>}
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '12px 8px', display: 'flex', flexDirection: 'column', gap: 2, overflowY: 'auto' }}>
        {items.map(item => {
          const active = activePage === item.id;
          return (
            <div key={item.id} onClick={() => setActivePage(item.id)} title={isCollapsed ? item.label : undefined}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: isCollapsed ? '10px 0' : '10px 12px',
                justifyContent: isCollapsed ? 'center' : 'flex-start',
                borderRadius: 'var(--radius)', cursor: 'pointer',
                position: 'relative', transition: 'background 150ms, color 150ms',
                background: active ? 'var(--primary-subtle)' : 'transparent',
                color: active ? 'var(--primary)' : 'var(--muted-foreground)',
              }}
              onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'var(--surface-secondary)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = ''; }}
            >
              {active && <div style={{ position: 'absolute', left: 0, top: 8, bottom: 8, width: 2, borderRadius: 1, background: 'var(--primary)' }} />}
              <Icon name={item.icon} size={18} />
              {!isCollapsed && <span style={{ fontSize: 13, fontWeight: active ? 600 : 400 }}>{item.label}</span>}
            </div>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <div style={{ padding: 8, borderTop: '1px solid var(--border)' }}>
        <Btn variant="ghost" size="icon" onClick={() => toggleCollapse(!isCollapsed)} style={{ width: '100%', height: 40 }}>
          <Icon name={isCollapsed ? 'chevronRight' : 'chevronLeft'} size={16} />
        </Btn>
      </div>
    </aside>
  );
};

// ─── Header ───
interface HeaderProps {
  currentPage?: string;
}

export const Header: React.FC<HeaderProps> = ({ currentPage }) => {
  const { page } = useNav();
  const { setOpen } = useCmd();
  const activePage = currentPage || page;
  const titles: Record<string, [string, string]> = {
    chat: ['Chat', 'Cognitive Link · Live session'],
    modules: ['Modules', '14 registered · monitoring active'],
    memory: ['Memory', 'Knowledge base · episodic + semantic'],
    graph: ['Memory Graph', 'Neural cartography · force-directed'],
    sleep: ['Sleep', 'Consolidation & dream cycles'],
    events: ['Events', 'Live event bus stream'],
    gateway: ['Gateway', 'Inference routing · cost tracking'],
    identity: ['Identity', 'Three-layer persona architecture'],
  };
  const [title, subtitle] = titles[activePage] || ['', ''];
  const [connected] = useState(true);

  return (
    <header style={{
      height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 24px', borderBottom: '1px solid var(--border)', flexShrink: 0,
    }}>
      <div>
        <div className="t-h2" style={{ lineHeight: 1 }}>{title}</div>
        <div className="t-small" style={{ color: 'var(--muted-foreground)', marginTop: 2 }}>{subtitle}</div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Pill onClick={() => setOpen(true)} style={{ cursor: 'pointer', fontSize: 9, padding: '2px 8px' }}>⌘K</Pill>
        <Pill border="var(--border)">v0.7.0</Pill>
        <Pill color="var(--success)" border="oklch(0.73 0.19 150 / 0.3)"><strong>7</strong>/8 healthy</Pill>
        {connected ? (
          <Pill color="var(--primary)" bg="var(--primary-subtle)" border="oklch(0.6678 0.2232 36.66 / 0.3)">
            <span className="pulse-amber" style={{ display: 'inline-block', width: 6, height: 6, borderRadius: 3, background: 'var(--primary)' }} />
            CONNECTED
          </Pill>
        ) : (
          <Pill color="var(--destructive)" border="oklch(0.65 0.23 26 / 0.3)">○ OFFLINE</Pill>
        )}
      </div>
    </header>
  );
};

// Export contexts
export { NavContext, CmdContext };