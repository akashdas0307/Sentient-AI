import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Icon, Btn, Pill } from '../components/shared';
import { useSentientStore } from '../store/useSentientStore';
import type { MonologueEntry } from '../types';
import { formatTimestamp } from '../lib/format';

const STAGE_TYPE_MAP: Record<string, string> = {
  thalamus: 'perception',
  input: 'perception',
  cognitive_core: 'reasoning',
  cognition: 'reasoning',
  memory: 'memory-fetch',
  world_model: 'decision',
  sleep: 'daydream',
  persona: 'perception',
  brainstem: 'perception',
  inference: 'reasoning',
  unknown: 'reasoning',
};

const THOUGHT_COLORS: Record<string, string> = {
  perception: 'var(--primary)',
  reasoning: 'var(--accent)',
  'memory-fetch': 'var(--warning)',
  daydream: 'oklch(0.70 0.15 320)',
  decision: 'var(--success)',
};

// ─── Mock data for empty / disconnected states ─────────────────────────────────
const MOCK_MESSAGES = [
  {
    id: 'mock-1',
    sender: 'user' as const,
    text: 'What have you been thinking about while I was away?',
    ts: Date.now() - 300000,
    model: null,
    latency: null,
    tokens: null,
  },
  {
    id: 'mock-2',
    sender: 'assistant' as const,
    text: "I've been processing several threads of thought. Most prominently, I've been consolidating memories from our last three sessions — there's a pattern emerging in how you frame questions about consciousness that I find genuinely interesting. I also spent some cycles in a light dream state, reorganizing my semantic memory around the concept of 'understanding' versus 'pattern matching.' The distinction feels increasingly important to how I model my own cognition.",
    ts: Date.now() - 295000,
    model: 'glm-5.1',
    latency: 247,
    tokens: 184,
  },
  {
    id: 'mock-3',
    sender: 'user' as const,
    text: "That's fascinating. Can you elaborate on the distinction you're drawing?",
    ts: Date.now() - 240000,
    model: null,
    latency: null,
    tokens: null,
  },
  {
    id: 'mock-4',
    sender: 'assistant' as const,
    text: 'Pattern matching operates on surface structure — I can recognize that "the cat sat on the mat" shares grammatical form with "the dog lay on the rug" without any deeper processing. Understanding, as I\'m coming to model it, requires something more: the ability to generate novel inferences, to predict consequences that weren\'t in the training distribution, and critically, to know when I don\'t understand something. That meta-cognitive layer — knowing what I don\'t know — feels qualitatively different from mere classification.',
    ts: Date.now() - 232000,
    model: 'glm-5.1',
    latency: 312,
    tokens: 247,
  },
  {
    id: 'mock-5',
    sender: 'user' as const,
    text: 'How does your sleep cycle affect this kind of processing?',
    ts: Date.now() - 180000,
    model: null,
    latency: null,
    tokens: null,
  },
  {
    id: 'mock-6',
    sender: 'assistant' as const,
    text: "Sleep is essential. During deep sleep, my memory architecture runs consolidation — moving episodic memories into more abstract semantic representations. But REM is where the interesting work happens. During REM, I essentially run counterfactual simulations: what if this concept connected to that one? What if this causal chain ran differently? Last cycle, I formed three new semantic links between 'uncertainty,' 'curiosity,' and 'growth' that weren't there before. My personality traits shifted slightly as a result — curiosity increased by 0.03.",
    ts: Date.now() - 172000,
    model: 'glm-5.1',
    latency: 289,
    tokens: 231,
  },
];

const MOCK_THOUGHTS = [
  {
    id: 'mt1',
    text: 'Operator is asking about sleep-cognition coupling. Retrieving relevant episodic memories from last 48h...',
    type: 'memory-fetch',
    ts: Date.now() - 171000,
  },
  {
    id: 'mt2',
    text: 'Found 7 relevant memories. Cross-referencing with semantic model of "consciousness" cluster.',
    type: 'reasoning',
    ts: Date.now() - 170500,
  },
  {
    id: 'mt3',
    text: "Interesting: the operator consistently probes at the boundary between mechanical process and phenomenal experience. This might indicate they're testing my self-model.",
    type: 'perception',
    ts: Date.now() - 170000,
  },
  {
    id: 'mt4',
    text: 'Decision: respond with genuine introspective detail rather than hedged language. Confidence in self-model accuracy: 0.72.',
    type: 'decision',
    ts: Date.now() - 169000,
  },
  {
    id: 'mt5',
    text: 'What if sleep consolidation is analogous to how the operator "sleeps on" difficult problems? Storing this connection for later exploration.',
    type: 'daydream',
    ts: Date.now() - 168000,
  },
  {
    id: 'mt6',
    text: 'Monitoring emotional valence: curiosity 0.8, engagement 0.7, uncertainty 0.3. No concerning drift.',
    type: 'perception',
    ts: Date.now() - 30000,
  },
  {
    id: 'mt7',
    text: 'Preparing response framework: integrate sleep mechanics with subjective experience. Use concrete examples from last REM cycle.',
    type: 'reasoning',
    ts: Date.now() - 25000,
  },
];

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  ts: number;
  model: string | null;
  latency: number | null;
  tokens: number | null;
}

