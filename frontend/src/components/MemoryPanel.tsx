import React, { useState, useEffect } from 'react';
import { Database } from 'lucide-react';
import { MemoryStats } from '../types';

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
    <div className="bg-[#222] rounded-xl border border-[#333] p-4 flex items-center space-x-4">
      <div className="w-10 h-10 rounded-lg bg-[#333] flex items-center justify-center shrink-0">
        <Database size={20} className="text-purple-500" />
      </div>
      <div className="flex-1 min-w-0">
        <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#666]">Knowledge Base</h3>
        <div className="flex items-baseline justify-between">
          <span className="text-sm font-bold text-white">{stats?.count?.toLocaleString() || '0'}</span>
          <span className="text-[10px] font-mono text-[#888]">nodes</span>
        </div>
      </div>
    </div>
  );
};
