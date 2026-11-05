import React from 'react';
import { useChatContext } from '../../context/ChatContext';

export function Header() {
  const { activeSession, systemOnline } = useChatContext();

  return (
    <header className="header">
      <div className="header-left">
        <h2 className="header-title">{activeSession?.title || 'Agentic RAG'}</h2>
        <span className="header-subtitle">/ agentic-v5</span>
      </div>
      <div className="header-badges">
        <div className="badge">
          {systemOnline ? 'API Connected' : 'Offline'}
        </div>
        <div className="badge">Router • Hybrid + Web • Critic</div>
      </div>
    </header>
  );
}
