import React from 'react';
import { ListTree } from 'lucide-react';
import { EventMessage } from '../types';

interface EventsPanelProps {
  events: EventMessage[];
}

export const EventsPanel: React.FC<EventsPanelProps> = ({ events }) => {
  return (
    <div className="flex-1 min-h-0 bg-[#222] rounded-xl border border-[#333] flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-[#333] bg-[#282828]">
        <h2 className="text-xs font-bold uppercase tracking-widest text-[#888] flex items-center">
          <ListTree size={14} className="mr-2" /> Recent Events
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-2 font-mono text-[10px]">
        {events.length === 0 ? (
          <p className="text-[#555] italic">Event buffer empty.</p>
        ) : (
          [...events].reverse().map((event, i) => (
            <div key={`${event.timestamp}-${i}`} className="border-l border-[#333] pl-3 py-1 hover:bg-[#2a2a2a] transition-colors">
              <div className="flex justify-between text-[#666]">
                <span>{event.stage}</span>
                <span>{new Date(event.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
              </div>
              <div className="text-[#0088ff] truncate">{event.event_name}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
