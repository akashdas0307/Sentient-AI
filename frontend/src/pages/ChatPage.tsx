import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Send, User, Bot, Sparkles, Trash2, Clock, Trash } from 'lucide-react';
import { useSentientStore } from '../store/useSentientStore';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

interface ChatMessage {
  id: string;
  text: string;
  sender: 'user' | 'assistant';
  timestamp: number;
}

export const ChatPage: React.FC<{ onSendMessage: (text: string) => void }> = ({ onSendMessage }) => {
  const [inputText, setInputText] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsMessages = useSentientStore((s) => s.messages);
  const clearHistory = useSentientStore((s) => s.clearMessages);
  const deleteMessage = useSentientStore((s) => s.deleteMessage);

  // Derived messages for the UI
  const displayMessages = useMemo(() => {
    return wsMessages
      .filter(m => m.type === 'reply' || (m.type === 'event' && m.event_name === 'chat.input.received'))
      .map(m => {
        const isUser = m.type === 'event' && m.event_name === 'chat.input.received' || m.payload?.sender === 'user';
        return {
          id: m.turn?.turn_id || m.turn_id || m.timestamp.toString(),
          text: m.turn?.assistant_reply || m.text || (m as any).data?.text || '',
          sender: isUser ? 'user' : 'assistant' as const,
          timestamp: m.timestamp,
        };
      })
      .filter(m => m.text) // Filter out empty messages
      .sort((a, b) => a.timestamp - b.timestamp);
  }, [wsMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [displayMessages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;

    onSendMessage(inputText);
    setInputText('');
  };

  return (
    <div className="flex flex-col h-full bg-background/50">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border bg-card/30 backdrop-blur-md flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center border border-primary/20 shadow-inner">
            <Sparkles size={20} className="text-primary animate-pulse" />
          </div>
          <div>
            <h2 className="text-lg font-bold tracking-tight text-foreground leading-none mb-1">Cognitive Link</h2>
            <div className="flex items-center gap-1.5">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-success"></span>
              </span>
              <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-mono font-bold">Synaptic Bridge Active</span>
            </div>
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={clearHistory}
          className="text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
          title="Purge short-term memory"
        >
          <Trash2 size={16} />
        </Button>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1">
        <div className="p-6 space-y-8 max-w-4xl mx-auto w-full pb-12">
          {displayMessages.length === 0 ? (
            <div className="h-[50vh] flex flex-col items-center justify-center text-muted-foreground space-y-6 opacity-40">
              <div className="relative">
                <div className="w-20 h-20 rounded-3xl bg-muted flex items-center justify-center border border-border shadow-2xl rotate-3 transition-transform hover:rotate-0 duration-500">
                  <Bot size={40} strokeWidth={1.5} className="text-muted-foreground" />
                </div>
                <div className="absolute -bottom-2 -right-2 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20 backdrop-blur-sm">
                  <Sparkles size={16} className="text-primary" />
                </div>
              </div>
              <div className="text-center space-y-2">
                <p className="text-sm font-bold uppercase tracking-[0.2em] text-foreground">Tabula Rasa</p>
                <p className="text-xs font-mono max-w-[200px] leading-relaxed">Cognitive core awaiting initial stimulus for pattern recognition.</p>
              </div>
            </div>
          ) : (
            <AnimatePresence initial={false}>
              {displayMessages.map((msg) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 10, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.3, ease: "easeOut" }}
                  className={cn(
                    "flex w-full group",
                    msg.sender === 'user' ? 'justify-end' : 'justify-start'
                  )}
                >
                  <div className={cn(
                    "flex max-w-[85%] gap-4",
                    msg.sender === 'user' ? 'flex-row-reverse' : 'flex-row'
                  )}>
                    <div className={cn(
                      "w-9 h-9 rounded-xl flex items-center justify-center shrink-0 border shadow-sm transition-transform group-hover:scale-110 duration-200 mt-1",
                      msg.sender === 'user'
                        ? 'bg-muted border-border text-muted-foreground'
                        : 'bg-primary/10 border-primary/20 text-primary shadow-primary/5'
                    )}>
                      {msg.sender === 'user' ? <User size={16} /> : <Bot size={16} />}
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <div className={cn("flex items-center gap-2", msg.sender === 'user' ? 'flex-row-reverse' : 'flex-row')}>
                        <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60">
                          {msg.sender === 'user' ? 'Guardian' : 'Sentient'}
                        </span>
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-5 w-5 rounded-md text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10"
                            onClick={() => deleteMessage(msg.timestamp)}
                          >
                            <Trash size={10} />
                          </Button>
                        </div>
                      </div>

                      <Card className={cn(
                        "p-4 shadow-sm border-border relative overflow-hidden group/card",
                        msg.sender === 'user'
                          ? 'bg-muted/30 rounded-tr-none'
                          : 'bg-card rounded-tl-none border-primary/10'
                      )}>
                        {msg.sender === 'assistant' && (
                          <div className="absolute top-0 left-0 w-1 h-full bg-primary/20" />
                        )}
                        <p className="text-sm leading-relaxed whitespace-pre-wrap font-sans selection:bg-primary/20">
                          {msg.text}
                        </p>
                        <div className={cn(
                          "mt-3 pt-2 border-t border-border/20 flex items-center gap-2 text-[9px] font-mono text-muted-foreground/50",
                          msg.sender === 'user' ? 'justify-end' : 'justify-start'
                        )}>
                          <Clock size={10} />
                          {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                          <Separator orientation="vertical" className="h-2" />
                          <span>TS: {msg.timestamp}</span>
                        </div>
                      </Card>
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          )}
          <div ref={messagesEndRef} className="h-8" />
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="p-6 border-t border-border bg-card/30 backdrop-blur-xl relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-primary/20 to-transparent" />
        <form onSubmit={handleSubmit} className="relative max-w-4xl mx-auto flex gap-3">
          <div className="relative flex-1 group">
            <Input
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Input semantic stimulus..."
              className="w-full bg-background/50 border-border rounded-2xl py-7 pl-6 pr-14 text-sm focus-visible:ring-primary/20 focus-visible:border-primary transition-all duration-300 shadow-inner group-focus-within:bg-background"
            />
            <div className="absolute right-5 top-1/2 -translate-y-1/2 text-muted-foreground/30 pointer-events-none group-focus-within:text-primary transition-colors duration-300">
              <Sparkles size={18} className="animate-pulse" />
            </div>
          </div>
          <Button
            type="submit"
            disabled={!inputText.trim()}
            size="icon"
            className="h-14 w-14 rounded-2xl bg-primary text-primary-foreground hover:scale-105 active:scale-95 transition-all duration-200 disabled:bg-muted disabled:text-muted-foreground disabled:scale-100 shrink-0 shadow-xl shadow-primary/20 flex items-center justify-center border-t border-white/10"
          >
            <Send size={22} className={cn(inputText.trim() && "animate-in slide-in-from-left-2")} />
          </Button>
        </form>
        <div className="flex items-center justify-center gap-4 mt-4">
          <p className="text-[9px] text-muted-foreground uppercase tracking-[0.3em] opacity-40 font-mono">
            Direct neural link • v0.7.0 • End-to-end encrypted
          </p>
        </div>
      </div>
    </div>
  );
};