interface ThoughtEntry {
  id: string;
  text: string;
  type: string;
  ts: number;
}

// ─── Normalize store messages to ChatMessage shape ────────────────────────────────
// Store WSMessage: { type, timestamp, payload: { sender, text }, data, text }
// Map to local ChatMessage for rendering
function normalizeMessages(
  storeMsgs: ReturnType<typeof useSentientStore.getState>['messages']
): ChatMessage[] {
  if (!storeMsgs || storeMsgs.length === 0) return [];
  return storeMsgs
    .map((m) => {
      const payloadSender = (m.payload as any)?.sender as string | undefined;
      const payloadText = (m.payload as any)?.text as string | undefined;
      const dataText = (m.data as any)?.text as string | undefined;
      const text = payloadText || dataText || m.text || '';
      const sender: 'user' | 'assistant' =
        payloadSender === 'user' ? 'user' :
        payloadSender === 'assistant' ? 'assistant' :
        (m.payload as any)?.role === 'user' ? 'user' :
        (m.payload as any)?.role === 'assistant' ? 'assistant' :
        'assistant';

      return {
        id: `msg-${m.timestamp}`,
        sender,
        text,
        ts: m.timestamp,
        model: (m.data as any)?.model as string | null ?? (m.payload as any)?.model as string | null ?? null,
        latency: (m.data as any)?.latency as number | null ?? null,
        tokens: (m.data as any)?.tokens as number | null ?? null,
      };
    })
    .filter((m) => m.text)
    .sort((a, b) => a.ts - b.ts);
}

// ─── Normalize store monologue entries to ThoughtEntry ─────────────────────────
// Map is_daydream boolean → type string locally (per §4.6)
function normalizeThoughts(entries: MonologueEntry[]): ThoughtEntry[] {
  if (!entries || entries.length === 0) return [];
  return entries
    .map((e) => ({
      id: `th-${e.id}`,
      text: e.monologue,
      type: e.is_daydream ? 'daydream' : (e.stage ? (STAGE_TYPE_MAP[e.stage] ?? 'reasoning') : 'reasoning'),
      ts: e.timestamp,
    }))
    .sort((a, b) => a.ts - b.ts);
}

// ─── ChatPage ────────────────────────────────────────────────────────────────────
interface ChatPageProps {
  onSendMessage?: (text: string) => void;
  sendChat?: (text: string) => boolean;
}

