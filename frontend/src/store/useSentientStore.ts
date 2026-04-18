import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import {
  WSMessage,
  HealthSnapshot,
  TurnRecord,
  SystemStatus,
  MemoryStats
} from '../types';

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

        // If it's an event, we might want to update an existing turn record instead of just adding it
        // but for now we keep the append logic and the UI filters

        return {
          messages: [message, ...state.messages].slice(0, 5000) // Increased limit for full history
        };
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
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        messages: state.messages,
        systemStatus: state.systemStatus,
      }),
    }
  )
);
