import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { motion } from 'framer-motion';

/* ------------------------------------------------------------------ */
/*  Memory type color map -- each type gets a distinct hue            */
/* ------------------------------------------------------------------ */
export const MEMORY_TYPE_COLORS: Record<string, string> = {
  EPISODIC: '#60a5fa',   // blue-400
  SEMANTIC: '#a78bfa',   // violet-400
  PROCEDURAL: '#4ade80', // green-400
  EMOTIONAL: '#fbbf24',  // amber-400
};

export const MEMORY_TYPE_LABELS: Record<string, string> = {
  EPISODIC: 'Episodic',
  SEMANTIC: 'Semantic',
  PROCEDURAL: 'Procedural',
  EMOTIONAL: 'Emotional',
};

/* ------------------------------------------------------------------ */
/*  Node data shape (what the parent puts in node.data)              */
/* ------------------------------------------------------------------ */
export interface MemoryNodeData {
  memory_type: string;
  content: string;
  importance: number;
  confidence: number;
  entity_tags: string[];
  topic_tags: string[];
  created_at: string;
  id: string;
  [key: string]: unknown;
}

/* ------------------------------------------------------------------ */
/*  Custom React Flow node                                            */
/* ------------------------------------------------------------------ */
export const MemoryNode: React.FC<NodeProps> = memo(({ data, selected }) => {
  const d = data as unknown as MemoryNodeData;
  const color = MEMORY_TYPE_COLORS[d.memory_type] ?? '#a3a3a3';
  const label = MEMORY_TYPE_LABELS[d.memory_type] ?? d.memory_type;
  const preview = (d.content ?? '').slice(0, 60) + ((d.content ?? '').length > 60 ? '...' : '');
  const importance = typeof d.importance === 'number' ? d.importance : 0;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2 }}
      className="group relative"
    >
      {/* Glow ring on hover / select */}
      <div
        className="absolute -inset-1.5 rounded-xl transition-opacity duration-300 opacity-0 group-hover:opacity-100"
        style={{
          boxShadow: `0 0 20px 4px ${color}30, 0 0 40px 8px ${color}15`,
          opacity: selected ? 1 : undefined,
        }}
      />

      {/* Card body */}
      <div
        className={[
          'relative w-56 rounded-xl border bg-[var(--bg-2)] px-3 py-2.5 transition-colors duration-150',
          selected
            ? 'border-[var(--border-strong)]'
            : 'border-[var(--border-subtle)] group-hover:border-[var(--border-default)]',
        ].join(' ')}
      >
        {/* Type badge */}
        <div className="flex items-center justify-between mb-1.5">
          <span
            className="text-[10px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded"
            style={{
              color,
              backgroundColor: `${color}18`,
            }}
          >
            {label}
          </span>
          <span
            className="text-[10px] font-mono"
            style={{ color }}
          >
            {(importance * 100).toFixed(0)}%
          </span>
        </div>

        {/* Content preview */}
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed line-clamp-2">
          {preview}
        </p>

        {/* Importance bar */}
        <div className="mt-2 h-1 rounded-full bg-[var(--bg-4)] overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${Math.max(importance * 100, 2)}%`,
              backgroundColor: color,
              boxShadow: `0 0 6px ${color}60`,
            }}
          />
        </div>

        {/* Handles */}
        <Handle
          type="target"
          position={Position.Top}
          className="!w-2 !h-2 !rounded-full !border-0"
          style={{ backgroundColor: `${color}50` }}
        />
        <Handle
          type="source"
          position={Position.Bottom}
          className="!w-2 !h-2 !rounded-full !border-0"
          style={{ backgroundColor: `${color}50` }}
        />
      </div>
    </motion.div>
  );
});

MemoryNode.displayName = 'MemoryNode';

export default MemoryNode;