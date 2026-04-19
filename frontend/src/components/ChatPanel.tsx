import React, { useState, useEffect, useRef } from 'react';
import { Send, User, Bot } from 'lucide-react';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'assistant';
  timestamp: number;
}

interface ChatPanelProps {
  onSendMessage: (text: string) => void;
  messages: any[]; // Raw messages from WS/API
}

export const ChatPanel: React.FC<ChatPanelProps> = ({ onSendMessage, messages }) => {
  const [inputText, setInputText] = useState('');
  const [localMessages, setLocalMessages] = useState<Message[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [localMessages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;

    const newMessage: Message = {
      id: Date.now().toString(),
      text: inputText,
      sender: 'user',
      timestamp: Date.now()
    };

    setLocalMessages(prev => [...prev, newMessage]);
    onSendMessage(inputText);
    setInputText('');
  };

  // Convert incoming WS events/replies to chat bubbles if appropriate
  useEffect(() => {
    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.event_name === 'assistant_reply' || lastMsg?.stage === 'reply') {
      const text = lastMsg.data?.text || lastMsg.data?.content;
      if (text) {
        setLocalMessages(prev => {
          // Avoid duplicates if turn_id is same
          const lastLocal = prev[prev.length - 1];
          if (lastLocal?.sender === 'assistant' && lastLocal.text === text) return prev;

          return [...prev, {
            id: lastMsg.turn_id || Date.now().toString(),
            text,
            sender: 'assistant',
            timestamp: lastMsg.timestamp || Date.now()
          }];
        });
      }
    }
  }, [messages]);

  return (
    <div className="flex flex-col h-full bg-[#111]">
      {/* Message Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {localMessages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-[#444] space-y-2">
            <Bot size={48} strokeWidth={1} />
            <p className="text-sm">Cognitive core idle. Awaiting stimulus.</p>
          </div>
        )}
        {localMessages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`flex max-w-[80%] space-x-3 ${msg.sender === 'user' ? 'flex-row-reverse space-x-reverse' : 'flex-row'}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                msg.sender === 'user' ? 'bg-[#333]' : 'bg-[#0044ff]/20 text-[#0088ff]'
              }`}>
                {msg.sender === 'user' ? <User size={16} /> : <Bot size={16} />}
              </div>
              <div className={`p-4 rounded-2xl text-sm leading-relaxed ${
                msg.sender === 'user'
                  ? 'bg-[#222] text-white rounded-tr-none border border-[#333]'
                  : 'bg-[#1a1a1a] text-[#ccc] rounded-tl-none border border-[#222]'
              }`}>
                {msg.text}
              </div>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-[#333]">
        <form onSubmit={handleSubmit} className="relative max-w-4xl mx-auto">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Input stimulus..."
            className="w-full bg-[#1a1a1a] border border-[#333] rounded-full py-3 pl-6 pr-14 text-sm focus:outline-none focus:border-[#555] transition-colors font-mono"
          />
          <button
            type="submit"
            disabled={!inputText.trim()}
            className="absolute right-2 top-1.5 p-2 bg-[#333] text-white rounded-full hover:bg-[#444] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  );
};
