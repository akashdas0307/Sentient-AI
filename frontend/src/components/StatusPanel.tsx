import React, { useState, useEffect } from 'react';
import { Shield, Cpu } from 'lucide-react';
import { SystemStatus } from '../types';

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

  return (
    <div className="bg-[#222] rounded-xl border border-[#333] p-4 flex items-center space-x-4">
      <div className="w-10 h-10 rounded-lg bg-[#333] flex items-center justify-center shrink-0">
        <Shield size={20} className="text-[#0088ff]" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex justify-between items-baseline">
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#666]">System Integrity</h3>
          <span className="text-[10px] font-mono text-[#444]">{status?.version || 'v0.0.0'}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm font-bold text-white uppercase">{status?.status || 'UNKNOWN'}</span>
          <span className="text-[10px] font-mono text-[#888]">{status ? formatUptime(status.uptime) : '--:--'}</span>
        </div>
      </div>
    </div>
  );
};
