import { useEffect, useCallback, useRef } from 'react';
import { useSentientStore } from '../store/useSentientStore';
import type { WSMessage } from '../types';

const MAX_RETRIES = 10;

export const useWebSocket = (url: string) => {
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number>(0);
  const retryCountRef = useRef<number>(0);

  const setConnected = useSentientStore((s) => s.setConnected);

  const connect = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = url.startsWith('ws') ? url : `${protocol}//${host}${url}`;

    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      setConnected(true);
      retryCountRef.current = 0;
    };

    socket.onmessage = (event) => {
      try {
        const message: WSMessage = JSON.parse(event.data);

        // Always add to message stream
        useSentientStore.getState().addMessage(message);

        switch (message.type) {
          case 'event':
            // Events are already added to message stream above
            break;
          case 'health':
            useSentientStore.getState().setHealthSnapshot(message.health || (message as any).data);
            break;
          case 'reply':
            const turn = message.turn || {
              turn_id: (message as any).turn_id || '',
              user_message: '',
              assistant_reply: (message as any).text || '',
              events: [],
              started_at: 0,
              completed_at: Date.now() / 1000,
              is_complete: true,
            };
            useSentientStore.getState().setLastTurn(turn);
            break;
          case 'welcome':
            // Fetch system status on connect
            fetch('/api/status')
              .then((r) => r.json())
              .then((data) => useSentientStore.getState().setSystemStatus(data))
              .catch(() => {});
            // Fetch memory stats on connect
            fetch('/api/memory/count')
              .then((r) => r.json())
              .then((data) => useSentientStore.getState().setMemoryStats(data))
              .catch(() => {});
            break;
        }
      } catch (err) {
        console.error('Failed to parse WS message', err);
      }
    };

    socket.onclose = () => {
      setConnected(false);
      if (retryCountRef.current < MAX_RETRIES) {
        const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), 30000);
        reconnectTimeoutRef.current = window.setTimeout(() => {
          retryCountRef.current++;
          connect();
        }, delay);
      }
    };

    socket.onerror = () => {
      socket.close();
    };
  }, [url, setConnected]);

  const sendChat = useCallback((text: string, sessionId: string = 'default') => {
    // Optimistically add user message to store for persistence
    useSentientStore.getState().addMessage({
      type: 'reply', // Using reply type but with user flag or just filtering later
      timestamp: Date.now(),
      text: text,
      payload: { sender: 'user' }
    });

    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({
        type: 'chat',
        text,
        session_id: sessionId,
      }));
      return true;
    }
    return false;
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (socketRef.current) socketRef.current.close();
    };
  }, [connect]);

  return { sendChat };
};