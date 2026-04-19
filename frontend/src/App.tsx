import React from 'react';
import { Routes, Route } from 'react-router';
import { DashboardLayout } from './layouts/DashboardLayout';
import { ChatPage } from './pages/ChatPage';
import { ModulesPage } from './pages/ModulesPage';
import { MemoryPage } from './pages/MemoryPage';
import { MemoryGraphPage } from './pages/MemoryGraphPage';
import { SleepPage } from './pages/SleepPage';
import { EventsPage } from './pages/EventsPage';
import { GatewayPage } from './pages/GatewayPage';
import { IdentityPage } from './pages/IdentityPage';
import { useWebSocket } from './hooks/useWebSocket';

const App: React.FC = () => {
  const { sendChat } = useWebSocket('/ws');

  const handleSendMessage = (text: string) => {
    const success = sendChat(text);
    if (!success) {
      fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, session_id: 'default' }),
      }).catch((err) => console.error('REST fallback failed', err));
    }
  };

  return (
    <div className="dark h-screen w-full">
      <Routes>
        <Route element={<DashboardLayout />}>
          <Route index element={<ChatPage onSendMessage={handleSendMessage} />} />
          <Route path="modules" element={<ModulesPage />} />
          <Route path="memory" element={<MemoryPage />} />
          <Route path="graph" element={<MemoryGraphPage />} />
          <Route path="sleep" element={<SleepPage />} />
          <Route path="events" element={<EventsPage />} />
          <Route path="gateway" element={<GatewayPage />} />
          <Route path="identity" element={<IdentityPage />} />
        </Route>
      </Routes>
    </div>
  );
};

export default App;