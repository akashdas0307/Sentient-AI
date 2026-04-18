import React from 'react';
import { DashboardLayout } from './layouts/DashboardLayout';
import { ChatPanel } from './components/ChatPanel';
import { HealthPanel } from './components/HealthPanel';
import { EventsPanel } from './components/EventsPanel';
import { StatusPanel } from './components/StatusPanel';
import { MemoryPanel } from './components/MemoryPanel';
import { useWebSocket } from './hooks/useWebSocket';

const App: React.FC = () => {
  const { messages, sendChat, healthSnapshot } = useWebSocket('/ws');

  const handleSendMessage = (text: string) => {
    const success = sendChat(text);
    if (!success) {
      console.warn('WS not connected, falling back to REST API');
      fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, session_id: 'default' })
      }).catch(err => console.error('REST fallback failed', err));
    }
  };

  return (
    <DashboardLayout
      rightPanel={
        <>
          <StatusPanel />
          <MemoryPanel />
          <HealthPanel snapshot={healthSnapshot} />
          <EventsPanel events={messages as any} />
        </>
      }
    >
      <ChatPanel
        onSendMessage={handleSendMessage}
        messages={messages}
      />
    </DashboardLayout>
  );
};

export default App;
