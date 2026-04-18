import React from 'react';
import { Activity } from 'lucide-react';
import { HealthSnapshot } from '../types';

interface HealthPanelProps {
  snapshot: HealthSnapshot | null;
}

export const HealthPanel: React.FC<HealthPanelProps> = ({ snapshot }) => {
  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'healthy': return 'bg-green-500';
      case 'degraded': return 'bg-yellow-500';
      case 'error': return 'bg-red-500';
      default: return 'bg-gray-600';
    }
  };

  const modules = snapshot ? Object.entries(snapshot) : [];

  return (
    <div className="bg-[#222] rounded-xl border border-[#333] overflow-hidden">
      <div className="px-4 py-3 border-b border-[#333] flex items-center justify-between bg-[#282828]">
        <h2 className="text-xs font-bold uppercase tracking-widest text-[#888] flex items-center">
          <Activity size={14} className="mr-2" /> Module Health
        </h2>
        {snapshot && (
          <span className="text-[10px] text-green-500 animate-pulse font-bold">LIVE</span>
        )}
      </div>
      <div className="p-4 space-y-3">
        {modules.length === 0 ? (
          <p className="text-xs text-[#555] italic">Waiting for telemetry...</p>
        ) : (
          modules.map(([name, data]) => (
            <div key={name} className="flex items-center justify-between group">
              <span className="text-xs text-[#aaa] font-mono group-hover:text-white transition-colors">{name}</span>
              <div className="flex items-center space-x-2">
                <span className="text-[10px] text-[#555] font-mono">{data.pulse_count}p</span>
                <div className={`w-2 h-2 rounded-full ${getStatusColor(data.status)} shadow-[0_0_8px_rgba(0,0,0,0.5)]`} />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