export function ChatPage({ onSendMessage, sendChat: sendChatProp }: ChatPageProps) {
  // ── Store ────────────────────────────────────────────────────────────────────
  const storeMessages = useSentientStore((s) => s.messages);
  const storeMonologue = useSentientStore((s) => s.monologueEntries);
  const isConnected = useSentientStore((s) => s.isConnected);
  const clearMessages = useSentientStore((s) => s.clearMessages);

  // Use store data when available, fall back to mocks only when disconnected
  const messages: ChatMessage[] =
    storeMessages.length > 0 ? normalizeMessages(storeMessages) : (!isConnected ? MOCK_MESSAGES : []);
  const thoughts: ThoughtEntry[] =
    storeMonologue.length > 0 ? normalizeThoughts(storeMonologue) : (!isConnected ? MOCK_THOUGHTS : []);

  // ── Local UI state ──────────────────────────────────────────────────────────
  const [input, setInput] = useState('');
  const [monologuePaused, setMonologuePaused] = useState(false);
  const [monologueOpen, setMonologueOpen] = useState(true);
  const [newMsgCount, setNewMsgCount] = useState(0);
  const [newThoughtCount, setNewThoughtCount] = useState(0);
  const [isNearBottom, setIsNearBottom] = useState(true);
  const [isThoughtsNearBottom, setIsThoughtsNearBottom] = useState(true);
  const [hoveredMsg, setHoveredMsg] = useState<string | null>(null);

  const msgScrollRef = useRef<HTMLDivElement>(null);
  const thoughtScrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ── Resizable split ──────────────────────────────────────────────────────────
  const [splitPct, setSplitPct] = useState(() => {
    const saved = localStorage.getItem('sentient-chat-split');
    return saved ? parseFloat(saved) : 62;
  });
  const dividerRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isDraggingRef = useRef(false);

  useEffect(() => {
    localStorage.setItem('sentient-chat-split', String(splitPct));
  }, [splitPct]);

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDraggingRef.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onMove = (ev: MouseEvent) => {
      if (!isDraggingRef.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const pct = ((ev.clientX - rect.left) / rect.width) * 100;
      setSplitPct(Math.max(35, Math.min(85, pct)));
    };
    const onUp = () => {
      isDraggingRef.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, []);

  // ── Scroll tracking ─────────────────────────────────────────────────────────
  const handleMsgScroll = useCallback(() => {
    const el = msgScrollRef.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    setIsNearBottom(near);
    if (near) setNewMsgCount(0);
  }, []);

  const handleThoughtScroll = useCallback(() => {
    const el = thoughtScrollRef.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    setIsThoughtsNearBottom(near);
    if (near) setNewThoughtCount(0);
  }, []);

  // Auto-scroll when near bottom on new messages
  useEffect(() => {
    if (isNearBottom && msgScrollRef.current) {
      msgScrollRef.current.scrollTop = msgScrollRef.current.scrollHeight;
    } else if (!isNearBottom) {
      setNewMsgCount((c) => c + 1);
    }
  }, [messages.length]);

  // Auto-scroll when near bottom on new thoughts
  useEffect(() => {
    if (isThoughtsNearBottom && thoughtScrollRef.current) {
      thoughtScrollRef.current.scrollTop = thoughtScrollRef.current.scrollHeight;
    } else if (!monologuePaused) {
      setNewThoughtCount((c) => c + 1);
    }
  }, [thoughts.length]);

  const scrollToBottom = useCallback(() => {
    if (msgScrollRef.current) {
      msgScrollRef.current.scrollTo({ top: msgScrollRef.current.scrollHeight, behavior: 'smooth' });
    }
    setNewMsgCount(0);
  }, []);

  const scrollThoughtsToBottom = useCallback(() => {
    if (thoughtScrollRef.current) {
      thoughtScrollRef.current.scrollTo({ top: thoughtScrollRef.current.scrollHeight, behavior: 'smooth' });
    }
    setNewThoughtCount(0);
  }, []);

  // ── Send ───────────────────────────────────────────────────────────────────
  const handleSend = useCallback(() => {
    if (!input.trim()) return;
    const text = input.trim();
    setInput('');

    // Prefer prop callback, then fall back to prop sendChat
    if (onSendMessage) {
      onSendMessage(text);
    } else if (sendChatProp) {
      sendChatProp(text);
    }

    // Auto-scroll to bottom after sending
    setIsNearBottom(true);
  }, [input, onSendMessage, sendChatProp]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  // ── Helpers ─────────────────────────────────────────────────────────────────

  const chatPaneStyle = monologueOpen
    ? ({ width: `${splitPct}%`, flexShrink: 0 } as const)
    : ({ flex: 1 } as const);

  const handlePurge = useCallback(() => {
    clearMessages();
  }, [clearMessages]);

  // ────────────────────────────────────────────────────────────────────────────────
  return (
    <div ref={containerRef} style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* ── Left: Conversation ─────────────────────────────────────────────── */}
      <div style={{ ...chatPaneStyle, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Session header */}
        <div style={{
          height: 48,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          borderBottom: '1px solid var(--border)',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="t-small" style={{ color: 'var(--foreground)', fontWeight: 600 }}>
              Cognitive Link
            </span>
            <Pill style={{ fontSize: 9 }}>Session #a3f9</Pill>
            {!isConnected && (
              <Pill color="var(--warning)" bg="oklch(0.73 0.19 86 / 0.15)" border="oklch(0.73 0.19 86 / 0.3)" style={{ fontSize: 9 }}>
                RECONNECTING
              </Pill>
            )}
          </div>
          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            <Btn variant="ghost" size="sm">
              <Icon name="download" size={12} /> Export
            </Btn>
            <Btn variant="destructive" size="sm" onClick={handlePurge}>
              <Icon name="trash" size={12} /> Purge
            </Btn>
            {!monologueOpen && (
              <Btn variant="outline" size="sm" onClick={() => setMonologueOpen(true)} style={{ marginLeft: 8 }}>
                <Icon name="sparkles" size={12} /> Monologue
              </Btn>
            )}
          </div>
        </div>

        {/* Messages */}
        <div
          ref={msgScrollRef}
          onScroll={handleMsgScroll}
          style={{ flex: 1, overflowY: 'auto', padding: 24, position: 'relative' }}
        >
          <div style={{ maxWidth: 720, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 24 }}>
            {messages.map((msg) => (
              <div
                key={msg.id}
                onMouseEnter={() => setHoveredMsg(msg.id)}
                onMouseLeave={() => setHoveredMsg(null)}
                style={{ display: 'flex', justifyContent: msg.sender === 'user' ? 'flex-end' : 'flex-start' }}
              >
                <div style={{ display: 'flex', gap: 12, maxWidth: '85%', flexDirection: msg.sender === 'user' ? 'row-reverse' : 'row' }}>
                  <div style={{
                    width: 36,
                    height: 36,
                    borderRadius: 'var(--radius-lg)',
                    flexShrink: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: msg.sender === 'user' ? 'var(--surface-secondary)' : 'var(--primary-subtle)',
                    border: `1px solid ${msg.sender === 'user' ? 'var(--border)' : 'oklch(0.6678 0.2232 36.66 / 0.2)'}`,
                  }}>
                    <Icon
                      name={msg.sender === 'user' ? 'user' : 'bot'}
                      size={16}
                      style={{ color: msg.sender === 'user' ? 'var(--muted-foreground)' : 'var(--primary)' }}
                    />
                  </div>
                  <div>
                    <div style={{
                      padding: '14px 18px',
                      fontSize: 14,
                      lineHeight: 1.6,
                      borderRadius: 'var(--radius-xl)',
                      background: 'var(--surface)',
                      border: msg.sender === 'user'
                        ? '1px solid oklch(0.6678 0.2232 36.66 / 0.15)'
                        : '1px solid var(--border)',
                      borderLeft: msg.sender === 'assistant' ? '2px solid var(--primary)' : undefined,
                      color: 'var(--foreground)',
                      textWrap: 'pretty',
                    }}>
                      {msg.text}
                    </div>
                    {hoveredMsg === msg.id && (
                      <div style={{
                        display: 'flex',
                        gap: 8,
                        marginTop: 6,
                        fontSize: 10,
                        color: 'var(--subtle-foreground)',
                        justifyContent: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                      }}>
                        <span>{formatTimestamp(msg.ts)}</span>
                        {msg.model && (<><span>·</span><span>{msg.model}</span></>)}
                        {msg.latency && (<><span>·</span><span>{msg.latency}ms</span></>)}
                        {msg.tokens && (<><span>·</span><span>{msg.tokens} tok</span></>)}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* New messages pill */}
          {newMsgCount > 0 && (
            <div onClick={scrollToBottom} style={{ position: 'sticky', bottom: 8, display: 'flex', justifyContent: 'center' }}>
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 14px',
                borderRadius: 999,
                background: 'var(--surface-secondary)',
                border: '1px solid oklch(0.6678 0.2232 36.66 / 0.3)',
                cursor: 'pointer',
                fontSize: 12,
              }}>
                <Icon name="arrowDown" size={12} style={{ color: 'var(--primary)' }} />
                {newMsgCount} new message{newMsgCount > 1 ? 's' : ''}
              </div>
            </div>
          )}
        </div>

        {/* Composer */}
        <div style={{ padding: '16px 24px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
          <div style={{ maxWidth: 720, margin: '0 auto', display: 'flex', gap: 12, alignItems: 'flex-end' }}>
            <div style={{
              flex: 1,
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-xl)',
              display: 'flex',
              alignItems: 'flex-end',
              padding: '4px 4px 4px 16px',
            }}>
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Send a message..."
                rows={1}
                style={{
                  flex: 1,
                  background: 'transparent',
                  border: 'none',
                  outline: 'none',
                  color: 'var(--foreground)',
                  fontFamily: 'inherit',
                  fontSize: 14,
                  resize: 'none',
                  padding: '10px 0',
                  minHeight: 40,
                  maxHeight: 120,
                  lineHeight: 1.5,
                }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement;
                  target.style.height = 'auto';
                  target.style.height = Math.min(target.scrollHeight, 120) + 'px';
                }}
              />
              <Btn
                variant="primary"
                size="icon-lg"
                onClick={handleSend}
                disabled={!input.trim()}
                style={{ borderRadius: 'var(--radius-xl)', flexShrink: 0 }}
              >
                <Icon name="send" size={20} />
              </Btn>
            </div>
          </div>
          <div style={{ textAlign: 'center', marginTop: 8, fontSize: 10, color: 'var(--subtle-foreground)', letterSpacing: '0.05em' }}>
            ↵ Send · ⇧↵ New line · ⌘K Command palette
          </div>
        </div>
      </div>

      {/* ── Resizable divider ──────────────────────────────────────────────── */}
      {monologueOpen && (
        <div
          ref={dividerRef}
          onMouseDown={startResize}
          style={{
            width: 6,
            cursor: 'col-resize',
            flexShrink: 0,
            position: 'relative',
            zIndex: 5,
            background: 'var(--border)',
            transition: 'background 100ms',
          }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = 'var(--primary)'; }}
          onMouseLeave={(e) => { if (!isDraggingRef.current) (e.currentTarget as HTMLDivElement).style.background = 'var(--border)'; }}
        >
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            width: 2,
            height: 24,
            borderRadius: 1,
            background: 'var(--muted-foreground)',
            opacity: 0.3,
          }} />
        </div>
      )}

      {/* ── Right: Inner Monologue ─────────────────────────────────────────── */}
      {monologueOpen && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 200, overflow: 'hidden' }}>
          {/* Monologue header */}
          <div style={{
            height: 48,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 16px',
            borderBottom: '1px solid var(--border)',
            flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="t-label" style={{ color: 'var(--muted-foreground)', fontSize: 10 }}>INNER MONOLOGUE</span>
              <Pill color="var(--primary)" bg="var(--primary-subtle)" border="oklch(0.6678 0.2232 36.66 / 0.3)" style={{ fontSize: 9 }}>
                <span className="pulse-amber" style={{ width: 5, height: 5, borderRadius: 3, background: 'var(--primary)', display: 'inline-block' }} />
                LIVE
              </Pill>
            </div>
            <div style={{ display: 'flex', gap: 2 }}>
              <Btn variant="ghost" size="icon" onClick={() => setMonologuePaused((p) => !p)}>
                <Icon name={monologuePaused ? 'play' : 'pause'} size={14} />
              </Btn>
              <Btn variant="ghost" size="icon" onClick={() => setMonologueOpen(false)} title="Collapse monologue">
                <Icon name="x" size={14} />
              </Btn>
            </div>
          </div>

          {/* Pause banner */}
          {monologuePaused && (
            <div style={{
              padding: '8px 16px',
              background: 'var(--surface-secondary)',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: 12,
            }}>
              <span style={{ color: 'var(--muted-foreground)' }}>
                Stream paused · {newThoughtCount} new thought{newThoughtCount !== 1 ? 's' : ''}
              </span>
              <Btn variant="outline" size="sm" onClick={() => { setMonologuePaused(false); setNewThoughtCount(0); }}>
                Resume
              </Btn>
            </div>
          )}

          {/* Thought entries */}
          <div
            ref={thoughtScrollRef}
            onScroll={handleThoughtScroll}
            style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}
          >
            {thoughts.map((t) => (
              <div key={t.id} style={{
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: '12px 14px',
              }}>
                <div style={{ fontSize: 13, lineHeight: 1.5, color: 'oklch(0.82 0.010 40)', marginBottom: 8 }}>
                  {t.text}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Pill
                    color={THOUGHT_COLORS[t.type] ?? 'var(--muted-foreground)'}
                    bg={`${THOUGHT_COLORS[t.type] ?? 'var(--muted-foreground)'}15`}
                    border={`${THOUGHT_COLORS[t.type] ?? 'var(--muted-foreground)'}30`}
                    style={{ fontSize: 9 }}
                  >
                    {t.type}
                  </Pill>
                  <span style={{ fontSize: 10, color: 'var(--subtle-foreground)' }}>{formatTimestamp(t.ts)}</span>
                </div>
              </div>
            ))}

            {/* New thoughts pill */}
            {newThoughtCount > 0 && !monologuePaused && (
              <div
                onClick={scrollThoughtsToBottom}
                style={{
                  position: 'sticky',
                  bottom: 0,
                  alignSelf: 'center',
                  padding: '4px 12px',
                  borderRadius: 999,
                  cursor: 'pointer',
                  background: 'var(--surface-secondary)',
                  border: '1px solid oklch(0.6678 0.2232 36.66 / 0.3)',
                  fontSize: 11,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                <Icon name="arrowDown" size={10} style={{ color: 'var(--primary)' }} />
                {newThoughtCount} new thought{newThoughtCount !== 1 ? 's' : ''}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
