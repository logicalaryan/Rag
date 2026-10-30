import React from 'react';
import { useChatContext } from '../../context/ChatContext';

export function Header() {
  const { activeSession, systemOnline } = useChatContext();

  return (
    <header className="header">
      <div className="header-left">
        <h2 className="header-title">{activeSession?.title || 'Agentic RAG'}</h2>
        <span className="header-subtitle">/ production-v6</span>
      </div>
      <div className="header-badges">
        <div className="badge">
          {systemOnline ? 'API Connected' : 'Local Standby'}
        </div>
        <div className="badge">Gemini Flash + Critic</div>
        <div className="badge">TTFT &lt; 400ms</div>
      </div>
    </header>
  );
}
