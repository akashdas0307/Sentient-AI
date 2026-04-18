import { useState, useEffect, useCallback, useRef } from 'react';
import { WSMessage, HealthSnapshot, EventMessage, TurnRecord } from '../types';

export const useWebSocket = (url: string) => {
  const [messages, setMessages] = useState<(WSMessage | EventMessage)[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [healthSnapshot, setHealthSnapshot] = useState<HealthSnapshot | null>(null);
  const [lastTurn, setLastTurn] = useState<TurnRecord | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number>(0);
  const retryCountRef = useRef<number>(0);
  const MAX_RETRIES = 5;

  const connect = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = url.startsWith('ws') ? url : `${protocol}//${host}${url}`;

    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      retryCountRef.current = 0;
    };

    socket.onmessage = (event) => {
      try {
        const message: WSMessage = JSON.parse(event.data);

        switch (message.type) {
          case 'health':
            if (message.health) setHealthSnapshot(message.health);
            break;
          case 'event':
            if (message.event) setMessages((prev) => [...prev.slice(-49), message.event!]);
            break;
          case 'reply':
            if (message.turn) {
              setLastTurn(message.turn);
              setMessages((prev) => [...prev, {
                type: 'event',
                stage: 'reply',
                event_name: 'assistant_reply',
                data: { text: message.turn?.assistant_reply },
                timestamp: Date.now(),
                turn_id: message.turn?.turn_id || null
              } as EventMessage]);
            }
            break;
          case 'welcome':
            console.log('Welcome from Sentient AI');
            break;
        }
      } catch (err) {
        console.error('Failed to parse WS message', err);
      }
    };

    socket.onclose = () => {
      setIsConnected(false);
      if (retryCountRef.current < MAX_RETRIES) {
        const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), 30000);
        reconnectTimeoutRef.current = window.setTimeout(() => {
          retryCountRef.current++;
          connect();
        }, delay);
      }
    };

    socket.onerror = (err) => {
      console.error('WebSocket error', err);
      socket.close();
    };
  }, [url]);

  const sendChat = useCallback((text: string, sessionId: string = 'default') => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({
        type: 'chat',
        text,
        session_id: sessionId
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

  return { messages, sendChat, isConnected, healthSnapshot, lastTurn };
};
