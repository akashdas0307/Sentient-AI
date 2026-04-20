import React, { useState, useEffect } from 'react';
import './styles/tokens.css';
import {
  NavContext,
  CmdContext,
  ToastProvider,
  CommandPalette,
  Sidebar,
  Header,
} from './components/shared';
import { ChatPage } from './pages/ChatPage';
import { ModulesPage } from './pages/ModulesPage';
import { MemoryPage } from './pages/MemoryPage';
import { MemoryGraphPage } from './pages/MemoryGraphPage';
import { SleepPage } from './pages/SleepPage';
import { EventsPage } from './pages/EventsPage';
import { GatewayPage } from './pages/GatewayPage';
import { IdentityPage } from './pages/IdentityPage';
import { useWebSocket } from './hooks/useWebSocket';

type PageComponent = React.FC<Record<string, unknown>>;

const pages: Record<string, PageComponent> = {
  chat: ChatPage as PageComponent,
  modules: ModulesPage,
  memory: MemoryPage,
  graph: MemoryGraphPage,
  sleep: SleepPage,
  events: EventsPage,
  gateway: GatewayPage,
  identity: IdentityPage,
};

const TWEAK_DEFAULTS = {
  accentHue: 27,
  sidebarCollapsed: false,
  showLiveIndicators: true,
};

const App: React.FC = () => {
  const [page, setPage] = useState(() => localStorage.getItem('sentient-page') || 'chat');
  const [collapsed, setCollapsed] = useState(TWEAK_DEFAULTS.sidebarCollapsed);
  const [cmdOpen, setCmdOpen] = useState(false);

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

  useEffect(() => {
    localStorage.setItem('sentient-page', page);
  }, [page]);

  const PageComponent = pages[page] || pages.chat;

  return (
    <NavContext.Provider value={{ page, setPage, collapsed, setCollapsed }}>
      <CmdContext.Provider value={{ open: cmdOpen, setOpen: setCmdOpen }}>
        <ToastProvider>
          <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
            <Sidebar />
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
              <Header />
              <main
                key={page}
                style={{ flex: 1, overflow: 'hidden', position: 'relative' }}
                className="page-enter"
              >
                {page === 'chat' ? (
                  <ChatPage onSendMessage={handleSendMessage} />
                ) : (
                  <PageComponent />
                )}
              </main>
            </div>
          </div>
          <CommandPalette />
        </ToastProvider>
      </CmdContext.Provider>
    </NavContext.Provider>
  );
};

export default App;