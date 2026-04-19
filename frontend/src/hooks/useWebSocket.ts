import { useEffect, useCallback, useRef } from 'react';
import { useSentientStore } from '../store/useSentientStore';
import type { WSMessage } from '../types';
import type { InferenceCall } from '../types/gateway';

const MAX_RETRIES = 10;
const MAX_SENT_TURN_IDS = 200;

export const useWebSocket = (url: string) => {
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number>(0);
  const retryCountRef = useRef<number>(0);
  const sentTurnIdsRef = useRef<Set<string>>(new Set());

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

        // Skip chat.input.received if we already added it optimistically (prevents duplicate)
        let skipAdd = false;
        if (message.type === 'event' && message.event_name === 'chat.input.received') {
          const eventTurnId = (message as any).turn_id;
          if (eventTurnId && sentTurnIdsRef.current.has(eventTurnId)) {
            sentTurnIdsRef.current.delete(eventTurnId);
            skipAdd = true;
          }
        }

        if (!skipAdd) {
          useSentientStore.getState().addMessage(message);
        }

        switch (message.type) {
          case 'event':
            // chat.input.received dedup already handled above
            // Handle cognitive.cycle.complete for inner monologue
            if (message.event_name === 'cognitive.cycle.complete') {
              const monologue = (message.data as any)?.monologue || '';
              if (monologue) { // Only add non-empty monologue entries
                useSentientStore.getState().addMonologueEntry({
                  id: (message.data as any)?.cycle_id || message.timestamp.toString(),
                  monologue,
                  is_daydream: (message.data as any)?.is_daydream || false,
                  decision_count: (message.data as any)?.decision_count || 0,
                  duration_ms: (message.data as any)?.duration_ms || null,
                  timestamp: message.timestamp,
                });
              }
            }
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
          case 'inference.call.complete': {
            const payload = message as any;
            const call: InferenceCall = {
              timestamp: payload.timestamp || Date.now() / 1000,
              model_label: payload.model_label || 'unknown',
              model_actual: payload.model_actual || 'unknown',
              provider: payload.provider || 'unknown',
              fallback_used: false,
              duration_ms: payload.duration_ms || 0,
              tokens_in: payload.tokens_in || 0,
              tokens_out: payload.tokens_out || 0,
              cost_usd: payload.cost_usd || 0,
              error: null,
            };
            useSentientStore.getState().addGatewayCall(call);
            break;
          }
          case 'inference.call.failed': {
            const payload = message as any;
            const call: InferenceCall = {
              timestamp: payload.timestamp || Date.now() / 1000,
              model_label: payload.model_label || 'unknown',
              model_actual: 'unknown',
              provider: payload.provider || 'unknown',
              fallback_used: false,
              duration_ms: payload.duration_ms || 0,
              tokens_in: 0,
              tokens_out: 0,
              cost_usd: 0,
              error: payload.error || 'Unknown error',
            };
            useSentientStore.getState().addGatewayCall(call);
            break;
          }
          case 'inference.fallback.triggered': {
            const payload = message as any;
            const call: InferenceCall = {
              timestamp: payload.timestamp || Date.now() / 1000,
              model_label: payload.model_label || 'unknown',
              model_actual: payload.model_actual || 'unknown',
              provider: payload.provider || 'unknown',
              fallback_used: true,
              duration_ms: payload.duration_ms || 0,
              tokens_in: payload.tokens_in || 0,
              tokens_out: payload.tokens_out || 0,
              cost_usd: payload.cost_usd || 0,
              error: null,
            };
            useSentientStore.getState().addGatewayCall(call);
            break;
          }
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
    const turnId = `turn_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;

    // Track sent turn_id to prevent duplicate when server echoes back
    sentTurnIdsRef.current.add(turnId);
    // Keep set bounded
    if (sentTurnIdsRef.current.size > MAX_SENT_TURN_IDS) {
      const arr = Array.from(sentTurnIdsRef.current);
      sentTurnIdsRef.current = new Set(arr.slice(-MAX_SENT_TURN_IDS));
    }

    // Optimistically add user message to store for persistence
    useSentientStore.getState().addMessage({
      type: 'reply',
      turn_id: turnId,
      timestamp: Date.now(),
      text: text,
      payload: { sender: 'user' }
    });

    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({
        type: 'chat',
        text,
        session_id: sessionId,
        turn_id: turnId,
      }));
      return true;
    }
    return false;
  }, []);

  useEffect(() => {
    connect();

    // Poll gateway status every 10s
    const pollInterval = setInterval(() => {
      fetch('/api/gateway/status')
        .then((r) => r.json())
        .then((data) => useSentientStore.getState().setGatewayStatus(data))
        .catch(() => {});
    }, 10000);

    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (socketRef.current) socketRef.current.close();
      clearInterval(pollInterval);
    };
  }, [connect]);

  return { sendChat };
};