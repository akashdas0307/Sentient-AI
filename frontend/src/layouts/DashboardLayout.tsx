import React from 'react';

interface DashboardLayoutProps {
  children: React.ReactNode;
  rightPanel: React.ReactNode;
}

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({ children, rightPanel }) => {
  return (
    <div className="flex flex-col h-screen overflow-hidden md:flex-row">
      {/* Main Content (Chat) */}
      <main className="flex-1 flex flex-col min-w-0 bg-[#111] border-r border-[#333]">
        <header className="h-14 border-b border-[#333] flex items-center px-6 shrink-0">
          <h1 className="text-lg font-bold tracking-tight text-white uppercase tracking-[0.2em]">
            Sentient AI <span className="text-[#666] ml-2 font-normal text-xs uppercase tracking-widest">Cognitive Core v0.7.0</span>
          </h1>
        </header>
        <div className="flex-1 overflow-hidden">
          {children}
        </div>
      </main>

      {/* Right Sidebar */}
      <aside className="w-full md:w-80 lg:w-96 shrink-0 bg-[#1c1c1c] overflow-y-auto flex flex-col p-4 space-y-4">
        {rightPanel}
      </aside>
    </div>
  );
};
