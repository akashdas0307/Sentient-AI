import React, { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router';
import { AnimatePresence, motion } from 'framer-motion';
import {
  MessageCircle,
  Activity,
  Database,
  Moon,
  ListTree,
  ChevronLeft,
  ChevronRight,
  Wifi,
  WifiOff,
  Shield,
  Network,
  Zap,
  User,
} from 'lucide-react';
import { useSentientStore } from '../store/useSentientStore';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

const navItems = [
  { path: '/', label: 'Chat', icon: MessageCircle },
  { path: '/modules', label: 'Modules', icon: Activity },
  { path: '/gateway', label: 'Gateway', icon: Zap },
  { path: '/memory', label: 'Memory', icon: Database },
  { path: '/graph', label: 'Graph', icon: Network },
  { path: '/sleep', label: 'Sleep', icon: Moon },
  { path: '/events', label: 'Events', icon: ListTree },
  { path: '/identity', label: 'Identity', icon: User },
];

const pageVariants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
};

export const DashboardLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const isConnected = useSentientStore((s) => s.isConnected);
  const healthSnapshot = useSentientStore((s) => s.healthSnapshot);
  const systemStatus = useSentientStore((s) => s.systemStatus);
  const location = useLocation();

  const healthyCount = healthSnapshot
    ? Object.values(healthSnapshot).filter((m: any) => m.status === 'healthy').length
    : 0;
  const totalModules = healthSnapshot ? Object.keys(healthSnapshot).length : 0;

  return (
    <div className="flex h-screen bg-background overflow-hidden text-foreground">
      {/* Sidebar */}
      <aside className={cn(
        "flex flex-col border-r border-border bg-card transition-all duration-200 shrink-0",
        collapsed ? "w-16" : "w-56"
      )}>
        {/* Logo */}
        <div className={cn(
          "h-14 flex items-center border-b border-border",
          collapsed ? "justify-center" : "px-4"
        )}>
          <Shield size={24} className="text-primary shrink-0" />
          {!collapsed && (
            <span className="ml-3 text-sm font-bold tracking-[0.15em] uppercase text-foreground">
              Sentient
            </span>
          )}
        </div>

        {/* Nav Links */}
        <nav className="flex-1 py-3 space-y-1 px-2 overflow-y-auto">
          {navItems.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 text-sm",
                  isActive
                    ? "bg-primary/10 text-primary font-medium shadow-sm shadow-primary/5"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
                  collapsed ? "justify-center" : ""
                )
              }
            >
              <Icon size={18} className="shrink-0" />
              {!collapsed && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Collapse Toggle */}
        <div className="p-2 border-t border-border bg-card/50">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setCollapsed(!collapsed)}
            className="w-full h-10 hover:bg-muted/50 text-muted-foreground transition-colors"
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </Button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 bg-background">
        {/* Header Bar */}
        <header className="h-14 flex items-center justify-between px-6 border-b border-border bg-card/30 backdrop-blur-sm shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-muted-foreground bg-muted/30 px-2 py-1 rounded border border-border/50">
              {systemStatus?.version ? `v${systemStatus.version}` : 'v0.7.0'}
            </span>
          </div>
          <div className="flex items-center gap-6">
            {totalModules > 0 && (
              <span className="text-xs font-mono text-muted-foreground hidden sm:inline-block">
                <span className="text-success font-bold">{healthyCount}</span>/{totalModules} modules healthy
              </span>
            )}
            <div className={cn(
              "flex items-center gap-1.5 text-xs font-mono px-2 py-1 rounded-full border",
              isConnected
                ? "text-success border-success/20 bg-success/5"
                : "text-destructive border-destructive/20 bg-destructive/5"
            )}>
              {isConnected ? <Wifi size={12} /> : <WifiOff size={12} />}
              {isConnected ? 'CONNECTED' : 'OFFLINE'}
            </div>
          </div>
        </header>

        {/* Page Content with Animation */}
        <main className="flex-1 overflow-hidden relative">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="h-full w-full overflow-y-auto"
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
};
