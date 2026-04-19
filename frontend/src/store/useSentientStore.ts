import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import {
  WSMessage,
  HealthSnapshot,
  TurnRecord,
  SystemStatus,
  MemoryStats
} from '../types';

const MAX_MESSAGES = 200;
const STORAGE_QUOTA_MARGIN = 0.8; // Evict when estimated size exceeds 80% of 5MB

function estimateStateSize(messages: WSMessage[]): number {
  // Rough JSON size estimate without full serialization
  let size = 0;
  for (const m of messages) {
    size += 100; // base overhead per message
    if (m.text) size += m.text.length;
    if (m.data) size += JSON.stringify(m.data).length;
    if (m.payload) size += JSON.stringify(m.payload).length;
  }
  return size;
}

// Custom storage that handles QuotaExceededError by evicting old messages
const safeLocalStorage = {
  getItem: (name: string): string | null => {
    try {
      return localStorage.getItem(name);
    } catch {
      return null;
    }
  },
  setItem: (name: string, value: string): void => {
    try {
      localStorage.setItem(name, value);
    } catch (e) {
      if (e instanceof DOMException && e.name === 'QuotaExceededError') {
        // Evict oldest 50% of messages and retry
        const store = useSentientStore.getState();
        const half = Math.ceil(store.messages.length / 2);
        useSentientStore.setState({
          messages: store.messages.slice(0, half),
        });
        try {
          localStorage.setItem(name, value);
        } catch {
          // Still failing — clear messages entirely and retry
          useSentientStore.setState({ messages: [] });
          try {
            localStorage.setItem(name, value);
          } catch {
            // Give up silently — app works without persistence
          }
        }
      }
    }
  },
  removeItem: (name: string): void => {
    try {
      localStorage.removeItem(name);
    } catch {
      // Ignore
    }
  },
};

interface SentientState {
  messages: WSMessage[];
  healthSnapshot: HealthSnapshot | null;
  isConnected: boolean;
  lastTurn: TurnRecord | null;
  systemStatus: SystemStatus | null;
  memoryStats: MemoryStats | null;

  // Actions
  addMessage: (message: WSMessage) => void;
  setHealthSnapshot: (snapshot: HealthSnapshot | null) => void;
  setConnected: (connected: boolean) => void;
  setLastTurn: (turn: TurnRecord | null) => void;
  setSystemStatus: (status: SystemStatus | null) => void;
  setMemoryStats: (stats: MemoryStats | null) => void;
  clearMessages: () => void;
  deleteMessage: (timestamp: number) => void;
}

export const useSentientStore = create<SentientState>()(
  persist(
    (set) => ({
      messages: [],
      healthSnapshot: null,
      isConnected: false,
      lastTurn: null,
      systemStatus: null,
      memoryStats: null,

      addMessage: (message) => set((state) => {
        // Prevent duplicate messages based on timestamp and type
        const exists = state.messages.some(m => m.timestamp === message.timestamp && m.type === message.type);
        if (exists) return state;

        const newMessages = [message, ...state.messages].slice(0, MAX_MESSAGES);

        // Proactive eviction: if estimated size exceeds quota margin, trim further
        const maxSize = 5 * 1024 * 1024 * STORAGE_QUOTA_MARGIN;
        let trimmed = newMessages;
        while (estimateStateSize(trimmed) > maxSize && trimmed.length > 20) {
          trimmed = trimmed.slice(0, Math.ceil(trimmed.length * 0.7));
        }

        return { messages: trimmed };
      }),

      setHealthSnapshot: (snapshot) => set({ healthSnapshot: snapshot }),

      setConnected: (connected) => set({ isConnected: connected }),

      setLastTurn: (turn) => set({ lastTurn: turn }),

      setSystemStatus: (status) => set({ systemStatus: status }),

      setMemoryStats: (stats) => set({ memoryStats: stats }),

      clearMessages: () => set({ messages: [] }),

      deleteMessage: (timestamp) => set((state) => ({
        messages: state.messages.filter(m => m.timestamp !== timestamp)
      })),
    }),
    {
      name: 'sentient-storage',
      storage: createJSONStorage(() => safeLocalStorage),
      partialize: (state) => ({
        messages: state.messages,
        systemStatus: state.systemStatus,
      }),
    }
  )
);
